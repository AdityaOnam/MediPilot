"""
Tests for the situation-specific, category-based question-tree branching in
intake/question_tree.py, and for the free-text merge bug fix.

Uses RuleBasedStructurer (deterministic, offline) throughout -- no network
access or GROQ_API_KEY required. The Groq structurer itself is not touched
by this feature and is not re-tested here (see intake/test_pipeline.py).

Some new categories (vomiting, diarrhea, abdominal_pain, choking, seizure,
vaginal_bleeding, burns) have new ObservationCode values that only the real
Groq structurer can extract (RuleBasedStructurer's keyword table lives in
the frozen intake/llm_structurer.py and was not touched, so it cannot
produce these new codes). Those categories are tested via the text-keyword
fallback path instead, which is exercised identically regardless of which
structurer produced the transcript.
"""

import pytest

from intake.llm_structurer import LLMStructurer, RuleBasedStructurer
from intake.models import AgeInfo, AgeSource, AgeStatus, AgeStratum, ConsentState, StructuredNarrative
from intake.pipeline import IntakePipeline
from intake.question_tree import (
    CATEGORIES,
    COMPLAINT_BRANCHES,
    QuestionTreeSession,
    build_plan,
    classify_complaint,
)
from intake.speech_adapter import Utterance


def _say(tree: QuestionTreeSession, text: str, structurer=None) -> None:
    tree.record_answer(Utterance(text=text, interaction_mode="text"), structurer or RuleBasedStructurer())


def _new_tree(stratum=AgeStratum.ADULT, consent=ConsentState.GRANTED) -> QuestionTreeSession:
    return QuestionTreeSession(plan=build_plan(stratum, consent))


def _walk_to_completion(tree: QuestionTreeSession, structurer=None) -> list:
    """Answers every remaining node with a generic filler, returning the
    ordered list of node_ids that were actually asked."""
    structurer = structurer or RuleBasedStructurer()
    asked = []
    while not tree.complete:
        node = tree.current_node
        asked.append(node.node_id)
        if node.node_id == "severity":
            _say(tree, "5", structurer)
        elif node.kind.value == "yes_no":
            _say(tree, "no", structurer)
        else:
            _say(tree, "no particular details", structurer)
    return asked


def _category_first_question(name: str) -> str:
    return COMPLAINT_BRANCHES[name][0].node_id


# ---------------------------------------------------------------------------
# Architecture integrity
# ---------------------------------------------------------------------------

def test_registry_has_no_duplicate_category_names():
    names = [c.name for c in CATEGORIES]
    assert len(names) == len(set(names))


def test_every_category_has_at_least_one_selector_and_one_question():
    for c in CATEGORIES:
        assert c.keywords or c.symptom_codes, f"{c.name} has no way to ever be selected"
        assert len(c.questions) >= 2, f"{c.name} has too few follow-up questions"
        assert len(c.questions) <= 6, f"{c.name} risks over-questioning"


def test_expected_category_set_is_present():
    expected = {
        "chest_pain", "abdominal_pain", "vomiting", "diarrhea", "fever", "cough_cold",
        "sore_throat", "choking", "breathing_difficulty", "headache", "weakness_fatigue",
        "back_neck_pain", "limb_joint_pain", "injury", "burns", "bleeding_wound",
        "rash_allergy", "swelling", "eye_problem", "ear_problem", "dental_pain",
        "urinary", "pregnancy_labour", "vaginal_bleeding", "seizure",
        "sudden_weakness_speech", "poisoning_bite",
    }
    assert expected.issubset({c.name for c in CATEGORIES})


# ---------------------------------------------------------------------------
# Broad test matrix: one representative case per requested category,
# English and Hindi/Hinglish where natural.
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "chief_complaint_text, expected_category",
    [
        ("I have chest pain and sweating", "chest_pain"),
        ("mera dil dhadak raha hai aur chest me dard hai", "chest_pain"),
        ("I have had fever since yesterday", "fever"),
        ("mujhe bukhar hai", "fever"),
        ("I have stomach pain", "abdominal_pain"),
        ("pet mein dard ho raha hai", "abdominal_pain"),
        ("I've been vomiting since this morning", "vomiting"),
        ("mujhe ulti ho rahi hai", "vomiting"),
        ("I have loose motions and feel weak", "diarrhea"),
        ("mujhe dast lag rahe hain", "diarrhea"),
        ("I have a cough and cold", "cough_cold"),
        ("my throat hurts a lot", "sore_throat"),
        ("something is stuck in my throat and I can't swallow", "choking"),
        ("I am having difficulty breathing", "breathing_difficulty"),
        ("I have a terrible headache", "headache"),
        ("I feel dizzy and almost fainted", "headache"),
        ("khujli aur rash ho gaya hai", "rash_allergy"),
        ("I fell down and got injured", "injury"),
        ("I cut my hand and it's bleeding a lot", "bleeding_wound"),
        ("peshab karte waqt jalan hoti hai", "urinary"),
        ("I am pregnant and having contractions", "pregnancy_labour"),
        ("saanp ne kata hai", "poisoning_bite"),
        ("suddenly one side of my body went weak and my speech is slurred", "sudden_weakness_speech"),
    ],
)
def test_classify_complaint_matrix(chief_complaint_text, expected_category):
    structurer = RuleBasedStructurer()
    partial = structurer.structure(chief_complaint_text, context={"field_hint": "chief_complaint"})
    assert classify_complaint(partial) == expected_category


def test_unknown_complaint_falls_back_to_generic():
    tree = _new_tree()
    _say(tree, "I have a strange feeling in my little finger for a week")
    # Generic: goes straight to the shared onset question, no branch inserted.
    assert tree.current_node.node_id == "onset"
    asked = _walk_to_completion(tree)
    known_branch_only_ids = {"pain_location", "vomit_duration", "mechanism", "chills", "neuro_symptoms", "rash_location"}
    assert not (known_branch_only_ids & set(asked))


# ---------------------------------------------------------------------------
# Per-category question-set checks (full walk, right questions asked)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "chief_complaint_text, category_name, must_include, must_exclude",
    [
        # Deliberately does not mention sweating/breathlessness up front, so
        # none of this branch's questions are auto-skipped as already-known
        # (see test_conversation_flow.py for that behavior specifically).
        ("I have chest pain", "chest_pain",
         ["pain_location", "pain_character", "pain_radiation", "breathing_difficulty", "sweating_nausea"],
         ["vomit_duration", "mechanism"]),
        ("I have stomach pain", "abdominal_pain",
         ["pain_location", "vomit_check", "bowel_symptoms", "associated_fever", "urinary_check"],
         ["pain_radiation"]),
        ("I have had fever since yesterday", "fever",
         ["measured_temperature", "chills", "cough_check", "breathing_difficulty"],
         ["pain_location"]),
        ("I've been vomiting", "vomiting",
         ["vomit_duration", "vomit_frequency", "vomit_blood", "fluids_tolerance"],
         ["mechanism"]),
        ("I have loose motions", "diarrhea",
         ["diarrhea_duration", "diarrhea_frequency", "stool_blood", "fluids_tolerance"],
         ["pain_radiation"]),
        ("my throat hurts", "sore_throat",
         ["throat_duration", "swallowing_difficulty"],
         ["pain_location"]),
        ("something is stuck in my throat", "choking",
         ["what_happened", "breathing_now", "able_to_cough"],
         ["pain_location"]),
        ("I fell down and got injured", "injury",
         ["mechanism", "injury_location", "bleeding", "deformity_swelling", "function"],
         ["vomit_duration"]),
        ("I cut my hand and it's bleeding a lot", "bleeding_wound",
         ["wound_cause", "bleeding_control", "wound_size"],
         ["mechanism"]),
        ("khujli aur rash ho gaya hai", "rash_allergy",
         ["rash_location", "rash_onset", "rash_spreading", "itching_or_pain", "swelling_breathing", "recent_exposure"],
         ["pain_location"]),
        ("peshab karte waqt jalan hoti hai", "urinary",
         ["urinary_check", "urinary_frequency", "urine_blood", "flank_pain"],
         ["pain_location"]),
        # "prasav" (Hindi for labour/delivery) matches the category's own
        # keywords but not RuleBasedStructurer's ACTIVE_LABOUR keywords, so
        # the full question set can be walked without an immediate
        # red-flag-confirmed stop (see the dedicated red-flag-early-stop
        # tests below for that behavior, using an English phrase that DOES
        # trip the code).
        ("mujhe prasav dard ho raha hai", "pregnancy_labour",
         ["gestational_age", "contraction_pattern", "fluid_leakage", "fetal_movement"],
         ["mechanism"]),
        ("saanp ne kata hai", "poisoning_bite",
         ["substance_or_creature", "time_since", "symptoms_since"],
         ["pain_location"]),
        ("suddenly my left side went weak and my speech is slurred", "sudden_weakness_speech",
         ["exact_onset_time", "which_side", "speech_check", "face_check"],
         ["pain_location"]),
    ],
)
def test_category_question_sets(chief_complaint_text, category_name, must_include, must_exclude):
    tree = _new_tree()
    _say(tree, chief_complaint_text)
    assert tree.current_node.node_id == _category_first_question(category_name)

    asked = _walk_to_completion(tree)
    for node_id in must_include:
        assert node_id in asked, f"expected {node_id} to be asked for {category_name}, got {asked}"
    for node_id in must_exclude:
        assert node_id not in asked, f"{node_id} should not be asked for {category_name}"
    assert "onset" in asked and "severity" in asked  # shared questions still asked once


# ---------------------------------------------------------------------------
# Age-stratum tail composes correctly with complaint branching
# (child-specific / elderly-specific complaints)
# ---------------------------------------------------------------------------

def test_child_complaint_gets_both_branch_questions_and_paediatric_tail():
    tree = QuestionTreeSession(plan=build_plan(AgeStratum.CHILD, ConsentState.GRANTED))
    _say(tree, "the baby has a fever")
    assert tree.current_node.node_id == "measured_temperature"  # fever branch selected

    # Custom walk, not the shared _walk_to_completion helper: feeding_normally
    # must be answered "yes" here specifically -- answering "no" correctly
    # confirms RF-08 (infant not feeding) via _apply_yes_no, which would
    # correctly stop the intake early (see the red-flag-early-stop tests),
    # cutting off "behaviour" before this test could observe it.
    asked = []
    while not tree.complete:
        node = tree.current_node
        asked.append(node.node_id)
        if node.node_id == "severity":
            _say(tree, "5")
        elif node.node_id == "feeding_normally":
            _say(tree, "yes")
        elif node.kind.value == "yes_no":
            _say(tree, "no")
        else:
            _say(tree, "no particular details")

    assert "chills" in asked and "cough_check" in asked  # fever branch
    assert "feeding_normally" in asked and "behaviour" in asked  # paediatric tail, untouched
    assert not tree.stopped_for_red_flag


def test_elderly_complaint_gets_both_branch_questions_and_geriatric_tail():
    tree = QuestionTreeSession(plan=build_plan(AgeStratum.GERIATRIC, ConsentState.GRANTED))
    _say(tree, "I fell down at home")
    assert tree.current_node.node_id == "mechanism"  # injury branch selected

    asked = _walk_to_completion(tree)
    assert "bleeding" in asked and "function" in asked  # injury branch
    assert "baseline_function" in asked and "falls_or_confusion" in asked  # geriatric tail, untouched


# ---------------------------------------------------------------------------
# Symptom-code-driven routing (not just keyword text), where
# RuleBasedStructurer already recognizes the relevant existing code
# ---------------------------------------------------------------------------

def test_symptom_code_routes_poisoning_bite_via_snakebite_code():
    structurer = RuleBasedStructurer()
    partial = structurer.structure("snake bite on my leg", context={"field_hint": "chief_complaint"})
    assert "snakebite" in partial.symptoms
    assert classify_complaint(partial) == "poisoning_bite"


def test_symptom_code_routes_sudden_weakness_via_facial_droop_code():
    narrative = StructuredNarrative(chief_complaint="something is wrong", symptoms=["facial_droop"])
    assert classify_complaint(narrative) == "sudden_weakness_speech"


def test_symptom_code_takes_priority_over_conflicting_keyword_text():
    # Text mentions "fell" (injury keyword) but the extracted code is
    # chest_pain -- code evidence wins (checked in the first pass).
    narrative = StructuredNarrative(chief_complaint="I fell because of chest pain", symptoms=["chest_pain"])
    assert classify_complaint(narrative) == "chest_pain"


# ---------------------------------------------------------------------------
# Free-text extraction bug fix: info volunteered off-topic still lands in
# the final narrative, regardless of which question prompted it.
# ---------------------------------------------------------------------------

class _RichStructurer(LLMStructurer):
    """Stands in for a real LLM that extracts everything it hears in one
    turn, regardless of which question prompted it."""

    def structure(self, transcript, context=None):
        return StructuredNarrative(
            onset_minutes=45,
            self_reported_severity=8,
            symptoms=["sweating"],
            raw_transcript=transcript,
            extraction_status="ok",
        )


def test_free_text_volunteered_off_topic_still_reaches_the_narrative():
    tree = _new_tree()
    _say(tree, "I have chest pain")
    assert tree.current_node.node_id == "pain_location"

    _say(tree, "left side, started 45 minutes ago, it's about an 8", _RichStructurer())

    assert tree.narrative.onset_minutes == 45
    assert tree.narrative.self_reported_severity == 8
    assert "sweating" in tree.narrative.symptoms


def test_first_write_wins_does_not_clobber_an_already_known_value():
    tree = _new_tree()
    _say(tree, "I have chest pain")  # sets chief_complaint

    class _OverwritingStructurer(LLMStructurer):
        def structure(self, transcript, context=None):
            return StructuredNarrative(chief_complaint="something else entirely", extraction_status="ok")

    _say(tree, "left side", _OverwritingStructurer())
    assert tree.narrative.chief_complaint == "I have chest pain"  # unchanged


# ---------------------------------------------------------------------------
# pipeline.py compatibility: full end-to-end conversations
# ---------------------------------------------------------------------------

def test_full_pipeline_chest_pain_conversation_stops_early_once_red_flag_confirmed():
    """chest_pain + radiating_pain together satisfy RF-03 as soon as the
    radiation answer is given -- the conversation correctly stops there
    rather than continuing to breathing_difficulty/sweating_nausea/onset/
    severity/tail (see the dedicated red-flag-early-stop tests for the
    general mechanism)."""
    pipeline = IntakePipeline("T-branch-01", RuleBasedStructurer())
    pipeline.answer_text("no")
    pipeline.answer_text("no")
    pipeline.answer_text("yes")
    pipeline.record_age(AgeInfo(value_days=40 * 365, source=AgeSource.PATIENT, status=AgeStatus.KNOWN))

    assert pipeline.current_prompt == "What is bothering you today?"
    pipeline.answer_text("I have chest pain")

    assert pipeline.current_prompt == "Where exactly is the pain?"
    pipeline.answer_text("center of my chest")
    pipeline.answer_text("it's crushing")
    pipeline.answer_text("radiates to my left arm")  # RADIATING_PAIN -> chest_pain + radiating_pain = RF-03

    assert pipeline.complete  # stopped immediately; breathing/sweating/onset/severity/tail never asked
    outcome = pipeline.finalize()

    assert "chest_pain" in outcome.record.narrative.symptoms
    assert "radiating_pain" in outcome.record.narrative.symptoms
    assert outcome.red_flag.red_flag is True
    assert outcome.red_flag.rule_id == "RF-03"
    assert pipeline.tree_session.stopped_for_red_flag
    assert pipeline.current_prompt == (
        "Thank you — based on what you've told us, we're moving you straight to the clinical team now."
    )


def test_full_pipeline_chest_pain_conversation_without_a_red_flag_walks_the_whole_plan():
    """Negative control: a chest-pain branch where every follow-up answer
    is explicitly negative never confirms a red flag, so the full branch
    plus the shared tail is walked end to end -- proving build_plan(),
    branch splicing, and pipeline.py compose correctly independent of the
    early-stop behavior."""
    pipeline = IntakePipeline("T-branch-02", RuleBasedStructurer())
    pipeline.answer_text("no")
    pipeline.answer_text("no")
    pipeline.answer_text("yes")
    pipeline.record_age(AgeInfo(value_days=40 * 365, source=AgeSource.PATIENT, status=AgeStatus.KNOWN))

    pipeline.answer_text("I have chest pain")
    pipeline.answer_text("on the left side")
    pipeline.answer_text("it's a dull ache")
    pipeline.answer_text("no, it does not spread anywhere")
    pipeline.answer_text("no, breathing is fine")
    # Plain "no" here deliberately, not e.g. "not sweating" -- RuleBasedStructurer
    # does naive substring keyword matching with no negation handling, so a
    # phrase containing the word "sweating" would be (mis)extracted as the
    # symptom regardless of the "not" in front of it. A real LLM would not
    # make this mistake; this is a known, pre-existing limitation of the
    # offline fallback structurer, not something this test is about.
    pipeline.answer_text("no")
    pipeline.answer_text("started 20 minutes ago")
    pipeline.answer_text("3")
    pipeline.answer_text("no")
    pipeline.answer_text("no")
    pipeline.answer_text("none")
    pipeline.answer_text("none")

    assert pipeline.complete
    assert not pipeline.tree_session.stopped_for_red_flag
    outcome = pipeline.finalize()
    assert outcome.record.narrative.onset_minutes == 20
    assert outcome.record.narrative.self_reported_severity == 3
    assert outcome.red_flag.red_flag is False


def test_full_pipeline_vomiting_conversation_hinglish():
    """A second full conversation, in Hinglish, through a brand-new category."""
    pipeline = IntakePipeline("T-branch-02", RuleBasedStructurer())
    pipeline.answer_text("no")
    pipeline.answer_text("no")
    pipeline.answer_text("yes")
    pipeline.record_age(AgeInfo(value_days=30 * 365, source=AgeSource.PATIENT, status=AgeStatus.KNOWN))

    pipeline.answer_text("mujhe ulti ho rahi hai")
    assert pipeline.current_prompt == "How long have you been vomiting?"
    pipeline.answer_text("since this morning")
    pipeline.answer_text("about 4 times")
    pipeline.answer_text("no blood")
    pipeline.answer_text("not really, everything comes back up")
    pipeline.answer_text("mild stomach pain")
    pipeline.answer_text("no fever or loose motions")

    assert pipeline.current_prompt == "When did this start?"
    pipeline.answer_text("this morning")
    pipeline.answer_text("4")
    pipeline.answer_text("no")
    pipeline.answer_text("no")
    pipeline.answer_text("none")
    pipeline.answer_text("none")

    assert pipeline.complete
    outcome = pipeline.finalize()
    # The original Hinglish chief complaint is preserved verbatim somewhere
    # in the accumulated transcript -- not translated, not discarded.
    assert "ulti" in outcome.record.narrative.raw_transcript
