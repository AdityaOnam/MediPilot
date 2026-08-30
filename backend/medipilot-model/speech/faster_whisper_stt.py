"""
M05 — LOCAL Whisper ASR via faster-whisper (CTranslate2).

This is the local-inference path: no network, no API key, no patient audio
leaving the building. Under India's DPDP Act 2023 and the §13 log properties
("Raw patient data stays at the institution"), that is the architecture the
project commits to; the hosted backend (speech/groq_asr.py) is the fallback
that keeps a demo alive, not the destination.

Why faster-whisper rather than openai-whisper
---------------------------------------------
The target hardware has no usable GPU for PyTorch: an AMD Radeon RX 6500M
means no CUDA, and ROCm has no Windows support, so `torch` runs CPU-only and
openai-whisper's `turbo` takes tens of seconds per utterance. faster-whisper
runs the same weights through CTranslate2, which is a CPU-first inference
engine with int8 quantisation — the difference between "unusable" and "a
couple of seconds" on a Ryzen 5 5600H.

It is also the configuration §15 actually promised: "Whisper-class ASR,
quantised". `eval/kaggle/asr_bakeoff.ipynb` measures what the quantisation
costs in accuracy rather than assuming it is free.

Interchangeability
------------------
transcribe() returns exactly the dict speech/whisper_stt.py and
speech/groq_asr.py return -- all three assemble it through
speech/asr_common.py -- so any of them can be dropped into
intake/speech_adapter.py unchanged, and the bake-off compares them field by
field rather than comparing three different post-processors.

Install:  pip install -r requirements-speech-local.txt
"""

from __future__ import annotations

import io
import os
import shutil
import subprocess
import tempfile
from typing import Optional, Union

import numpy as np

from speech import asr_common

# "medium" was chosen empirically, not guessed. On this project's real
# fixtures (speech/test.ogg, Hindi), tested on the actual CPU-only target
# hardware:
#   small  (4.7s/utt)  -- HALLUCINATES: repeats one Devanagari word in an
#                          infinite loop instead of transcribing.
#   base   (1.4s/utt)  -- TRANSLATES the Hindi into English instead of
#                          transcribing it verbatim, violating the "never
#                          translate" contract this whole module documents
#                          (translation can distort clinical meaning M06 and
#                          the red-flag table both depend on being faithful).
#   medium (14.9s/utt) -- correct, faithful, verbatim transcription.
# Slow-but-correct beats fast-but-wrong for a triage system: a hallucinated
# or mistranslated utterance becomes the patient's own reported symptoms
# downstream. Override with MEDIPILOT_WHISPER_MODEL if your hardware can
# afford large-v3, or if you have separately verified a smaller size is
# faithful on your own fixtures.
DEFAULT_MODEL = "medium"

# int8 is the CPU configuration. On a CUDA machine use "float16", and on one
# with limited VRAM "int8_float16".
DEFAULT_COMPUTE_TYPE = "int8"

_SAMPLE_RATE = 16000


class FasterWhisperSTT:
    """
    Local single-utterance (Tap-to-Speak) transcription. The model is loaded
    once in __init__ and reused, matching WhisperSTT's lifecycle.
    """

    def __init__(self, model_name: str = DEFAULT_MODEL,
                 device: str = "auto", compute_type: Optional[str] = None,
                 cpu_threads: int = 0, model=None):
        self.model_name = model_name
        self.compute_type = compute_type or os.getenv(
            "MEDIPILOT_WHISPER_COMPUTE_TYPE", DEFAULT_COMPUTE_TYPE)

        if model is not None:  # injectable for testing
            self.model = model
            return

        try:
            from faster_whisper import WhisperModel
        except ImportError as exc:
            raise RuntimeError(
                "faster-whisper is not installed; "
                "pip install -r requirements-speech-local.txt"
            ) from exc

        self.model = WhisperModel(
            model_name, device=device, compute_type=self.compute_type,
            # 0 lets CTranslate2 pick, which is right on a 6-core laptop.
            cpu_threads=cpu_threads,
        )

    def transcribe(self, audio: Union[bytes, str, np.ndarray],
                   filename: str = "utterance.webm") -> dict:
        """
        Transcribe one completed audio utterance.

        `audio` is a path, raw encoded bytes (what the frontend uploads), or a
        mono float32 waveform at 16 kHz. `filename` is accepted so this class
        is call-compatible with GroqWhisperSTT; only its extension is used,
        and only when bytes are passed.
        """
        waveform, source = self._as_waveform(audio, filename)

        # Same pre-flight energy gate as every other backend. Whisper emits
        # "Thank you." over silence with no_speech_prob ~= 0 -- its own
        # confidence signal does not catch it -- and in this pipeline a
        # hallucinated sentence becomes the patient's reported symptoms.
        if waveform is not None and asr_common.is_effectively_silent(waveform):
            result = asr_common.empty_result(no_speech=True, backend=self._backend_name())
            result["silence_gate"] = "fired"
            return result

        segments, info = self.model.transcribe(
            waveform if waveform is not None else source,
            # Transcribe in the language spoken -- never translate to English.
            task="transcribe",
            # Auto-detect so English, Hindi and Hinglish are all supported,
            # matching whisper_stt.py's `language=None`.
            language=None,
            # Each Tap-to-Speak recording is one independent utterance.
            condition_on_previous_text=False,
            temperature=0,
        )
        segments = list(segments)  # the generator is lazy; decoding happens here

        result = asr_common.build_result(
            text="".join(s.text for s in segments),
            language=info.language,
            segments=[{
                "start": s.start, "end": s.end, "text": s.text,
                "no_speech_prob": s.no_speech_prob,
                "avg_logprob": s.avg_logprob,
                "compression_ratio": s.compression_ratio,
            } for s in segments],
            backend=self._backend_name(),
            language_confidence=info.language_probability,
        )
        result["silence_gate"] = "applied" if waveform is not None else "skipped_no_decoder"
        return result

    # -- internal helpers -----------------------------------------------

    def _backend_name(self) -> str:
        return f"faster-whisper:{self.model_name}/{self.compute_type}"

    def _as_waveform(self, audio, filename: str) -> tuple:
        """
        Returns (waveform_or_None, fallback_source).

        The waveform is what the energy gate needs. When bytes arrive in a
        container this process cannot decode (webm/opus without ffmpeg), the
        waveform is None and the bytes are spilled to a temp file for
        CTranslate2's own decoder -- the gate then reports itself skipped
        rather than silently passing.
        """
        if isinstance(audio, np.ndarray):
            return np.asarray(audio, dtype=np.float32), None
        if isinstance(audio, str):
            return _decode_file(audio), audio
        if isinstance(audio, bytes):
            waveform = _decode_bytes(audio)
            suffix = os.path.splitext(filename)[1] or ".webm"
            with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
                tmp.write(audio)
                return waveform, tmp.name
        raise TypeError(f"unsupported audio type: {type(audio).__name__}")


def _decode_file(path: str) -> Optional[np.ndarray]:
    try:
        import soundfile as sf

        data, sr = sf.read(path, dtype="float32", always_2d=True)
        return _to_mono_16k(data.mean(axis=1), sr)
    except Exception:
        with open(path, "rb") as fh:
            return _decode_bytes(fh.read())


def _decode_bytes(audio_bytes: bytes) -> Optional[np.ndarray]:
    """Best-effort decode for the energy gate only. soundfile handles
    wav/flac/ogg with no external binary; ffmpeg covers webm/opus from the
    browser. Returns None when neither can, so the caller can be honest
    about the gate not having run."""
    try:
        import soundfile as sf

        data, sr = sf.read(io.BytesIO(audio_bytes), dtype="float32", always_2d=True)
        return _to_mono_16k(data.mean(axis=1), sr)
    except Exception:
        pass

    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        return None
    try:
        proc = subprocess.run(
            [ffmpeg, "-nostdin", "-threads", "0", "-i", "pipe:0",
             "-f", "s16le", "-ac", "1", "-acodec", "pcm_s16le",
             "-ar", str(_SAMPLE_RATE), "pipe:1"],
            input=audio_bytes, capture_output=True, check=True, timeout=30,
        )
        return np.frombuffer(proc.stdout, np.int16).astype(np.float32) / 32768.0
    except Exception:
        return None


def _to_mono_16k(mono: np.ndarray, sr: int) -> np.ndarray:
    if sr == _SAMPLE_RATE or len(mono) < 2:
        return mono.astype(np.float32)
    idx = np.linspace(0, len(mono) - 1, int(len(mono) * _SAMPLE_RATE / sr))
    return np.interp(idx, np.arange(len(mono)), mono).astype(np.float32)


if __name__ == "__main__":
    import json
    import sys
    import time

    path = sys.argv[1] if len(sys.argv) > 1 else "speech/f_test1.ogg"
    size = sys.argv[2] if len(sys.argv) > 2 else DEFAULT_MODEL

    t0 = time.perf_counter()
    stt = FasterWhisperSTT(size)
    print(f"loaded {size}/{stt.compute_type} in {time.perf_counter()-t0:.1f}s")

    t0 = time.perf_counter()
    out = stt.transcribe(path)
    print(f"transcribed in {time.perf_counter()-t0:.2f}s")
    out.pop("segments", None)
    print(json.dumps(out, indent=2, ensure_ascii=False))
