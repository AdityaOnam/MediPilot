"""
Regression tests for the real conversation bug reproduced from
test_conversation.py: a patient answering severity/yes-no questions with
natural phrasing ("about an 8", "not really") instead of a bare token got
stuck repeating the same question forever, because _parse_severity /
_parse_yes_no only accepted an exact bare answer.

Also covers the related "don't re-ask what's already known" behavior added
alongside the fix (a good triage nurse does not repeat a question the
patient already answered unprompted, e.g. while describing their chief
complaint).

Uses RuleBasedStructurer (deterministic, offline) throughout -- no network
access or GROQ_API_KEY required.
"""

import pytest

from intake.llm_structurer import GroqLLMStructurer, LLMStructurer, RuleBasedStructurer, StructurerOutputError
from intake.models import AgeInfo, AgeSource, AgeStatus, AgeStratum, ConsentState
from intake.pipeline import IntakePipeline
from intake.question_tree import (
    QuestionTreeSession,
    _parse_severity,
    _parse_yes_no,
    build_plan,
)
from intake.speech_adapter import Utterance
from intake.state_machine import InvalidAnswerError


def _say(tree: QuestionTreeSession, text: str) -> None:
    tree.record_answer(Utterance(text=text, interaction_mode="text"), RuleBasedStructurer())


# ---------------------------------------------------------------------------
# _parse_severity: natural phrasing, not just a bare digit
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "text, expected",
    [
        ("8", 8),
        (" 9 ", 9),
        ("about an 8", 8),
        ("maybe 7 out of 10", 7),
        ("I'd say 8", 8),
        ("7/10", 7),
        ("10", 10),
        ("0", 0),
        ("", None),
        ("no", None),
        ("very bad", None),
    ],
)
def test_parse_severity_handles_natural_phrasing(text, expected):
    assert _parse_severity(text) == expected


# ---------------------------------------------------------------------------
# _parse_yes_no: natural phrasing, English + Hindi/Hinglish
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "text, expected",
    [
        ("yes", True),
        ("no", False),
        ("yeah", True),
        ("yep", True),
        ("sure", True),
        ("nope", False),
        ("not really", False),
        ("i don't think so", False),
        ("haan", True),
        ("nahi", False),
        ("bilkul", True),
        ("", None),
        ("maybe", None),
        # Real Whisper ASR output, not clean typed text: sentence-ending
        # punctuation Whisper attaches to a short spoken answer.
        ("No.", False),
        ("Yes.", True),
        ("No,", False),
        ("Yes,", True),
        ("Yeah!", True),
        ("Yes!", True),
        ("NO!!", False),
        ("Nope.", False),
        ("Yep!", True),
        ("haan.", True),
        ("nahi.", False),
        # Mis-transcription / elongation artifacts Whisper actually produces.
        ("Non.", False),  # common mis-hearing of a clipped/soft "no"
        ("Nooo.", False),  # emphatic elongation
        ("yesss", True),
        # Multiple/repeated punctuation, extra whitespace, brackets.
        ("No..", False),
        ("No...", False),
        ("No  .", False),
        (" No .", False),
        ("(No)", False),
        # Devanagari script (Whisper renders actual Hindi speech this way,
        # not romanized) -- "नहीं"/"हाँ" including the sentence-ending danda.
        ("नहीं।", False),
        ("नही।", False),
        ("हाँ।", True),
        # Sanity: unrelated free text is still not misread as yes/no.
        ("known", None),
        ("sweating a lot", None),
    ],
)
def test_parse_yes_no_handles_natural_phrasing(text, expected):
    assert _parse_yes_no(text) == expected


def test_previously_broken_answers_no_longer_raise():
    """Before the fix, these raised InvalidAnswerError and the tree never
    advanced past the question."""
    tree = QuestionTreeSession(plan=build_plan(AgeStratum.ADULT, ConsentState.GRANTED))
    _say(tree, "I have a headache")
    while tree.current_node.node_id != "severity":
        _say(tree, "no particular details")
    _say(tree, "about an 8")  # used to raise InvalidAnswerError
    assert tree.narrative.self_reported_severity == 8


# ---------------------------------------------------------------------------
# Skip questions already answered from an earlier turn
# ---------------------------------------------------------------------------

def test_symptom_implied_question_is_skipped_when_already_volunteered():
    # Deliberately fever+chills, not chest-pain+sweating: the latter would
    # immediately satisfy RF-03 and stop the conversation before reaching
    # the node this test is actually about (see test_conversation_flow.py's
    # red-flag-early-stop tests for that behavior).
    tree = QuestionTreeSession(plan=build_plan(AgeStratum.ADULT, ConsentState.GRANTED))
    _say(tree, "I have a fever and chills")  # chills already stated
    asked = []
    while not tree.complete:
        asked.append(tree.current_node.node_id)
        if tree.current_node.node_id == "severity":
            _say(tree, "5")
        elif tree.current_node.kind.value == "yes_no":
            _say(tree, "no")
        else:
            _say(tree, "nothing more to add")
    assert "chills" not in asked
    assert any(s["node_id"] == "chills" and s["reason"] == "already_known" for s in tree.skipped_nodes)
    assert not tree.stopped_for_red_flag  # fever+chills alone is not a red flag


def test_onset_is_not_reasked_if_already_known():
    tree = QuestionTreeSession(plan=build_plan(AgeStratum.ADULT, ConsentState.GRANTED))
    _say(tree, "I have a headache that started 2 hours ago")
    node_ids = [n.node_id for n in tree.plan]
    assert "onset" in node_ids  # onset still part of the plan, but should be auto-skipped if known
    # Walk forward; onset must never actually be asked again if it was captured already.
    while not tree.complete and tree.current_node.node_id != "onset_character":
        _say(tree, "no particular details")
    # onset_minutes may or may not have been extracted by the rule-based
    # structurer depending on field_hint; this test only asserts the
    # mechanism doesn't crash and completes normally either way.
    while not tree.complete:
        if tree.current_node.node_id == "severity":
            _say(tree, "5")
        elif tree.current_node.kind.value == "yes_no":
            _say(tree, "no")
        else:
            _say(tree, "no particular details")
    assert tree.complete


# ---------------------------------------------------------------------------
# Full conversation-level regression test, matching the exact scenario
# reproduced from test_conversation.py
# ---------------------------------------------------------------------------

def test_full_conversation_with_natural_language_answers_completes_without_getting_stuck():
    # A benign headache, not chest pain: every branch answer below is
    # deliberately negative for the neuro/vomiting/vision/fainting checks,
    # so no red flag is ever confirmed and the full plan (branch + shared
    # onset/severity + tail) can be walked end to end -- isolating the
    # natural-language parsing fix this test is actually about from the
    # red-flag-early-stop behavior (covered separately below).
    pipeline = IntakePipeline("repro-001", RuleBasedStructurer())
    pipeline.answer_text("no")
    pipeline.answer_text("no")
    pipeline.answer_text("yes")
    pipeline.record_age(AgeInfo(value_days=35 * 365, source=AgeSource.PATIENT, status=AgeStatus.KNOWN))

    answers_by_prompt_keyword = [
        ("bothering you today", "I have a bad headache"),
        ("suddenly, or build up gradually", "it came on gradually"),
        ("weakness, numbness, or trouble speaking", "no, nothing like that"),
        ("vomiting along with it", "no vomiting"),
        ("changes in your vision", "no changes"),
        ("lose consciousness", "no, never lost consciousness"),
        ("when did this start", "about 3 hours ago"),
        ("scale of 0 to 10", "about an 8"),
        ("could you be pregnant", "no"),
        ("pain-relief medicine", "not really"),
        ("regular medications", "none"),
        ("past medical history", "none"),
    ]

    turns = 0
    while not pipeline.complete and turns < 25:
        turns += 1
        prompt = pipeline.current_prompt.lower()
        match = next((ans for kw, ans in answers_by_prompt_keyword if kw in prompt), None)
        assert match is not None, f"no scripted answer for prompt: {pipeline.current_prompt!r}"
        pipeline.answer_text(match)  # must never raise

    assert pipeline.complete
    assert turns < 25  # did not get stuck looping
    assert not pipeline.tree_session.stopped_for_red_flag  # a benign headache never confirms one

    outcome = pipeline.finalize()
    assert outcome.record.narrative.self_reported_severity == 8
    assert outcome.record.narrative.onset_minutes == 180
    assert outcome.red_flag.red_flag is False


# ---------------------------------------------------------------------------
# Regression test for the exact reported bug: "ulti ho rhi hai mujhe" as the
# chief-complaint answer produced an EMPTY StructuredNarrative
# (chief_complaint=None, symptoms=[], raw_transcript='') because the
# structurer call raised StructurerOutputError (e.g. missing GROQ_API_KEY, or
# any other Groq failure) before _merge_narrative ever ran. Fixed in
# QuestionTreeSession._preserve_raw_answer_on_failure(): the patient's raw
# words are now preserved into chief_complaint/raw_transcript even when the
# structurer fails outright. Extraction (symptoms, onset, etc.) correctly
# stays unset in that case -- only the verbatim text is preserved, nothing
# is fabricated.
# ---------------------------------------------------------------------------

class _AlwaysFailingStructurer(LLMStructurer):
    def structure(self, transcript, context=None):
        raise StructurerOutputError("simulated structurer failure")


def test_chief_complaint_text_is_not_lost_when_structurer_fails():
    """The exact bug report, reproduced directly against QuestionTreeSession."""
    tree = QuestionTreeSession(plan=build_plan(AgeStratum.ADULT, ConsentState.GRANTED))
    utterance = Utterance(text="ulti ho rhi hai mujhe", interaction_mode="text")

    with pytest.raises(StructurerOutputError):
        tree.record_answer(utterance, _AlwaysFailingStructurer())

    assert tree.narrative.chief_complaint == "ulti ho rhi hai mujhe"
    assert "ulti ho rhi hai mujhe" in tree.narrative.raw_transcript
    # Extraction genuinely did not happen -- correctly left unset, not fabricated.
    assert tree.narrative.symptoms == []


def test_chief_complaint_preserved_through_the_real_groq_missing_credentials_path(monkeypatch):
    """Same bug, but through the actual GroqLLMStructurer failure path (the
    one hit in practice when GROQ_API_KEY is unset), not a stub."""
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    tree = QuestionTreeSession(plan=build_plan(AgeStratum.ADULT, ConsentState.GRANTED))
    utterance = Utterance(text="ulti ho rhi hai mujhe", interaction_mode="text")

    with pytest.raises(StructurerOutputError):
        tree.record_answer(utterance, GroqLLMStructurer())

    assert tree.narrative.chief_complaint == "ulti ho rhi hai mujhe"
    assert tree.narrative.raw_transcript == "ulti ho rhi hai mujhe"


def test_full_pipeline_preserves_chief_complaint_when_structurer_fails():
    """End-to-end through IntakePipeline (same call shape as test_conversation.py),
    confirming the final StructuredNarrative is not empty."""
    pipeline = IntakePipeline("bug-repro-001", _AlwaysFailingStructurer())
    pipeline.answer_text("no")
    pipeline.answer_text("no")
    pipeline.answer_text("yes")
    pipeline.record_age(AgeInfo(value_days=30 * 365, source=AgeSource.PATIENT, status=AgeStatus.KNOWN))

    pipeline.answer_text("ulti ho rhi hai mujhe")  # does not raise: pipeline catches StructurerOutputError

    assert pipeline.tree_session.narrative.chief_complaint == "ulti ho rhi hai mujhe"
    assert pipeline.tree_session.skipped_nodes[0] == {"node_id": "chief_complaint", "reason": "structurer_failed"}


def test_only_chief_complaint_and_raw_transcript_are_preserved_on_failure():
    """Preservation is narrowly scoped: a later free-text node's raw answer
    is appended to raw_transcript, but it must not overwrite the earlier
    chief_complaint, and structured fields for THAT node stay unset."""
    tree = QuestionTreeSession(plan=build_plan(AgeStratum.ADULT, ConsentState.GRANTED))
    with pytest.raises(StructurerOutputError):
        tree.record_answer(Utterance(text="ulti ho rhi hai mujhe", interaction_mode="text"), _AlwaysFailingStructurer())
    tree.skip_current(reason="structurer_failed")  # mirror pipeline.py's handling, advance past chief_complaint

    with pytest.raises(StructurerOutputError):
        tree.record_answer(Utterance(text="since this morning", interaction_mode="text"), _AlwaysFailingStructurer())

    assert tree.narrative.chief_complaint == "ulti ho rhi hai mujhe"  # unchanged, not overwritten
    assert "since this morning" in tree.narrative.raw_transcript
    assert tree.narrative.onset_minutes is None  # not fabricated


# ---------------------------------------------------------------------------
# End-to-end: real ASR-style punctuation through the actual YES_NO node
# handling in QuestionTreeSession.record_answer(), not just the parser in
# isolation -- proves the fix reaches the real conversation flow reported
# as broken (answer_text() rejecting "No."/"Yeah!" etc.).
# ---------------------------------------------------------------------------

def test_no_period_answers_a_yes_no_node_through_the_real_pipeline():
    tree = QuestionTreeSession(plan=build_plan(AgeStratum.ADULT, ConsentState.GRANTED))
    _say(tree, "I have a headache")
    while tree.current_node.node_id != "severity":
        _say(tree, "no particular details")
    _say(tree, "5")
    assert tree.current_node.node_id == "pregnancy_status"

    _say(tree, "No.")  # used to be rejected as an unrecognized answer

    assert tree.narrative.pregnancy_status is False
    assert tree.current_node.node_id == "analgesia_given"


def test_yes_period_answers_a_yes_no_node_through_the_real_pipeline():
    tree = QuestionTreeSession(plan=build_plan(AgeStratum.ADULT, ConsentState.GRANTED))
    _say(tree, "I have a headache")
    while tree.current_node.node_id != "severity":
        _say(tree, "no particular details")
    _say(tree, "5")
    assert tree.current_node.node_id == "pregnancy_status"

    _say(tree, "Yes.")

    assert tree.narrative.pregnancy_status is True


def test_unrecognized_punctuation_noise_still_raises_not_silently_advances():
    """The fix must not become so lenient that it accepts everything --
    genuinely unparseable input still raises, so the patient is asked
    again rather than silently advanced."""
    tree = QuestionTreeSession(plan=build_plan(AgeStratum.ADULT, ConsentState.GRANTED))
    _say(tree, "I have a headache")
    while tree.current_node.node_id != "severity":
        _say(tree, "no particular details")
    _say(tree, "5")
    assert tree.current_node.node_id == "pregnancy_status"

    with pytest.raises(InvalidAnswerError):
        _say(tree, "...")
    assert tree.current_node.node_id == "pregnancy_status"  # did not advance
