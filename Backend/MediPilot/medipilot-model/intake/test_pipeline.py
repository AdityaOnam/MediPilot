"""
Tests for the Stage 2 intake subsystem (M03-M09 interfaces).

Uses RuleBasedStructurer (deterministic, offline) everywhere except where a
test specifically targets malformed/failed LLM output — no network access
or GROQ_API_KEY is required to run this file. See groq_live_check.py for a
separate, manually-run script that exercises the real Groq API when
GROQ_API_KEY is present.
"""

import json
from dataclasses import fields

import pytest

from intake.llm_structurer import (
    GroqLLMStructurer,
    LLMStructurer,
    RuleBasedStructurer,
    StructurerOutputError,
    validate_structured_narrative,
)
from intake.models import (
    AgeInfo,
    AgeSource,
    AgeStatus,
    AgeStratum,
    ConsentState,
    IntakeRecord,
    ReliabilitySignals,
    StructuredNarrative,
    TriState,
)
from intake.pipeline import IntakePipeline
from intake.red_flags import evaluate_red_flags
from intake.reliability import set_stoic_presentation_flag
from intake.speech_adapter import SpeechAdapter
from intake.state_machine import IntakeState


def _known_adult() -> AgeInfo:
    return AgeInfo(value_days=30 * 365, source=AgeSource.PATIENT, status=AgeStatus.KNOWN)


def _known_geriatric() -> AgeInfo:
    return AgeInfo(value_days=70 * 365, source=AgeSource.PATIENT, status=AgeStatus.KNOWN)


def _consent_granted_adult_pipeline(structurer=None, speech_adapter=None) -> IntakePipeline:
    pipeline = IntakePipeline("T-adult", structurer or RuleBasedStructurer(), speech_adapter)
    pipeline.answer_text("no")   # not assisted
    pipeline.answer_text("no")   # doesn't want a person
    pipeline.answer_text("yes")  # grants consent
    pipeline.record_age(_known_adult())
    return pipeline


# ---------------------------------------------------------------------------
# 1. Human assistance
# ---------------------------------------------------------------------------

def test_human_assistance_request_stops_clinical_questions():
    pipeline = IntakePipeline("T-01", RuleBasedStructurer())
    pipeline.answer_text("yes")  # someone is with them
    pipeline.answer_text("yes")  # but they want a person

    assert pipeline.session.state == IntakeState.HUMAN_ASSISTANCE_REQUESTED
    assert pipeline.session.human_assistance_requested is True
    assert pipeline.complete
    assert pipeline.tree_session is None  # clinical question tree never started

    outcome = pipeline.finalize()
    assert outcome.record.human_assistance_requested is True
    assert outcome.record.narrative is None
    assert outcome.red_flag.red_flag is False


# ---------------------------------------------------------------------------
# 2. Consent declined
# ---------------------------------------------------------------------------

def test_consent_declined_continues_without_penalty():
    pipeline = IntakePipeline("T-02", RuleBasedStructurer())
    pipeline.answer_text("no")   # not assisted
    pipeline.answer_text("no")   # doesn't want a person
    pipeline.answer_text("no")   # declines medical-information consent

    assert pipeline.session.medical_information_consent == ConsentState.DECLINED
    assert pipeline.session.state == IntakeState.AGE_CONTEXT  # NOT stopped

    pipeline.record_age(_known_adult())
    node_ids = [n.node_id for n in pipeline.tree_session.plan]
    assert "medications" not in node_ids
    assert "relevant_history" not in node_ids
    assert "chief_complaint" in node_ids  # presenting complaint still collected

    # Deliberately branch-neutral: this test is about consent handling, not
    # complaint-specific branching (see test_question_tree_branching.py).
    pipeline.answer_text("feeling generally unwell")
    pipeline.answer_text("since morning")
    pipeline.answer_text("5")
    pipeline.answer_text("no")  # pregnancy_status
    pipeline.answer_text("no")  # analgesia_given

    assert pipeline.complete
    outcome = pipeline.finalize()
    assert outcome.record.medical_information_consent == ConsentState.DECLINED
    # Declining consent must never itself surface as a red flag / risk factor.
    assert outcome.red_flag.red_flag is False
    record_field_names = {f.name for f in fields(IntakeRecord)}
    assert "consent_penalty" not in record_field_names
    assert "risk" not in record_field_names


# ---------------------------------------------------------------------------
# 3. Unknown age
# ---------------------------------------------------------------------------

def test_unknown_age_never_assumes_adult():
    pipeline = IntakePipeline("T-03", RuleBasedStructurer())
    pipeline.answer_text("no")
    pipeline.answer_text("no")
    pipeline.answer_text("yes")
    pipeline.record_age(AgeInfo())  # no value, no source, no appearance hint at all

    resolution = pipeline._age_resolution
    assert resolution.status == AgeStatus.UNKNOWN
    assert resolution.stratum is None
    assert set(resolution.plausible_strata) == set(AgeStratum)  # widest-safety: every stratum plausible
    assert resolution.confidence < 0.5

    # Widest-safety fallback question plan must NOT be the adult branch.
    node_ids = [n.node_id for n in pipeline.tree_session.plan]
    assert "pregnancy_status" not in node_ids  # adult/adolescent-only node
    assert "feeding_normally" in node_ids      # paediatric (widest-safety) branch

    assert pipeline.session.age.status == AgeStatus.UNKNOWN


# ---------------------------------------------------------------------------
# 4. Hindi / English / Hinglish transcript extraction
# ---------------------------------------------------------------------------

def test_english_transcript_extraction():
    structurer = RuleBasedStructurer()
    result = structurer.structure(
        "I am having chest pain and I am sweating as well.", {"field_hint": "chief_complaint"}
    )
    assert "chest_pain" in result.symptoms
    assert "sweating" in result.symptoms
    assert result.raw_transcript == "I am having chest pain and I am sweating as well."


def test_hinglish_transcript_extraction_is_not_translated():
    structurer = RuleBasedStructurer()
    text = "mujhe chest mein pain ho raha hai aur paseena bhi aa raha hai"
    result = structurer.structure(text, {"field_hint": "chief_complaint"})
    assert "chest_pain" in result.symptoms
    assert "sweating" in result.symptoms
    assert result.raw_transcript == text  # faithful, not translated/normalized
    assert result.chief_complaint == text


def test_hindi_transcript_extraction():
    structurer = RuleBasedStructurer()
    text = "mujhe kal se bukhar hai aur sharir mein bahut kamzori lag rahi hai"
    result = structurer.structure(text, {"field_hint": "chief_complaint"})
    assert "fever" in result.symptoms
    assert "weakness_general" in result.symptoms

    # Symptom-code extraction is hint-independent; onset is only parsed when
    # the turn is actually answering the onset question (matches real usage
    # in question_tree.py, where each turn is scoped to the question asked).
    onset_result = structurer.structure(text, {"field_hint": "onset"})
    assert onset_result.onset_minutes == 24 * 60  # "kal se" = since yesterday


# ---------------------------------------------------------------------------
# 5. Malformed LLM output handled safely
# ---------------------------------------------------------------------------

class _AlwaysMalformedStructurer(LLMStructurer):
    def structure(self, transcript, context=None):
        raise StructurerOutputError("simulated malformed structurer output")


def test_validate_structured_narrative_rejects_forbidden_and_out_of_range():
    with pytest.raises(StructurerOutputError):
        validate_structured_narrative({"diagnosis": "MI", "chief_complaint": "chest pain"}, "x")
    with pytest.raises(StructurerOutputError):
        validate_structured_narrative({"self_reported_severity": 15}, "x")
    with pytest.raises(StructurerOutputError):
        validate_structured_narrative("not a dict at all", "x")


def test_malformed_llm_response_does_not_crash_pipeline_or_fabricate():
    pipeline = _consent_granted_adult_pipeline(structurer=_AlwaysMalformedStructurer())
    pipeline.answer_text("some chief complaint text")  # structurer raises -> caught internally

    assert pipeline.tree_session.skipped_nodes[0]["node_id"] == "chief_complaint"
    # The patient's own words are preserved verbatim even when the structurer
    # fails outright -- this is NOT fabrication (nothing was invented), only
    # EXTRACTION (symptoms, onset, etc.) is skipped, which is checked below.
    assert pipeline.tree_session.narrative.chief_complaint == "some chief complaint text"
    assert pipeline.tree_session.narrative.symptoms == []  # extraction genuinely unavailable, not fabricated
    assert pipeline.tree_session.narrative.onset_minutes is None
    assert pipeline.tree_session.current_node.node_id == "onset"  # conversation still advances


def test_groq_structurer_fails_cleanly_without_credentials(monkeypatch):
    """No network call, no real API key needed: confirms GroqLLMStructurer
    raises a typed StructurerOutputError (not a raw SDK exception) when
    GROQ_API_KEY is absent, matching the "explicit failure, never silent
    fabrication" contract the whole interface relies on."""
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    structurer = GroqLLMStructurer()
    with pytest.raises(StructurerOutputError, match="GROQ_API_KEY"):
        structurer.structure("I have chest pain")


def test_groq_structurer_uses_expected_default_model():
    # 2026-08-28: eval/run_structurer_bakeoff.py on eval/structurer_cases.json
    # (40 cases) showed 120b at F1 0.962 / 0 missed red flags / 0 schema
    # failures vs 20b at 0.816 / 4 / 4 -- see intake/llm_structurer.py.
    assert GroqLLMStructurer.DEFAULT_MODEL == "openai/gpt-oss-120b"
    assert GroqLLMStructurer().model == "openai/gpt-oss-120b"


def test_groq_structurer_with_injected_client_parses_valid_json_schema_response():
    """Exercises the real request/response wiring (model name, response_format
    shape, response parsing, validate_structured_narrative call) with a stub
    client standing in for the network call — no API key needed."""

    class _StubMessage:
        content = json.dumps({
            "chief_complaint": "chest pain",
            "onset_minutes": 30,
            "self_reported_severity": 7,
            "symptoms": ["chest_pain", "sweating"],
            "medications": [],
            "pregnancy_status": None,
            "relevant_history": [],
        })

    class _StubChoice:
        message = _StubMessage()

    class _StubResponse:
        choices = [_StubChoice()]

    class _StubCompletions:
        def create(self, **kwargs):
            assert kwargs["model"] == "openai/gpt-oss-120b"
            assert kwargs["response_format"]["type"] == "json_schema"
            assert kwargs["response_format"]["json_schema"]["strict"] is True
            return _StubResponse()

    class _StubChat:
        completions = _StubCompletions()

    class _StubGroqClient:
        chat = _StubChat()

    structurer = GroqLLMStructurer(client=_StubGroqClient())
    result = structurer.structure("I have chest pain and sweating since 30 minutes")
    assert result.chief_complaint == "chest pain"
    assert "chest_pain" in result.symptoms
    assert result.self_reported_severity == 7


# ---------------------------------------------------------------------------
# 6 & 7. Red-flag pass reachable from structured observations
# ---------------------------------------------------------------------------

def test_active_labour_reaches_red_flag():
    structurer = RuleBasedStructurer()
    narrative = structurer.structure(
        "I am in labour, the contractions are close together", {"field_hint": "chief_complaint"}
    )
    result = evaluate_red_flags(narrative)
    assert result.red_flag is True
    assert result.rule_id == "RF-02"


def test_altered_consciousness_reaches_red_flag():
    structurer = RuleBasedStructurer()
    narrative = structurer.structure("she is not responding to me at all", {"field_hint": "chief_complaint"})
    result = evaluate_red_flags(narrative)
    assert result.red_flag is True
    assert result.rule_id == "RF-01"


def test_question_tree_and_structurer_never_emit_band_fields():
    narrative_field_names = {f.name for f in fields(StructuredNarrative)}
    assert not (narrative_field_names & {"band", "red_flag", "acuity", "diagnosis", "triage"})
    # Only the dedicated M07 result type carries a red-flag verdict.
    result_field_names = {f.name for f in fields(evaluate_red_flags(StructuredNarrative()).__class__)}
    assert "red_flag" in result_field_names  # this is the ONE place it belongs


# ---------------------------------------------------------------------------
# 8. Stoic presentation flag: clinician-set only
# ---------------------------------------------------------------------------

def test_stoic_presentation_is_clinician_set_only():
    signals = ReliabilitySignals()
    assert signals.stoic_presentation is False
    set_stoic_presentation_flag(signals, True)
    assert signals.stoic_presentation is True

    # Nothing in the automatic pipeline flow sets it on its own.
    pipeline = _consent_granted_adult_pipeline()
    pipeline.answer_text("I have no pain at all")
    pipeline.answer_text("since morning")
    pipeline.answer_text("0")
    pipeline.answer_text("no")
    pipeline.answer_text("no")
    outcome = pipeline.finalize()
    assert outcome.record.reliability_signals.stoic_presentation is False


# ---------------------------------------------------------------------------
# 9. Communication barrier
# ---------------------------------------------------------------------------

class _UnsupportedLanguageSTT:
    def transcribe(self, audio):
        return {
            "text": "patient speaks a language the ASR does not support",
            "language": "xx",
            "asr_reliability": {
                "no_speech": False,
                "low_confidence": False,
                "possible_hallucination": False,
                "unsupported_language": True,
            },
        }


def test_communication_barrier_surfaces_from_unsupported_language():
    adapter = SpeechAdapter(stt=_UnsupportedLanguageSTT())
    pipeline = _consent_granted_adult_pipeline(speech_adapter=adapter)

    pipeline.answer_voice("fake-audio-handle")  # chief_complaint, via voice
    assert pipeline.tree_session.reliability_signals.communication_barrier == TriState.TRUE

    pipeline.answer_text("since morning")
    pipeline.answer_text("5")
    pipeline.answer_text("no")
    pipeline.answer_text("no")
    outcome = pipeline.finalize()
    assert outcome.record.reliability_signals.communication_barrier == TriState.TRUE
    assert outcome.record.communication_barrier == TriState.TRUE


def test_answer_voice_transcript_records_voice_interaction_mode_and_metadata():
    """answer_voice_transcript() (used by voice_conversation.py, which gets
    its transcript from speech/vad_recorder.py's MicrophoneVADListener
    rather than raw audio) must behave like answer_voice() for downstream
    purposes: interaction_mode="voice", and asr_reliability/language carried
    through so communication_barrier detection still works."""
    pipeline = _consent_granted_adult_pipeline()

    pipeline.answer_voice_transcript(
        text="patient speaks a language the ASR does not support",
        language="xx",
        asr_reliability={
            "no_speech": False,
            "low_confidence": False,
            "possible_hallucination": False,
            "unsupported_language": True,
        },
    )
    assert pipeline.tree_session.reliability_signals.communication_barrier == TriState.TRUE

    # interaction_mode/language on IntakeRecord reflect only the LAST turn
    # (pre-existing behavior, same as answer_voice()) -- check them right
    # after the voice turn, before any subsequent text turns overwrite them.
    assert pipeline._last_utterance.interaction_mode == "voice"
    assert pipeline._last_utterance.language == "xx"

    pipeline.answer_text("since morning")
    pipeline.answer_text("5")
    pipeline.answer_text("no")
    pipeline.answer_text("no")
    outcome = pipeline.finalize()

    assert outcome.record.communication_barrier == TriState.TRUE
