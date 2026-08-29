"""
Tests for speech/whisper_stt.py (ASR layer only).

Uses the real audio fixtures in speech/ (test.ogg, test2.ogg,
test3.ogg) plus two synthetic fixtures generated locally for the silence
regression test (speech/test_silence.wav, speech/test_near_silence.wav --
digital silence and low-amplitude noise, created with ffmpeg's anullsrc/
anoisesrc; not patient data, not committed audio of a real recording).

NOTE ON COVERAGE: the three real fixtures happen to cover English, Hindi,
and a Hindi/English code-mixed (Hinglish) clinical utterance, so those are
empirically evaluated below. There is no noisy/low-confidence or
Indian-accented-English fixture available, so that case is NOT evaluated
here -- see the final report for what is configuration-only vs. tested.

Model is loaded ONCE at module scope and reused across all tests.
"""

import os
import sys

import pytest

from speech.whisper_stt import WhisperSTT  # noqa: E402

FIXTURES = os.path.dirname(os.path.abspath(__file__))

TEST_EN = os.path.join(FIXTURES, "test2.ogg")   # "I am having chest pain and I am sweating as well."
TEST_HI = os.path.join(FIXTURES, "test.ogg")    # Hindi: "yeh bas testing ke liye hai"
TEST_HINGLISH = os.path.join(FIXTURES, "test3.ogg")  # Hindi grammar + English loanwords (chest/pain)
TEST_SILENCE = os.path.join(FIXTURES, "test_silence.wav")
TEST_NEAR_SILENCE = os.path.join(FIXTURES, "test_near_silence.wav")


@pytest.fixture(scope="module")
def stt():
    return WhisperSTT()


def _assert_schema(result):
    assert set(result.keys()) == {
        "text", "language", "language_confidence", "code_mixed",
        "segments", "asr_reliability", "asr_metrics",
        # Added when the result contract moved into speech/asr_common.py so
        # the hosted (Groq) and local backends emit the same shape: which
        # engine ran, and whether it returned per-segment logprobs at all.
        "backend", "metrics_available",
    }
    assert isinstance(result["text"], str)
    assert isinstance(result["segments"], list)
    reliability = result["asr_reliability"]
    for key in ("no_speech", "low_confidence", "possible_hallucination", "unsupported_language"):
        assert isinstance(reliability[key], bool), key
    metrics = result["asr_metrics"]
    for key in ("avg_no_speech_prob", "avg_logprob", "avg_compression_ratio"):
        assert key in metrics


def test_english_utterance(stt):
    result = stt.transcribe(TEST_EN)
    _assert_schema(result)
    assert result["language"] == "en"
    assert "chest" in result["text"].lower()
    assert "pain" in result["text"].lower()
    assert result["asr_reliability"]["no_speech"] is False
    # This is a clean, clearly-articulated recording -- must not be flagged
    # as a hallucination or as unsupported-language.
    assert result["asr_reliability"]["possible_hallucination"] is False
    assert result["asr_reliability"]["unsupported_language"] is False


def test_hindi_utterance(stt):
    result = stt.transcribe(TEST_HI)
    _assert_schema(result)
    assert result["language"] == "hi"
    assert len(result["text"]) > 0
    assert result["asr_reliability"]["no_speech"] is False
    assert result["asr_reliability"]["unsupported_language"] is False
    # Must NOT be auto-translated to English.
    assert "testing" not in result["text"].lower() or any(
        "ऀ" <= ch <= "ॿ" for ch in result["text"]
    )


def test_hinglish_utterance_is_preserved_not_translated(stt):
    result = stt.transcribe(TEST_HINGLISH)
    _assert_schema(result)
    # Whisper detects this as Hindi (transliterated loanwords in Devanagari);
    # the important property is that the text is NOT translated into plain
    # English and is NOT clinically interpreted.
    assert result["language"] in ("hi", "en")
    assert len(result["text"]) > 0
    assert "acute chest pain" not in result["text"].lower()
    assert result["asr_reliability"]["no_speech"] is False


def test_code_mixed_flag_is_conservative_and_documented(stt):
    # Documents the known limitation described in whisper_stt.py:
    # test3.ogg IS code-mixed speech (Hindi grammar, English medical loanwords)
    # but Whisper renders it entirely in Devanagari script, so the
    # Devanagari+Latin heuristic does NOT detect it. This test pins that
    # documented limitation so it isn't silently "fixed" into a false claim.
    result = stt.transcribe(TEST_HINGLISH)
    assert result["code_mixed"] is False


def test_silence_does_not_hallucinate(stt):
    """Regression test for the 'thank you' hallucination bug."""
    result = stt.transcribe(TEST_SILENCE)
    _assert_schema(result)
    assert result["text"] == ""
    assert result["asr_reliability"]["no_speech"] is True
    assert "thank you" not in result["text"].lower()


def test_near_silence_does_not_hallucinate(stt):
    result = stt.transcribe(TEST_NEAR_SILENCE)
    _assert_schema(result)
    assert result["text"] == ""
    assert result["asr_reliability"]["no_speech"] is True


def test_short_utterance_is_not_treated_as_silence(stt):
    # test.ogg / test2.ogg / test3.ogg are all short (~5-7s) real utterances;
    # confirm none of them are misclassified as no_speech by the energy gate.
    for path in (TEST_EN, TEST_HI, TEST_HINGLISH):
        result = stt.transcribe(path)
        assert result["asr_reliability"]["no_speech"] is False
        assert result["text"] != ""


def test_model_loaded_once_and_reused(stt, monkeypatch):
    import whisper as whisper_module

    calls = {"n": 0}
    original_load_model = whisper_module.load_model

    def counting_load_model(*args, **kwargs):
        calls["n"] += 1
        return original_load_model(*args, **kwargs)

    monkeypatch.setattr(whisper_module, "load_model", counting_load_model)

    stt.transcribe(TEST_EN)
    stt.transcribe(TEST_HI)

    assert calls["n"] == 0  # no reload triggered by transcribe() calls
    assert stt.model is not None


def test_output_schema_on_real_and_silent_audio(stt):
    for path in (TEST_EN, TEST_SILENCE):
        _assert_schema(stt.transcribe(path))
