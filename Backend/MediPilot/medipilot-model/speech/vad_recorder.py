"""
Automatic speech-end detection (VAD) for hands-free Tap-to-Speak.

Continuously monitors short fixed-size audio chunks, detects when speech
begins and ends using Silero VAD, and hands the completed utterance to the
EXISTING speech/whisper_stt.py WhisperSTT for transcription. whisper_stt.py
is not modified by this module.

Two layers, deliberately kept separate:

  - VADSegmenter: pure, no I/O. Consumes fixed-size audio chunks one at a
    time and returns a completed UtteranceResult exactly when an utterance
    just ended (by silence or by hitting the max-duration cap). Fully
    unit-testable without a microphone or an audio device.

  - MicrophoneVADListener: the only class here that touches a real
    microphone (via `sounddevice`). Feeds live audio into a VADSegmenter
    and, for each completed utterance, calls the existing
    speech.whisper_stt.WhisperSTT.transcribe() on the captured samples.

No audio is streamed anywhere over the network at any point, and nothing
in this module talks to Groq or any LLM. Only the finished waveform is
handed to the local WhisperSTT, and only start_listening()'s return value
(text + metadata) ever leaves this module — exactly like the existing
Tap-to-Speak flow, just triggered by silence instead of a button release.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Iterator, Optional

import numpy as np

# Silero VAD only supports 8000/16000 Hz, and at 16000 Hz its models require
# EXACTLY 512-sample chunks per call (256 at 8000 Hz) — this is enforced by
# the model itself, not a stylistic choice. 16000 Hz also matches what
# speech/whisper_stt.py and Whisper itself expect, so no resampling is
# needed anywhere in the pipeline.
SAMPLE_RATE = 16000
VAD_CHUNK_SAMPLES = 512

# "~1-1.5 seconds of continuous silence" ends the utterance.
DEFAULT_MIN_SILENCE_MS = 1300
# "20-30 second maximum recording limit."
DEFAULT_MAX_UTTERANCE_S = 25.0
DEFAULT_VAD_THRESHOLD = 0.5

_vad_model_singleton = None


def _load_default_vad_model():
    """Load the Silero VAD model once and reuse it (same pattern as
    WhisperSTT loading its model once in __init__)."""
    global _vad_model_singleton
    if _vad_model_singleton is None:
        from silero_vad import load_silero_vad

        _vad_model_singleton = load_silero_vad()
    return _vad_model_singleton


def iter_fixed_chunks(waveform: np.ndarray, chunk_size: int = VAD_CHUNK_SAMPLES) -> Iterator[np.ndarray]:
    """Split a waveform into fixed-size chunks, zero-padding the last one.
    Used by tests and by anything replaying a pre-recorded file through the
    same chunk-by-chunk path the live microphone uses."""
    waveform = np.asarray(waveform, dtype=np.float32)
    for start in range(0, len(waveform), chunk_size):
        chunk = waveform[start:start + chunk_size]
        if len(chunk) < chunk_size:
            chunk = np.pad(chunk, (0, chunk_size - len(chunk)))
        yield chunk


@dataclass
class UtteranceResult:
    """One completed utterance capture, before transcription."""

    audio: np.ndarray       # float32 mono waveform @ SAMPLE_RATE
    end_reason: str          # "silence" | "max_duration"
    duration_s: float


class VADSegmenter:
    """
    Pure speech segmentation. Feed it fixed-size (VAD_CHUNK_SAMPLES) mono
    float32 chunks one at a time via process_chunk(); it returns an
    UtteranceResult exactly on the chunk where an utterance completes,
    and None otherwise. No microphone, no file I/O, no model beyond the
    Silero VAD model itself.

    Short in-speech pauses are handled by Silero's own VADIterator
    (min_silence_duration_ms only fires "end" after that much CONTINUOUS
    sub-threshold audio; speech resuming beforehand resets the countdown),
    so brief pauses inside an utterance do not end it early.
    """

    def __init__(
        self,
        vad_model=None,
        sample_rate: int = SAMPLE_RATE,
        min_silence_ms: int = DEFAULT_MIN_SILENCE_MS,
        max_utterance_s: float = DEFAULT_MAX_UTTERANCE_S,
        threshold: float = DEFAULT_VAD_THRESHOLD,
    ):
        from silero_vad import VADIterator

        model = vad_model or _load_default_vad_model()
        self.sample_rate = sample_rate
        self.max_utterance_samples = int(max_utterance_s * sample_rate)
        self._iterator = VADIterator(
            model,
            threshold=threshold,
            sampling_rate=sample_rate,
            min_silence_duration_ms=min_silence_ms,
        )
        self._buffer: list = []
        self._recording = False

    def reset(self) -> None:
        self._iterator.reset_states()
        self._buffer = []
        self._recording = False

    def process_chunk(self, chunk: np.ndarray) -> Optional[UtteranceResult]:
        if len(chunk) != VAD_CHUNK_SAMPLES:
            raise ValueError(f"chunk must be exactly {VAD_CHUNK_SAMPLES} samples, got {len(chunk)}")

        event = self._iterator(chunk, return_seconds=False)
        starting_now = event is not None and "start" in event and not self._recording

        if starting_now:
            self._recording = True
            self._buffer = []

        if self._recording:
            self._buffer.append(np.asarray(chunk, dtype=np.float32))

            if self._total_samples() >= self.max_utterance_samples:
                return self._finish("max_duration")

            if event is not None and "end" in event:
                return self._finish("silence")

        return None

    def _total_samples(self) -> int:
        return sum(len(c) for c in self._buffer)

    def _finish(self, reason: str) -> UtteranceResult:
        audio = np.concatenate(self._buffer) if self._buffer else np.array([], dtype=np.float32)
        result = UtteranceResult(audio=audio, end_reason=reason, duration_s=len(audio) / self.sample_rate)
        self._iterator.reset_states()
        self._buffer = []
        self._recording = False
        return result


@dataclass
class VADTranscriptResult:
    """What start_listening() hands back: the finished transcript plus the
    same ASR metadata WhisperSTT already produces, plus a little VAD
    bookkeeping. This never includes anything Groq/LLM-related — this
    module stops at the transcript, exactly like the existing Tap-to-Speak
    flow feeding intake/speech_adapter.py."""

    text: str
    language: Optional[str]
    asr_reliability: Optional[dict]
    audio: np.ndarray
    end_reason: str
    duration_s: float


class MicrophoneVADListener:
    """
    The only class in this module that touches a real microphone. Wraps a
    VADSegmenter and the EXISTING, unmodified WhisperSTT.

    Usage (mirrors the existing Tap-to-Speak call shape, just without a
    button):
        listener = MicrophoneVADListener()
        result = listener.start_listening()   # blocks until one utterance
        print(result.text)
    """

    def __init__(self, stt=None, segmenter: Optional[VADSegmenter] = None,
                 sample_rate: int = SAMPLE_RATE, device=None):
        self._stt = stt  # lazy-loaded WhisperSTT; injectable for testing
        self.segmenter = segmenter or VADSegmenter(sample_rate=sample_rate)
        self.sample_rate = sample_rate
        self.device = device

    def _ensure_stt(self):
        if self._stt is None:
            from speech.whisper_stt import WhisperSTT  # existing module, unmodified

            self._stt = WhisperSTT()
        return self._stt

    def _transcribe(self, utterance: UtteranceResult) -> VADTranscriptResult:
        stt = self._ensure_stt()
        asr_result = stt.transcribe(utterance.audio)  # same call shape Tap-to-Speak already uses
        return VADTranscriptResult(
            text=asr_result["text"],
            language=asr_result.get("language"),
            asr_reliability=asr_result.get("asr_reliability"),
            audio=utterance.audio,
            end_reason=utterance.end_reason,
            duration_s=utterance.duration_s,
        )

    def start_listening(self, on_utterance: Optional[Callable[[VADTranscriptResult], None]] = None) -> VADTranscriptResult:
        """
        Continuously listens on the microphone (no button) and blocks until
        one complete utterance has been captured and transcribed, then
        returns it. If `on_utterance` is given it is also called with the
        result before returning — a later caller (e.g. a frontend event
        loop) can pass a callback and keep calling start_listening() again
        for the next utterance, which is what makes this "hands-free"
        rather than single-shot.
        """
        import sounddevice as sd

        self.segmenter.reset()
        holder: dict = {}

        def callback(indata, frames, time_info, status):
            chunk = indata[:, 0].astype(np.float32)
            utterance = self.segmenter.process_chunk(chunk)
            if utterance is not None:
                holder["result"] = self._transcribe(utterance)
                raise sd.CallbackStop

        with sd.InputStream(
            samplerate=self.sample_rate,
            channels=1,
            dtype="float32",
            blocksize=VAD_CHUNK_SAMPLES,
            device=self.device,
            callback=callback,
        ):
            while "result" not in holder:
                sd.sleep(50)

        result = holder["result"]
        if on_utterance:
            on_utterance(result)
        return result


def start_listening(**kwargs) -> VADTranscriptResult:
    """Module-level convenience wrapper: `speech.vad_recorder.start_listening()`.
    Equivalent to `MicrophoneVADListener().start_listening()`. Frontend code
    can call this directly instead of managing a MicrophoneVADListener."""
    return MicrophoneVADListener().start_listening(**kwargs)
