"""
Regression tests for the exact reported bug: real Whisper ASR output like
"No." was rejected by the M03 intake-branch questions (Is anyone with you?/
Would you prefer a person?/consent), even though intake/question_tree.py's
own yes/no parser had already been fixed for natural ASR punctuation.

Root cause: intake/state_machine.py has its OWN, separate _parse_yes_no --
an exact set-membership check ({"no","n","nahi",...}) -- used by
answer_assistance_check()/answer_human_preference()/answer_consent(). It is
NOT the same function as intake/question_tree.py's _parse_yes_no (same
name, different module, never shared), so fixing the question-tree parser
never touched this path. voice_conversation.py's very first two questions
(assistance check, human preference) are answered through this exact code
path -- before the question tree even exists -- which is why the voice
conversation failed on "No." immediately, before any clinical question was
ever reached.

Fixed by upgrading intake/state_machine.py's own _parse_yes_no with the
same normalization approach (ASR punctuation incl. Devanagari, elongation,
whitespace/string-edge word boundaries) as a self-contained copy -- no
cross-import into question_tree.py (would be circular: question_tree.py
already imports InvalidAnswerError FROM state_machine.py).

Uses RuleBasedStructurer (deterministic, offline) throughout -- no network
access or GROQ_API_KEY required.
"""

import pytest

from intake.llm_structurer import RuleBasedStructurer
from intake.pipeline import IntakePipeline
from intake.state_machine import IntakeSession, IntakeState, InvalidAnswerError, _parse_yes_no


# ---------------------------------------------------------------------------
# state_machine._parse_yes_no in isolation
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "text, expected",
    [
        ("No.", False),
        ("Yes.", True),
        ("No!", False),
        ("nope", False),
        ("yeah", True),
        ("haan.", True),
        ("nahi.", False),
        ("yes", True),
        ("no", False),
        ("Non.", False),
        ("Nooo.", False),
        ("yesss", True),
        ("नहीं।", False),
        ("हाँ।", True),
        ("", None),
        ("maybe", None),
    ],
)
def test_state_machine_parse_yes_no_handles_asr_punctuation(text, expected):
    assert _parse_yes_no(text) == expected


# ---------------------------------------------------------------------------
# Exact reported regression: pipeline.answer_voice_transcript("No.", ...)
# must advance ASSISTANCE_CHECK -> HUMAN_PREFERENCE.
# ---------------------------------------------------------------------------

def test_answer_voice_transcript_no_period_advances_assistance_check():
    pipeline = IntakePipeline("voice-regression-001", RuleBasedStructurer())
    assert pipeline.session.state == IntakeState.ASSISTANCE_CHECK

    pipeline.answer_voice_transcript(text="No.", language="en", asr_reliability=None)

    assert pipeline.session.state == IntakeState.HUMAN_PREFERENCE
    assert pipeline.session.assisted.value == "false"


@pytest.mark.parametrize("answer", ["Yes.", "No!", "nope", "yeah", "haan.", "nahi."])
def test_answer_voice_transcript_common_asr_punctuated_answers_advance_assistance_check(answer):
    pipeline = IntakePipeline("voice-regression-002", RuleBasedStructurer())
    assert pipeline.session.state == IntakeState.ASSISTANCE_CHECK

    pipeline.answer_voice_transcript(text=answer, language="en", asr_reliability=None)

    assert pipeline.session.state == IntakeState.HUMAN_PREFERENCE  # never raises, always advances


def test_full_assistance_and_preference_and_consent_sequence_via_voice_punctuation():
    """The whole M03 sequence (three yes/no questions in a row), each
    answered with real ASR-style punctuation, exactly as
    voice_conversation.py would drive it before any clinical question is
    ever reached."""
    pipeline = IntakePipeline("voice-regression-003", RuleBasedStructurer())

    pipeline.answer_voice_transcript(text="No.", language="en", asr_reliability=None)  # assisted?
    assert pipeline.session.state == IntakeState.HUMAN_PREFERENCE

    pipeline.answer_voice_transcript(text="No.", language="en", asr_reliability=None)  # wants a person?
    assert pipeline.session.state == IntakeState.CONSENT

    pipeline.answer_voice_transcript(text="Yes.", language="en", asr_reliability=None)  # consent
    assert pipeline.session.state == IntakeState.AGE_CONTEXT


def test_unparseable_voice_answer_still_raises_not_silently_advances():
    """The fix must not become so lenient that it accepts everything --
    genuinely unparseable input still raises, matching the existing
    "malformed answer never silently advances the state" contract."""
    session = IntakeSession()
    session.start()
    with pytest.raises(InvalidAnswerError):
        session.answer_assistance_check("...")
    assert session.state == IntakeState.ASSISTANCE_CHECK  # did not advance
