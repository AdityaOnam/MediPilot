"""
M05 — Hosted Whisper ASR via the Groq API.

Same scope and the same guarantees as speech/whisper_stt.py: speech ->
transcript + ASR-observable metadata ONLY. No diagnosis, no acuity, no risk,
no red flags, no questioning logic. This module corresponds to blocks (3)/(4)
of intake_architecture part 1 and produces only the raw material the LLM
structurer (M06) and the deterministic red-flag pass (M07) consume.

Why hosted rather than local
----------------------------
round2-implementation-plan.html §16 lists "speech integration slips" as a
Medium risk and requires the demo not to depend on it. The development
hardware has an AMD Radeon RX 6500M -- no CUDA, no ROCm-on-Windows -- so
local Whisper runs CPU-only at several seconds per utterance. Groq serves
whisper-large-v3-turbo at roughly real-time-x100, needs no GPU, no tunnel,
and no process to keep alive during the demo. The same GROQ_API_KEY already
used by intake/llm_structurer.py (M06) covers this, so integration adds one
dependency and zero new credentials.

Interchangeability
------------------
GroqWhisperSTT.transcribe() returns exactly the dict speech/whisper_stt.py's
WhisperSTT.transcribe() returns -- both assemble it through
speech/asr_common.py -- so intake/speech_adapter.py can hold either without
modification, and the §16 ASR bake-off can compare them field by field.
"""

from __future__ import annotations

import io
import os
import shutil
import subprocess
from typing import Optional, Union

import numpy as np

from speech import asr_common

# Groq accepts flac/mp3/mp4/mpeg/mpga/m4a/ogg/wav/webm. The browser's
# MediaRecorder produces audio/webm (Opus), which is on that list, so the
# blob is forwarded verbatim rather than transcoded -- one less place to
# fail on demo day, and one less dependency on ffmpeg being installed.
DEFAULT_MODEL = "whisper-large-v3-turbo"

# Groq's documented upload ceiling for the free tier. Checked locally so an
# oversized recording fails with a clear message instead of a 413.
MAX_UPLOAD_BYTES = 25 * 1024 * 1024

_SAMPLE_RATE = 16000


class ASRError(Exception):
    """
    Raised when transcription could not be performed: missing credentials,
    missing package, auth failure, rate limit, connection error, or an
    oversized upload. Callers must NOT fabricate a transcript when this is
    raised -- an empty/failed ASR turn is a real state the intake state
    machine handles (it re-prompts, or falls back to typed input), and
    inventing text here would put words in a patient's mouth.
    """


def _decode_to_waveform(audio_bytes: bytes, suffix: str = "") -> Optional[np.ndarray]:
    """
    Best-effort decode to mono float32 @16kHz, used ONLY for the pre-flight
    RMS silence gate. Returns None when no decoder is available, in which
    case the caller records that the gate was skipped rather than pretending
    it passed.

    Tries soundfile first (handles wav/flac/ogg with no external binary),
    then ffmpeg if it is on PATH (handles webm/opus from the browser).
    """
    try:
        import soundfile as sf

        data, sr = sf.read(io.BytesIO(audio_bytes), dtype="float32", always_2d=True)
        mono = data.mean(axis=1)
        if sr != _SAMPLE_RATE and len(mono) > 1:
            # Cheap linear resample -- adequate for an energy measurement,
            # and never used for the audio that is actually transcribed.
            idx = np.linspace(0, len(mono) - 1, int(len(mono) * _SAMPLE_RATE / sr))
            mono = np.interp(idx, np.arange(len(mono)), mono).astype(np.float32)
        return mono
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


class GroqWhisperSTT:
    """
    Thin wrapper around Groq's hosted Whisper for single-utterance
    (Tap-to-Speak) transcription, matching WhisperSTT's interface.

    Credentials are resolved by the `groq` SDK's default client from the
    GROQ_API_KEY environment variable. This class never reads or hardcodes a
    key itself -- it only checks one is present so it can fail with a clear
    ASRError instead of an opaque SDK error, exactly as
    intake/llm_structurer.py does.
    """

    def __init__(self, model: str = DEFAULT_MODEL, client=None):
        self.model = model
        self._client = client  # allows tests to inject a stub client

    def _ensure_client(self):
        if self._client is not None:
            return self._client
        try:
            import groq
        except ImportError as exc:
            raise ASRError(
                "the 'groq' package is not installed; "
                "install it (`pip install groq`) or inject a client for testing"
            ) from exc

        if not os.environ.get("GROQ_API_KEY"):
            raise ASRError(
                "no Groq credentials found: set the GROQ_API_KEY environment "
                "variable before using GroqWhisperSTT"
            )
        self._client = groq.Groq()
        return self._client

    def transcribe(self, audio: Union[bytes, str, np.ndarray], filename: str = "utterance.webm") -> dict:
        """
        Transcribe one completed audio utterance.

        Parameters
        ----------
        audio:
            Raw encoded audio bytes (what the frontend uploads), a path to an
            audio file, or a mono float32 waveform at 16 kHz. A waveform is
            encoded to WAV before upload.
        filename:
            Name sent with the upload. Only its extension matters -- Groq
            uses it to pick a demuxer.

        Returns
        -------
        dict
            The speech/asr_common.py result contract, identical in shape to
            speech/whisper_stt.py's output, plus `backend` and
            `metrics_available`.
        """
        audio_bytes, filename = self._as_bytes(audio, filename)

        if len(audio_bytes) > MAX_UPLOAD_BYTES:
            raise ASRError(
                f"audio is {len(audio_bytes)} bytes, over the {MAX_UPLOAD_BYTES}-byte "
                f"upload limit; shorten the recording or downsample it"
            )

        # Pre-flight energy gate: never spend a network round trip, and never
        # give the model an opportunity to hallucinate "Thank you.", on audio
        # that carries no signal.
        waveform = _decode_to_waveform(audio_bytes)
        gate_applied = waveform is not None
        if gate_applied and asr_common.is_effectively_silent(waveform):
            result = asr_common.empty_result(no_speech=True, backend=self._backend_name())
            result["silence_gate"] = "fired"
            return result

        client = self._ensure_client()
        import groq

        try:
            response = client.audio.transcriptions.create(
                file=(filename, audio_bytes),
                model=self.model,
                # Transcribe in the language spoken -- never translate. The
                # `language` parameter is deliberately omitted so English,
                # Hindi and Hinglish are all auto-detected, matching
                # whisper_stt.py's `language=None`.
                response_format="verbose_json",
                timestamp_granularities=["segment"],
                temperature=0,
            )
        except groq.AuthenticationError as exc:
            raise ASRError(f"Groq authentication failed: {exc}") from exc
        except groq.RateLimitError as exc:
            raise ASRError(f"Groq rate limited: {exc}") from exc
        except groq.BadRequestError as exc:
            raise ASRError(f"Groq rejected the audio: {exc}") from exc
        except groq.APIConnectionError as exc:
            raise ASRError(f"Groq connection error: {exc}") from exc
        except groq.APIStatusError as exc:
            raise ASRError(f"Groq API error ({exc.status_code}): {exc}") from exc

        text, language, segments = self._unpack(response)
        result = asr_common.build_result(
            text=text,
            # Groq's verbose_json returns the full language NAME ("English",
            # "Hindi"), not the ISO code local Whisper returns ("en", "hi").
            # Every downstream check (SUPPORTED_LANGUAGES, the
            # unsupported_language reliability flag) compares against the
            # code, so leaving this un-normalized flags every correctly
            # transcribed utterance as unsupported. Discovered via the ASR
            # bake-off reporting language_accuracy: 0.0 alongside 0.0 WER.
            language=asr_common.normalize_language_name(language),
            segments=segments,
            backend=self._backend_name(),
        )
        result["silence_gate"] = "applied" if gate_applied else "skipped_no_decoder"
        return result

    # -- internal helpers -----------------------------------------------

    def _backend_name(self) -> str:
        return f"groq:{self.model}"

    @staticmethod
    def _unpack(response) -> tuple:
        """Normalise the SDK response (object or dict) into plain values.
        verbose_json carries per-segment avg_logprob / no_speech_prob /
        compression_ratio, which is what keeps the low-confidence heuristic
        working identically to the local Whisper backend."""
        if isinstance(response, dict):
            payload = response
        else:
            payload = response.model_dump() if hasattr(response, "model_dump") else dict(response)

        segments = payload.get("segments") or []
        segments = [s if isinstance(s, dict) else dict(s) for s in segments]
        return payload.get("text", ""), payload.get("language"), segments

    @staticmethod
    def _as_bytes(audio, filename: str) -> tuple:
        if isinstance(audio, bytes):
            return audio, filename
        if isinstance(audio, np.ndarray):
            return GroqWhisperSTT._wav_bytes(audio), "utterance.wav"
        if isinstance(audio, str):
            with open(audio, "rb") as fh:
                return fh.read(), os.path.basename(audio)
        raise ASRError(f"unsupported audio type: {type(audio).__name__}")

    @staticmethod
    def _wav_bytes(waveform: np.ndarray) -> bytes:
        """Encode a float32 mono waveform as 16-bit PCM WAV, so a waveform
        captured by speech/vad_recorder.py can be uploaded directly."""
        import wave

        pcm = np.clip(np.asarray(waveform, dtype=np.float32), -1.0, 1.0)
        pcm = (pcm * 32767).astype("<i2")
        buf = io.BytesIO()
        with wave.open(buf, "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(_SAMPLE_RATE)
            wf.writeframes(pcm.tobytes())
        return buf.getvalue()


if __name__ == "__main__":
    import json
    import sys

    path = sys.argv[1] if len(sys.argv) > 1 else "speech/f_test1.ogg"
    out = GroqWhisperSTT().transcribe(path)
    out.pop("segments", None)  # too verbose for a console check
    print(json.dumps(out, indent=2, ensure_ascii=False))
