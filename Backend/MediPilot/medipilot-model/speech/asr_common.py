"""
Shared ASR heuristics and the common transcription result contract.

Extracted from speech/whisper_stt.py so that a hosted-ASR backend
(speech/groq_asr.py) and the local Whisper backend produce byte-identical
result shapes and apply byte-identical reliability heuristics. The two must
not drift: the intake layer (intake/speech_adapter.py) reads
`asr_reliability` without knowing or caring which backend produced it, and
the §16 ASR bake-off compares backends on exactly these fields.

Nothing here performs clinical interpretation. Every flag below is an
ASR-observable property of the audio or the decoded text -- never a
statement about the patient. Clinical reliability weighting is M09
(intake/reliability.py) and is a separate concept entirely.

This module imports nothing beyond numpy, so it is importable on a server
that has no `whisper`, no `torch`, and no ffmpeg.
"""

from __future__ import annotations

import re
from typing import Optional

import numpy as np

# --- Silence handling -------------------------------------------------------
#
# Whisper (including "turbo") hallucinates short filler phrases such as
# "Thank you." on silent/near-silent audio, and its own no_speech_prob is NOT
# reliable for catching this: empirically (see speech/test_whisper.py) literal
# digital silence produced no_speech_prob ~= 0 while still emitting "Thank
# you." with high confidence. Hosted ASR APIs exhibit the same failure, and
# there the cost is also a wasted network round trip, so the gate runs before
# the request is sent.
#
# Threshold calibration (measured on available fixtures):
#   - digital silence:                 RMS ~= 0.0
#   - near-silence background noise:   RMS ~= 0.0005
#   - real recorded speech (3 fixtures): RMS ~= 0.12 - 0.14
# 0.01 sits ~20x above the near-silence fixture and ~10x below real speech.
SILENCE_RMS_THRESHOLD = 0.01

# Whisper's own published default decoding-failure thresholds (see
# whisper/transcribe.py). We reuse these rather than inventing new numbers,
# since they are already tuned by the Whisper authors for this exact purpose.
LOGPROB_LOW_CONFIDENCE_THRESHOLD = -1.0
NO_SPEECH_PROB_THRESHOLD = 0.6

# Short filler phrases Whisper is known to hallucinate on faint/ambiguous
# audio that narrowly survives the energy gate above. This is an ASR-only
# pattern match derived from observed decoding artifacts -- it is NOT a
# measure of clinical reliability, and it never discards or rewrites real
# transcript text. It only sets a flag downstream systems may use.
HALLUCINATION_FILLER_PHRASES = {
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
# scheduled languages Whisper supports, included so that speech in those
# languages is not mislabeled "unsupported" merely for not being English or
# Hindi. Intentionally NOT an exhaustive Whisper language list -- it exists
# only to flag the clear-cut case of a detected language wildly outside this
# project's expected population.
SUPPORTED_LANGUAGES = {
    "en", "hi", "bn", "gu", "kn", "ml", "mr", "ne", "or", "pa", "sa", "sd",
    "ta", "te", "ur", "as",
}

# Groq/OpenAI's hosted Whisper endpoint returns `language` as a full English
# name in its verbose_json response ("English", "Hindi"), unlike local
# openai-whisper and faster-whisper, which both return an ISO 639-1 code
# ("en", "hi") directly. SUPPORTED_LANGUAGES above and every reliability
# check in this module compare against the CODE, so a hosted response that
# is not normalized first makes `unsupported_language` True for every
# correctly transcribed utterance -- discovered exactly this way, via the
# ASR bake-off (eval/kaggle/asr_bakeoff.ipynb) reporting
# language_accuracy: 0.0 for the Groq backends despite 0.0 WER.
#
# Whisper's full published language list (99 languages), lower-cased name
# to ISO 639-1 code.
_WHISPER_LANGUAGE_NAME_TO_CODE = {
    "english": "en", "chinese": "zh", "german": "de", "spanish": "es",
    "russian": "ru", "korean": "ko", "french": "fr", "japanese": "ja",
    "portuguese": "pt", "turkish": "tr", "polish": "pl", "catalan": "ca",
    "dutch": "nl", "arabic": "ar", "swedish": "sv", "italian": "it",
    "indonesian": "id", "hindi": "hi", "finnish": "fi", "vietnamese": "vi",
    "hebrew": "he", "ukrainian": "uk", "greek": "el", "malay": "ms",
    "czech": "cs", "romanian": "ro", "danish": "da", "hungarian": "hu",
    "tamil": "ta", "norwegian": "no", "thai": "th", "urdu": "ur",
    "croatian": "hr", "bulgarian": "bg", "lithuanian": "lt", "latin": "la",
    "maori": "mi", "malayalam": "ml", "welsh": "cy", "slovak": "sk",
    "telugu": "te", "persian": "fa", "latvian": "lv", "bengali": "bn",
    "serbian": "sr", "azerbaijani": "az", "slovenian": "sl", "kannada": "kn",
    "estonian": "et", "macedonian": "mk", "breton": "br", "basque": "eu",
    "icelandic": "is", "armenian": "hy", "nepali": "ne", "mongolian": "mn",
    "bosnian": "bs", "kazakh": "kk", "albanian": "sq", "swahili": "sw",
    "galician": "gl", "marathi": "mr", "punjabi": "pa", "sinhala": "si",
    "khmer": "km", "shona": "sn", "yoruba": "yo", "somali": "so",
    "afrikaans": "af", "occitan": "oc", "georgian": "ka", "belarusian": "be",
    "tajik": "tg", "sindhi": "sd", "gujarati": "gu", "amharic": "am",
    "yiddish": "yi", "lao": "lo", "uzbek": "uz", "faroese": "fo",
    "haitian creole": "ht", "pashto": "ps", "turkmen": "tk", "nynorsk": "nn",
    "maltese": "mt", "sanskrit": "sa", "luxembourgish": "lb", "myanmar": "my",
    "tibetan": "bo", "tagalog": "tl", "malagasy": "mg", "assamese": "as",
    "tatar": "tt", "hawaiian": "haw", "lingala": "ln", "hausa": "ha",
    "bashkir": "ba", "javanese": "jw", "sundanese": "su", "cantonese": "yue",
}
_WHISPER_LANGUAGE_CODES = set(_WHISPER_LANGUAGE_NAME_TO_CODE.values())


def normalize_language_name(language: Optional[str]) -> Optional[str]:
    """
    Map a Whisper-family language identifier to its ISO 639-1 code.

    Idempotent: a value that is already a recognised code passes through
    unchanged, so this is safe to call on every backend's output regardless
    of which convention it already uses. An unrecognised value is
    lower-cased and returned as-is rather than raised, so an unexpected API
    response degrades to "flagged as unsupported" instead of crashing the
    transcription -- the same fail-open-to-a-flag posture as the rest of
    this module's reliability heuristics.
    """
    if not language:
        return language
    lowered = language.strip().lower()
    if lowered in _WHISPER_LANGUAGE_CODES:
        return lowered
    return _WHISPER_LANGUAGE_NAME_TO_CODE.get(lowered, lowered)


_DEVANAGARI_RE = re.compile(r"[ऀ-ॿ]")
_LATIN_LETTER_RE = re.compile(r"[A-Za-z]")


def is_effectively_silent(waveform: np.ndarray) -> bool:
    """True when the waveform carries no meaningful signal, measured by RMS
    against SILENCE_RMS_THRESHOLD. Callers gate on this BEFORE decoding."""
    if waveform is None or waveform.size == 0:
        return True
    rms = float(np.sqrt(np.mean(np.square(waveform))))
    return rms < SILENCE_RMS_THRESHOLD


def looks_like_hallucination(text: str) -> bool:
    normalized = (text or "").strip().lower().rstrip(".!")
    return normalized in HALLUCINATION_FILLER_PHRASES


def looks_code_mixed(text: str) -> bool:
    """
    Conservative, descriptive heuristic only: flags a transcript as
    code-mixed when it contains BOTH Devanagari and Latin-alphabet
    characters (e.g. Hindi grammar with an English word in Latin script).

    Known limitation (documented per project requirements): this will NOT
    catch romanized Hindi written entirely in Latin script, nor Hindi/English
    loanwords phonetically transliterated INTO Devanagari (e.g. "chest pain"
    written in Devanagari -- Whisper commonly outputs this for Hinglish
    speech). Those cases are single-script and indistinguishable from "pure"
    text by this heuristic alone. This never modifies the transcript and
    never feeds clinical interpretation -- it is descriptive metadata only.
    """
    text = text or ""
    return bool(_DEVANAGARI_RE.search(text)) and bool(_LATIN_LETTER_RE.search(text))


def is_unsupported_language(text: str, language: Optional[str]) -> bool:
    return bool(text) and language not in SUPPORTED_LANGUAGES


def is_low_confidence(metrics: dict) -> bool:
    """
    Applies Whisper's own decoding-failure thresholds to aggregated segment
    metrics. A hosted backend that returns no logprobs passes None for both
    and is reported as not-low-confidence -- absence of evidence is recorded
    as such by `metrics_available` on the result, never faked as a number.
    """
    avg_logprob = metrics.get("avg_logprob")
    no_speech_prob = metrics.get("avg_no_speech_prob")
    if avg_logprob is not None and avg_logprob < LOGPROB_LOW_CONFIDENCE_THRESHOLD:
        return True
    if no_speech_prob is not None and no_speech_prob > NO_SPEECH_PROB_THRESHOLD:
        return True
    return False


def aggregate_metrics(segments: list) -> dict:
    """Mean of the per-segment decoding metadata Whisper exposes. Returns
    None for every field when no segments carry it (hosted APIs commonly
    omit logprobs), which is what keeps `metrics_available` honest."""
    empty = {"avg_no_speech_prob": None, "avg_logprob": None, "avg_compression_ratio": None}
    if not segments:
        return empty

    def _mean(key):
        vals = [s[key] for s in segments if isinstance(s, dict) and s.get(key) is not None]
        return float(np.mean(vals)) if vals else None

    return {
        "avg_no_speech_prob": _mean("no_speech_prob"),
        "avg_logprob": _mean("avg_logprob"),
        "avg_compression_ratio": _mean("compression_ratio"),
    }


def empty_result(no_speech: bool = True, backend: str = "unknown") -> dict:
    """The result returned when the energy gate fires and no decode happens."""
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
        "backend": backend,
        "metrics_available": False,
    }


def build_result(
    text: str,
    language: Optional[str],
    segments: list,
    backend: str,
    language_confidence: Optional[float] = None,
) -> dict:
    """
    Assemble the common ASR result contract from a decoded transcript.
    Every backend routes through this so the reliability heuristics are
    applied identically regardless of where decoding happened.
    """
    text = (text or "").strip()
    metrics = aggregate_metrics(segments)
    metrics_available = any(v is not None for v in metrics.values())

    return {
        "text": text,
        "language": language,
        "language_confidence": language_confidence,
        "code_mixed": looks_code_mixed(text),
        "segments": segments,
        "asr_reliability": {
            "no_speech": not text,
            "low_confidence": is_low_confidence(metrics),
            "possible_hallucination": looks_like_hallucination(text),
            "unsupported_language": is_unsupported_language(text, language),
        },
        "asr_metrics": metrics,
        "backend": backend,
        "metrics_available": metrics_available,
    }
