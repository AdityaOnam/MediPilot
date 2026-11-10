"""
Tests for speech/vad_recorder.py.

VADSegmenter tests use the REAL Silero VAD model (bundled locally with the
`silero-vad` package -- no network needed) fed synthetic chunk sequences
built from the existing real speech/silence fixtures, so segmentation is
tested against actual recorded speech, not sine tones.

MicrophoneVADListener itself is NOT exercised here -- it requires a real
microphone. See speech/mic_check.py for a manual, real-microphone check.
"""

import os

import numpy as np
import pytest
import whisper

from speech.vad_recorder import (
    DEFAULT_MIN_SILENCE_MS,
    SAMPLE_RATE,
    VAD_CHUNK_SAMPLES,
    VADSegmenter,
    iter_fixed_chunks,
)

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _load(filename: str) -> np.ndarray:
    return whisper.load_audio(os.path.join(REPO_ROOT, filename)).astype(np.float32)


def _silence(seconds: float) -> np.ndarray:
    return np.zeros(int(seconds * SAMPLE_RATE), dtype=np.float32)


@pytest.fixture(scope="module")
def vad_model():
    from silero_vad import load_silero_vad

    return load_silero_vad()


def _run(segmenter: VADSegmenter, waveform: np.ndarray) -> list:
    """Feed a full waveform through the segmenter chunk by chunk, collecting
    every UtteranceResult produced (there may be zero, one, or more)."""
    results = []
    for chunk in iter_fixed_chunks(waveform):
        result = segmenter.process_chunk(chunk)
        if result is not None:
            results.append(result)
    return results


# ---------------------------------------------------------------------------
# 1. Speech followed by silence
# ---------------------------------------------------------------------------

def test_speech_followed_by_silence_produces_one_utterance(vad_model):
    speech = _load("test2.ogg")  # clean English speech, ~5.9s
    waveform = np.concatenate([speech, _silence(2.0)])
    segmenter = VADSegmenter(vad_model=vad_model)

    results = _run(segmenter, waveform)

    assert len(results) == 1
    assert results[0].end_reason == "silence"
    assert len(results[0].audio) > 0
    # Most of the spoken content was captured (VAD legitimately trims a
    # trailing low-energy tail within the recording itself, so this is not
    # exactly the full nominal clip length)...
    assert results[0].duration_s > 0.9 * (len(speech) / SAMPLE_RATE)
    # ...but the appended silence was NOT captured in full (proves the
    # recording actually stopped on its own rather than just running until
    # the input ran out).
    assert results[0].duration_s < len(waveform) / SAMPLE_RATE


# ---------------------------------------------------------------------------
# 2. Pure silence
# ---------------------------------------------------------------------------

def test_pure_silence_produces_no_utterance(vad_model):
    waveform = _silence(4.0)
    segmenter = VADSegmenter(vad_model=vad_model)

    results = _run(segmenter, waveform)

    assert results == []


# ---------------------------------------------------------------------------
# 3. Short pauses inside speech
# ---------------------------------------------------------------------------

def test_short_pause_inside_speech_does_not_split_the_utterance(vad_model):
    # test.ogg is spliced (not concatenated end-to-end) so the inserted gap
    # sits INSIDE a stretch that is confidently speech on both sides,
    # rather than at the file's own softer lead-in/trail-off edges -- a
    # real trailing low-energy region at a clip boundary would otherwise
    # combine with the inserted gap and exceed the silence threshold on its
    # own, which is a property of the recording, not of segmentation logic.
    speech = _load("test.ogg")  # ~7.25s continuous Hindi speech
    splice_at = 95 * VAD_CHUNK_SAMPLES  # chunk 95 sits inside a long confidently-speech run
    short_gap = _silence(0.4)  # well under the ~1.3s end-of-utterance threshold
    waveform = np.concatenate([speech[:splice_at], short_gap, speech[splice_at:], _silence(2.0)])
    segmenter = VADSegmenter(vad_model=vad_model)

    results = _run(segmenter, waveform)

    # Exactly one utterance: the short internal gap must not end it early.
    assert len(results) == 1
    assert results[0].end_reason == "silence"
    # Spans substantially more than either half alone would (rules out a
    # false split, where the first piece alone would be ~3s).
    assert results[0].duration_s > 5.0
    assert results[0].duration_s < len(waveform) / SAMPLE_RATE


# ---------------------------------------------------------------------------
# 4. Maximum recording duration
# ---------------------------------------------------------------------------

def test_max_duration_cuts_off_continuous_speech(vad_model):
    speech = _load("test.ogg")  # ~7.2s of continuous Hindi speech, no long internal pause
    assert len(speech) / SAMPLE_RATE > 3.0  # comfortably longer than the test cap below

    cap_s = 2.0
    segmenter = VADSegmenter(vad_model=vad_model, max_utterance_s=cap_s, min_silence_ms=DEFAULT_MIN_SILENCE_MS)

    results = _run(segmenter, speech)

    assert len(results) >= 1
    first = results[0]
    assert first.end_reason == "max_duration"
    # Cut off at (approximately) the cap -- at most one chunk of overshoot.
    assert cap_s <= first.duration_s <= cap_s + (VAD_CHUNK_SAMPLES / SAMPLE_RATE) + 1e-6


# ---------------------------------------------------------------------------
# Chunking helper + input validation
# ---------------------------------------------------------------------------

def test_iter_fixed_chunks_pads_the_last_chunk():
    waveform = np.ones(VAD_CHUNK_SAMPLES + 10, dtype=np.float32)
    chunks = list(iter_fixed_chunks(waveform))
    assert len(chunks) == 2
    assert all(len(c) == VAD_CHUNK_SAMPLES for c in chunks)
    assert chunks[1][10:].sum() == 0  # zero-padded tail


def test_process_chunk_rejects_wrong_size(vad_model):
    segmenter = VADSegmenter(vad_model=vad_model)
    with pytest.raises(ValueError):
        segmenter.process_chunk(np.zeros(100, dtype=np.float32))


# ---------------------------------------------------------------------------
# End-to-end: VAD-segmented audio still transcribes correctly through the
# EXISTING, unmodified WhisperSTT (proves the new module doesn't corrupt or
# mis-trim audio in a way that would break English/Hindi/Hinglish handling).
# ---------------------------------------------------------------------------

def test_vad_segmented_audio_still_transcribes_correctly(vad_model):
    from speech.whisper_stt import WhisperSTT

    speech = _load("test2.ogg")  # "I am having chest pain and I am sweating as well."
    waveform = np.concatenate([speech, _silence(2.0)])
    segmenter = VADSegmenter(vad_model=vad_model)

    results = _run(segmenter, waveform)
    assert len(results) == 1

    stt = WhisperSTT()
    transcription = stt.transcribe(results[0].audio)
    assert transcription["language"] == "en"
    assert "chest" in transcription["text"].lower()
    assert transcription["asr_reliability"]["no_speech"] is False
