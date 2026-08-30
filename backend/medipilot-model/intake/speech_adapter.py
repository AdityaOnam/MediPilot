"""
M05 — Speech & multilingual adapter.

Speech is the default interaction mode; typed text is a complete fallback,
not a placeholder. This module wraps the existing speech/whisper_stt.py
(WhisperSTT) behind a small interface so the intake flow never depends on
Whisper directly, and never has to run without it either.

No medical decision logic lives here — only speech-to-text plumbing and the
same faithful-transcript guarantees whisper_stt.py already provides
(no translation, no clinical interpretation, no forced language).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass
class Utterance:
    """One turn of patient/attendant input, regardless of modality."""

    text: str
    interaction_mode: str  # "voice" | "text"
    language: Optional[str] = None
    asr_reliability: Optional[dict] = None  # only populated for voice turns


class TypedInputAdapter:
    """Typed fallback. Always available; never requires speech infrastructure."""

    def read(self, text: str) -> Utterance:
        return Utterance(text=text, interaction_mode="text", language=None, asr_reliability=None)


class SpeechAdapter:
    """
    Voice input path. The Whisper model is loaded lazily on first use so
    that a text-only intake session never needs ffmpeg/whisper installed.
    """

    def __init__(self, stt=None):
        self._stt = stt  # allows tests to inject a mock/stub WhisperSTT

    def _ensure_stt(self):
        if self._stt is None:
            from speech.whisper_stt import WhisperSTT  # local import: keep speech optional

            self._stt = WhisperSTT()
        return self._stt

    def listen(self, audio) -> Utterance:
        """
        Transcribe one completed audio utterance (a Tap-to-Speak recording).
        `audio` is whatever speech.whisper_stt.WhisperSTT.transcribe accepts
        (file path or waveform).
        """
        stt = self._ensure_stt()
        result = stt.transcribe(audio)
        return Utterance(
            text=result["text"],
            interaction_mode="voice",
            language=result.get("language"),
            asr_reliability=result.get("asr_reliability"),
        )
