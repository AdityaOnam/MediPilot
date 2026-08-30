"""
Regression tests for three exact reported scenarios:

1. Human assistance: saying yes to "Would you prefer a person?" must be
   acknowledged (not a silent termination), and no clinical questions
   follow.
2. Stop when a red flag is already established: once the structured
   observations already satisfy an EXISTING red_flags.py rule, the intake
   must stop asking generic follow-ups (onset, severity, pregnancy,
   medications, ...) rather than grinding through the rest of the plan.
   red_flags.py itself is not modified -- this only calls its existing
   evaluate_red_flags().
3. Injury information lost: safety-critical answers in the injury branch
   (e.g. "is there bleeding?") must reliably land in narrative.symptoms
   using the EXISTING ObservationCode vocabulary, including natural
   English/Hindi/Hinglish phrasing, so the EXISTING red-flag rule can see
   them -- no new code or rule is invented.

Uses RuleBasedStructurer (deterministic, offline) throughout -- no network
access or GROQ_API_KEY required.
"""

import pytest

from intake.llm_structurer import LLMStructurer, RuleBasedStructurer, StructurerOutputError
from intake.models import AgeInfo, AgeSource, AgeStatus
from intake.pipeline import IntakePipeline
from intake.question_tree import QuestionTreeSession, build_plan
from intake.models import AgeStratum, ConsentState
from intake.red_flags import evaluate_red_flags
from intake.speech_adapter import Utterance
from intake.state_machine import IntakeState


def _say(tree: QuestionTreeSession, text: str) -> None:
    tree.record_answer(Utterance(text=text, interaction_mode="text"), RuleBasedStructurer())


# ---------------------------------------------------------------------------
# 1. Human assistance is acknowledged, not silent
# ---------------------------------------------------------------------------

def test_human_assistance_yes_is_acknowledged_not_silent():
    pipeline = IntakePipeline("handoff-001", RuleBasedStructurer())
    pipeline.answer_text("yes")  # someone is with them
    pipeline.answer_text("yes")  # they want a person

    assert pipeline.session.state == IntakeState.HUMAN_ASSISTANCE_REQUESTED
    assert pipeline.complete
    # The whole point of the bug report: this must NOT be None.
    assert pipeline.current_prompt is not None
    assert "help" in pipeline.current_prompt.lower()
    assert pipeline.tree_session is None  # no clinical questions ever started


def test_human_assistance_prevents_any_clinical_question_from_being_asked():
    pipeline = IntakePipeline("handoff-002", RuleBasedStructurer())
    pipeline.answer_text("no")
    pipeline.answer_text("yes")  # wants a person, before consent/age/clinical questions

    assert pipeline.complete
    outcome = pipeline.finalize()
    assert outcome.record.narrative is None
    assert outcome.record.human_assistance_requested is True


# ---------------------------------------------------------------------------
# 2. Stop when a red flag is already established: exact reported scenario
#    "I am having labour pain -> 42 weeks -> contractions too often ->
#    water broken -> severity 10"
# ---------------------------------------------------------------------------

def test_labour_scenario_stops_once_red_flag_confirmed_not_after_full_checklist():
    pipeline = IntakePipeline("labour-001", RuleBasedStructurer())
    pipeline.answer_text("no")
    pipeline.answer_text("no")
    pipeline.answer_text("yes")
    pipeline.record_age(AgeInfo(value_days=28 * 365, source=AgeSource.PATIENT, status=AgeStatus.KNOWN))

    assert pipeline.current_prompt == "What is bothering you today?"
    pipeline.answer_text("I am having labour pain")

    # active_labour is already unambiguous from the opening statement alone
    # (RuleBasedStructurer's own ACTIVE_LABOUR keyword "labour" matches) --
    # red_flags.py's existing RF-02 fires immediately, so the intake stops
    # here rather than continuing to ask gestational age, contraction
    # pattern, fluid leakage, onset, severity, pregnancy status, medications,
    # etc. This is the correct, MORE aggressive application of "stop once
    # confirmed" than the reported conversation walked through by hand.
    assert pipeline.complete
    assert pipeline.tree_session.stopped_for_red_flag

    outcome = pipeline.finalize()
    assert "active_labour" in outcome.record.narrative.symptoms
    assert outcome.red_flag.red_flag is True
    assert outcome.red_flag.rule_id == "RF-02"
    # Generic follow-ups were never reached.
    assert outcome.record.narrative.self_reported_severity is None
    assert outcome.record.narrative.pregnancy_status is None


def test_red_flag_stop_also_applies_mid_branch_not_only_at_chief_complaint():
    """Same mechanism, demonstrated with the code appearing on a LATER turn
    (not the opening statement), using Hindi that the category keywords
    recognize but that RuleBasedStructurer's own ACTIVE_LABOUR keyword list
    does not -- so the branch is entered normally and walks a couple of
    questions before the confirming answer arrives."""
    pipeline = IntakePipeline("labour-002", RuleBasedStructurer())
    pipeline.answer_text("no")
    pipeline.answer_text("no")
    pipeline.answer_text("yes")
    pipeline.record_age(AgeInfo(value_days=28 * 365, source=AgeSource.PATIENT, status=AgeStatus.KNOWN))

    pipeline.answer_text("mujhe prasav dard ho raha hai")  # routes to pregnancy_labour, no code yet
    assert pipeline.current_prompt == "How many weeks pregnant are you, if known?"
    pipeline.answer_text("42 weeks")
    assert pipeline.current_prompt == "How often are the contractions coming?"
    pipeline.answer_text("they are coming very often, contractions every few minutes")  # -> active_labour

    assert pipeline.complete
    assert pipeline.tree_session.stopped_for_red_flag
    outcome = pipeline.finalize()
    assert outcome.red_flag.red_flag is True
    assert outcome.red_flag.rule_id == "RF-02"
    # fluid_leakage and everything after it were never asked.
    assert outcome.record.narrative.self_reported_severity is None


def test_stop_check_never_fires_when_no_red_flag_is_present():
    """Negative control: ordinary answers with no red-flag-relevant code
    never trigger an early stop."""
    tree = QuestionTreeSession(plan=build_plan(AgeStratum.ADULT, ConsentState.GRANTED))
    _say(tree, "I have a mild headache")
    _say(tree, "it came on gradually")
    _say(tree, "no, nothing like that")
    assert not tree.stopped_for_red_flag
    assert not tree.complete


# ---------------------------------------------------------------------------
# 3. Injury information must be represented in the EXISTING structured
#    observations. Exact reported scenario:
#    "accident -> motorcycle fall -> leg injury -> heavy bleeding ->
#    deformity -> cannot move" must not end with symptoms=[] / red_flag=False.
# ---------------------------------------------------------------------------

class _StructurerThatMissesBleedingExtraction(LLMStructurer):
    """Simulates a realistic LLM call that succeeds normally on every turn
    EXCEPT it fails to map the "bleeding" answer to the closed vocabulary
    -- each turn is extracted independently with no conversation memory, so
    missing an informal/typo'd answer on one narrow follow-up is a
    realistic failure mode, not a contrived one."""

    def __init__(self):
        self._rb = RuleBasedStructurer()

    def structure(self, transcript, context=None):
        result = self._rb.structure(transcript, context=context)
        if (context or {}).get("field_hint") == "bleeding":
            result.symptoms = []
        return result


def test_injury_bleeding_scenario_reaches_existing_red_flag_even_when_extraction_misses_it():
    pipeline = IntakePipeline("injury-001", _StructurerThatMissesBleedingExtraction())
    pipeline.answer_text("no")
    pipeline.answer_text("no")
    pipeline.answer_text("yes")
    pipeline.record_age(AgeInfo(value_days=30 * 365, source=AgeSource.PATIENT, status=AgeStatus.KNOWN))

    pipeline.answer_text("accident")
    pipeline.answer_text("motorcycle fall")
    pipeline.answer_text("leg injury")
    assert pipeline.current_prompt == "Is there any bleeding, and is it under control?"
    pipeline.answer_text("yess its bleeding heavily")

    # Stops immediately: UNCONTROLLED_BLEEDING alone satisfies RF-06.
    assert pipeline.complete
    assert pipeline.tree_session.stopped_for_red_flag

    outcome = pipeline.finalize()
    assert "uncontrolled_bleeding" in outcome.record.narrative.symptoms
    assert outcome.red_flag.red_flag is True
    assert outcome.red_flag.rule_id == "RF-06"


@pytest.mark.parametrize(
    "bleeding_answer",
    [
        "yess its bleeding heavily",
        "bahut khoon aa raha hai",
        "haan, bleeding is not stopping",
        "yes, won't stop bleeding",
    ],
)
def test_injury_bleeding_detected_from_natural_english_hindi_hinglish_answers(bleeding_answer):
    tree = QuestionTreeSession(plan=build_plan(AgeStratum.ADULT, ConsentState.GRANTED))
    structurer = _StructurerThatMissesBleedingExtraction()
    tree.record_answer(Utterance(text="accident", interaction_mode="text"), structurer)
    tree.record_answer(Utterance(text="motorcycle fall", interaction_mode="text"), structurer)
    tree.record_answer(Utterance(text="leg injury", interaction_mode="text"), structurer)
    assert tree.current_node.node_id == "bleeding"
    tree.record_answer(Utterance(text=bleeding_answer, interaction_mode="text"), structurer)

    assert "uncontrolled_bleeding" in tree.narrative.symptoms
    assert evaluate_red_flags(tree.narrative).rule_id == "RF-06"


def test_explicit_denial_of_bleeding_does_not_set_the_symptom():
    """The backstop must never override a clear "no" even when the
    extraction also (correctly) found nothing -- no false positive."""
    tree = QuestionTreeSession(plan=build_plan(AgeStratum.ADULT, ConsentState.GRANTED))
    structurer = RuleBasedStructurer()
    _say_via = lambda t: tree.record_answer(Utterance(text=t, interaction_mode="text"), structurer)
    _say_via("accident")
    _say_via("motorcycle fall")
    _say_via("leg injury")
    assert tree.current_node.node_id == "bleeding"
    _say_via("no, not bleeding")

    assert "uncontrolled_bleeding" not in tree.narrative.symptoms
    assert not tree.stopped_for_red_flag


def test_injury_scenario_with_flaky_extraction_does_not_end_with_empty_symptoms_and_false_red_flag():
    """Pins the exact bug report: this combination used to end with
    symptoms=[] and red_flag=False."""
    pipeline = IntakePipeline("injury-002", _StructurerThatMissesBleedingExtraction())
    pipeline.answer_text("no")
    pipeline.answer_text("no")
    pipeline.answer_text("yes")
    pipeline.record_age(AgeInfo(value_days=30 * 365, source=AgeSource.PATIENT, status=AgeStatus.KNOWN))

    for a in ["accident", "motorcycle fall", "leg injury", "yess its bleeding heavily"]:
        if pipeline.current_prompt is None:
            break
        pipeline.answer_text(a)

    outcome = pipeline.finalize()
    assert outcome.record.narrative.symptoms != []
    assert outcome.red_flag.red_flag is not False
