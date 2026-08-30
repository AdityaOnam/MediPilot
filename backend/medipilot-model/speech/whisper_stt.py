"""
Whisper-based ASR for MediPilot.

Scope: speech -> transcript + ASR-observable metadata ONLY.

This module performs no clinical interpretation. It does not assign
diagnosis, acuity, risk, treatment, red flags, or reliability discounts,
and it does not decide on questioning logic. Those responsibilities belong
to the downstream LLM structurer and risk model (see intake_architecture
parts 2/3). This module corresponds to blocks (3)/(4) of intake_architecture
part 1 (Language Detection & Barrier Flag / ASR) and produces only the raw
material those later stages consume.

Usage:
    stt = WhisperSTT()          # loads the model once
    result = stt.transcribe(audio_path_or_waveform)

Each call to transcribe() is treated as one independent, already-complete
utterance (a single Tap-to-Speak recording), matching the frontend's
record-then-send flow. There is no continuous listening or streaming VAD
here, and previous utterances never contaminate the current one
(condition_on_previous_text=False).
"""

import numpy as np
import whisper

from speech import asr_common

# Every silence threshold, hallucination phrase, supported-language set and
# low-confidence rule this module used to define itself now lives in
# speech/asr_common.py, shared verbatim with the hosted backend
# (speech/groq_asr.py). The reasoning behind each constant is documented
# there. They are shared rather than duplicated because the ASR bake-off
# compares the two backends on exactly these flags -- if the heuristics
# differed, the comparison would be measuring the heuristics rather than
# the models.


class WhisperSTT:
    """
    Thin wrapper around openai-whisper for single-utterance (Tap-to-Speak)
    transcription. The model is loaded once in __init__ and reused for every
    transcribe() call.
    """

    def __init__(self, model_name="turbo"):
        self.model_name = model_name
        self.model = whisper.load_model(model_name)

    def transcribe(self, audio):
        """
        Transcribe one completed audio utterance.

        Parameters
        ----------
        audio:
            Audio file path, or a mono float32 numpy waveform at 16kHz
            (e.g. from whisper.load_audio), representing one already-complete
            recording -- not a live/streaming source.

        Returns
        -------
        dict:
            {
                "text": str,                     # transcript in the language spoken (no translation)
                "language": str | None,           # Whisper-detected language code
                "language_confidence": float | None,  # Whisper's own probability for that code
                "code_mixed": bool,               # see asr_common.looks_code_mixed()
                "segments": [...],                # raw Whisper segments (unmodified)
                "asr_reliability": {               # ASR-only heuristics -- NOT clinical confidence
                    "no_speech": bool,
                    "low_confidence": bool,
                    "possible_hallucination": bool,
                    "unsupported_language": bool,
                },
                "asr_metrics": {                   # raw Whisper decoding metadata, preserved
                    "avg_no_speech_prob": float | None,   # for later recalibration of the
                    "avg_logprob": float | None,          # heuristics above without needing
                    "avg_compression_ratio": float | None,# to change this module's API.
                },
                "backend": str,                    # e.g. "whisper-local:turbo" -- which
                                                   # engine produced this, for the bake-off
                "metrics_available": bool,         # False when the backend returned no
                                                   # per-segment logprobs at all
            }

        The shape is assembled by speech/asr_common.build_result() and is
        identical to what speech/groq_asr.py returns, so either backend can
        be dropped into intake/speech_adapter.py unchanged.
        """
        waveform = audio if isinstance(audio, np.ndarray) else whisper.load_audio(audio)

        if asr_common.is_effectively_silent(waveform):
            return asr_common.empty_result(no_speech=True, backend=self._backend_name())

        result = self.model.transcribe(
            waveform,
            # Transcribe in the language spoken -- never translate to English.
            task="transcribe",
            # Auto-detect language so English, Hindi, and Hinglish are all supported.
            language=None,
            # Each Tap-to-Speak recording is one independent utterance; do not
            # let prior utterances bias this one.
            condition_on_previous_text=False,
            temperature=0,
            verbose=False,
        )

        segments = result.get("segments", [])
        text = result["text"].strip()

        if not segments and not text:
            return asr_common.empty_result(no_speech=True, backend=self._backend_name())

        language = result.get("language")
        return asr_common.build_result(
            text=text,
            language=language,
            segments=segments,
            backend=self._backend_name(),
            language_confidence=self._detect_language_confidence(waveform, language),
        )

    # -- internal helpers -----------------------------------------------

    def _backend_name(self):
        return f"whisper-local:{self.model_name}"

    def _detect_language_confidence(self, waveform, detected_language):
        if not detected_language:
            return None
        try:
            mel = whisper.log_mel_spectrogram(
                whisper.pad_or_trim(waveform), n_mels=self.model.dims.n_mels
            ).to(self.model.device)
            _, probs = self.model.detect_language(mel)
            return float(probs.get(detected_language))
        except Exception:
            # Language-confidence is a best-effort convenience signal;
            # never let it break the primary transcription result.
            return None


if __name__ == "__main__":
    import sys

    stt = WhisperSTT()
    audio_path = sys.argv[1] if len(sys.argv) > 1 else "speech/test3.ogg"
    result = stt.transcribe(audio_path)

    print("Language:", result["language"], "(confidence:", result["language_confidence"], ")")
    print("Text:", result["text"])
    print("Code-mixed (heuristic):", result["code_mixed"])
    print("ASR reliability:", result["asr_reliability"])
    print("ASR metrics:", result["asr_metrics"])
