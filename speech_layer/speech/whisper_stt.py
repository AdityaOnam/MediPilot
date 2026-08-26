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

import re

import numpy as np
import whisper

# --- Silence handling -------------------------------------------------------
#
# Whisper (including "turbo") is known to hallucinate short filler phrases
# such as "Thank you." on silent/near-silent audio, and its own no_speech_prob
# output is NOT reliable for catching this: empirically (see speech/test_whisper.py
# and the accompanying test suite), literal digital silence produced
# no_speech_prob ~= 0 while still emitting "Thank you." with high confidence.
#
# To fix this at the source rather than trying to post-hoc filter Whisper's
# output, we gate on raw waveform energy (RMS) BEFORE calling the model at
# all. If the audio has no meaningful signal, we skip decoding entirely and
# return text="".
#
# Threshold calibration (measured on available fixtures, see speech/test_whisper.py):
#   - digital silence:                 RMS ~= 0.0
#   - near-silence background noise:   RMS ~= 0.0005
#   - real recorded speech (3 fixtures): RMS ~= 0.12 - 0.14
# 0.01 sits ~20x above the near-silence fixture and ~10x below real speech,
# giving comfortable margin without needing to guess at quiet-speech loudness.
_SILENCE_RMS_THRESHOLD = 0.01

# Whisper's own published default decoding-failure thresholds (see
# whisper/transcribe.py: compression_ratio_threshold, logprob_threshold,
# no_speech_threshold). We reuse these rather than inventing new numbers,
# since they are already tuned by the Whisper authors for this exact purpose.
_LOGPROB_LOW_CONFIDENCE_THRESHOLD = -1.0
_NO_SPEECH_PROB_THRESHOLD = 0.6

# Short filler phrases Whisper is known to hallucinate on faint/ambiguous
# audio that narrowly survives the energy gate above (e.g. quiet room tone,
# breathing, a single click). This is an ASR-only pattern-matching heuristic
# derived from observed Whisper decoding artifacts -- it is NOT a measure of
# clinical reliability, and it never discards or rewrites real transcript
# text. It only sets a flag downstream systems may use.
_HALLUCINATION_FILLER_PHRASES = {
    "thank you",
    "thanks for watching",
    "thanks for watching!",
    "please subscribe",
    "subscribe",
    "bye",
    "bye bye",
    "you",
    "okay",
    "ok",
}

# Conservative set of languages this deployment is prepared to handle.
# English/Hindi are the primary targets; the remainder are other Indian
# scheduled languages Whisper itself supports, included so that speech in
# those languages is not mislabeled "unsupported" just because it isn't
# English or Hindi. This is intentionally NOT an exhaustive Whisper language
# list -- it exists only to flag the conservative, clear-cut case of a
# detected language wildly outside this project's expected population.
_SUPPORTED_LANGUAGES = {
    "en", "hi", "bn", "gu", "kn", "ml", "mr", "ne", "or", "pa", "sa", "sd",
    "ta", "te", "ur", "as",
}

_DEVANAGARI_RE = re.compile(r"[ऀ-ॿ]")
_LATIN_LETTER_RE = re.compile(r"[A-Za-z]")


class WhisperSTT:
    """
    Thin wrapper around openai-whisper for single-utterance (Tap-to-Speak)
    transcription. The model is loaded once in __init__ and reused for every
    transcribe() call.
    """

    def __init__(self, model_name="turbo"):
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
                "code_mixed": bool,               # see _looks_code_mixed()
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
            }
        """
        waveform = audio if isinstance(audio, np.ndarray) else whisper.load_audio(audio)

        if self._is_effectively_silent(waveform):
            return self._empty_result(no_speech=True)

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
            return self._empty_result(no_speech=True)

        metrics = self._aggregate_metrics(segments)
        language = result.get("language")
        language_confidence = self._detect_language_confidence(waveform, language)

        reliability = {
            "no_speech": False,
            "low_confidence": self._is_low_confidence(metrics),
            "possible_hallucination": self._looks_like_hallucination(text),
            "unsupported_language": bool(text) and language not in _SUPPORTED_LANGUAGES,
        }

        return {
            "text": text,
            "language": language,
            "language_confidence": language_confidence,
            "code_mixed": self._looks_code_mixed(text),
            "segments": segments,
            "asr_reliability": reliability,
            "asr_metrics": metrics,
        }

    # -- internal helpers -----------------------------------------------

    def _is_effectively_silent(self, waveform):
        if waveform.size == 0:
            return True
        rms = float(np.sqrt(np.mean(np.square(waveform))))
        return rms < _SILENCE_RMS_THRESHOLD

    def _empty_result(self, no_speech):
        return {
            "text": "",
            "language": None,
            "language_confidence": None,
            "code_mixed": False,
            "segments": [],
            "asr_reliability": {
                "no_speech": no_speech,
                "low_confidence": False,
                "possible_hallucination": False,
                "unsupported_language": False,
            },
            "asr_metrics": {
                "avg_no_speech_prob": None,
                "avg_logprob": None,
                "avg_compression_ratio": None,
            },
        }

    def _aggregate_metrics(self, segments):
        if not segments:
            return {
                "avg_no_speech_prob": None,
                "avg_logprob": None,
                "avg_compression_ratio": None,
            }
        return {
            "avg_no_speech_prob": float(np.mean([s.get("no_speech_prob", 0.0) for s in segments])),
            "avg_logprob": float(np.mean([s.get("avg_logprob", 0.0) for s in segments])),
            "avg_compression_ratio": float(np.mean([s.get("compression_ratio", 0.0) for s in segments])),
        }

    def _is_low_confidence(self, metrics):
        no_speech_prob = metrics["avg_no_speech_prob"]
        avg_logprob = metrics["avg_logprob"]
        if avg_logprob is not None and avg_logprob < _LOGPROB_LOW_CONFIDENCE_THRESHOLD:
            return True
        if no_speech_prob is not None and no_speech_prob > _NO_SPEECH_PROB_THRESHOLD:
            return True
        return False

    def _looks_like_hallucination(self, text):
        normalized = text.strip().lower().rstrip(".!")
        return normalized in _HALLUCINATION_FILLER_PHRASES

    def _looks_code_mixed(self, text):
        """
        Conservative, descriptive heuristic only: flags a transcript as
        code-mixed when it contains BOTH Devanagari and Latin-alphabet
        characters (e.g. Hindi grammar with an English word typed in Latin
        script).

        Known limitation (documented per project requirements): this will
        NOT catch romanized Hindi written entirely in Latin script, nor
        Hindi/English loanwords phonetically transliterated INTO Devanagari
        (e.g. "chest pain" written as the Devanagari "chest pen" -- Whisper
        commonly outputs this for Hinglish speech). Those cases are
        single-script and indistinguishable from "pure" text by this
        heuristic alone. This never modifies the transcript and never feeds
        clinical interpretation -- it is descriptive metadata only.
        """
        return bool(_DEVANAGARI_RE.search(text)) and bool(_LATIN_LETTER_RE.search(text))

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
    audio_path = sys.argv[1] if len(sys.argv) > 1 else "test3.ogg"
    result = stt.transcribe(audio_path)

    print("Language:", result["language"], "(confidence:", result["language_confidence"], ")")
    print("Text:", result["text"])
    print("Code-mixed (heuristic):", result["code_mixed"])
    print("ASR reliability:", result["asr_reliability"])
    print("ASR metrics:", result["asr_metrics"])
