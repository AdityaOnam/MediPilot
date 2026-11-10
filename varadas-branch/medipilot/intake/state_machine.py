"""
M03 — Intake branch: explicit, deterministic, resumable conversation states.

Sequence (round2-implementation-plan.html §09):
    1. Is anyone with you?               -> ASSISTANCE_CHECK
    2. Would you prefer a person?        -> HUMAN_PREFERENCE
       (wants human -> HUMAN_ASSISTANCE_REQUESTED, clinical questions stop)
    3. Consent to use medical information -> CONSENT
       (declined -> LIMITED_INFORMATION_INTAKE marker, triage continues)
    4. Proceed, with the branch recorded  -> AGE_CONTEXT -> CLINICAL_QUESTIONS -> COMPLETE

A malformed/unrecognized answer never silently advances the state. Sessions
are resumable via to_state()/from_state().
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

from intake.models import AgeInfo, AgeSource, AgeStatus, ConsentState, TriState


class IntakeState(str, Enum):
    START = "START"
    ASSISTANCE_CHECK = "ASSISTANCE_CHECK"
    HUMAN_PREFERENCE = "HUMAN_PREFERENCE"
    HUMAN_ASSISTANCE_REQUESTED = "HUMAN_ASSISTANCE_REQUESTED"
    CONSENT = "CONSENT"
    LIMITED_INFORMATION_INTAKE = "LIMITED_INFORMATION_INTAKE"
    AGE_CONTEXT = "AGE_CONTEXT"
    CLINICAL_QUESTIONS = "CLINICAL_QUESTIONS"
    COMPLETE = "COMPLETE"


class InvalidAnswerError(ValueError):
    """Raised when an answer cannot be interpreted for the current state.
    The session does NOT advance when this is raised."""


# Mirrors intake/question_tree.py's yes/no normalization, kept as a
# self-contained copy here rather than a shared import: M03 (this module)
# intentionally has no dependency on M04/question_tree.py, and
# question_tree.py already imports InvalidAnswerError FROM this module, so
# importing the other way would be circular. A patient/attendant answering
# by voice rarely says a bare "yes"/"no" -- Whisper attaches sentence
# punctuation ("No.", "Yeah!"), sometimes mis-hears a clipped "no" as
# "Non.", and renders Hindi speech in Devanagari script, not romanized text.
_YES_KEYWORDS = [
    "yes", "y", "yeah", "yep", "yup", "sure", "definitely", "correct",
    "haan", "han", "ha", "bilkul", "true",
    "हाँ", "हां",
]
_NO_KEYWORDS = [
    "no", "n", "nope", "nah", "not really", "dont think so", "never",
    "nahi", "nahin", "bilkul nahi", "non", "false",
    "नहीं", "नही",
]

# ASR output attaches sentence punctuation to a short spoken answer
# ("No.", "Yeah!", "Yes,") -- stripped to spaces (not deleted outright, so
# adjacent words don't fuse together) before matching. Includes Devanagari
# danda "।"/double-danda "॥", not just ASCII punctuation.
_ASR_PUNCTUATION_RE = re.compile(r"[.,!?;:()\[\]\"“”‘’…—–।॥]+")
# Emphatic elongation ("Nooo.", "yesss") collapsed to the plain word before
# matching -- 3+ repeats of the same letter is not a normal spelling.
_REPEATED_CHAR_RE = re.compile(r"(.)\1{2,}")


def _normalize_asr_answer(answer: str) -> str:
    normalized = (answer or "").strip().lower().replace("'", "")
    normalized = _ASR_PUNCTUATION_RE.sub(" ", normalized)
    normalized = _REPEATED_CHAR_RE.sub(r"\1", normalized)
    normalized = re.sub(r"\s+", " ", normalized)
    return normalized.strip()


def _contains_word(text: str, phrase: str) -> bool:
    # Explicit whitespace/string-edge boundary, not Python's \b: \w does not
    # include Devanagari dependent vowel signs (matras), so \b fails to find
    # a boundary at the end of most Devanagari words. Text reaching here has
    # already had punctuation collapsed to single spaces (see
    # _normalize_asr_answer), so this is both correct and sufficient.
    return re.search(r"(?:^|\s)" + re.escape(phrase) + r"(?:\s|$)", text) is not None


def _parse_yes_no(answer: str) -> Optional[bool]:
    normalized = _normalize_asr_answer(answer)
    if not normalized:
        return None
    # Negation checked first: "not really" etc. should never be read as yes.
    if any(_contains_word(normalized, kw) for kw in _NO_KEYWORDS):
        return False
    if any(_contains_word(normalized, kw) for kw in _YES_KEYWORDS):
        return True
    return None


@dataclass
class IntakeSession:
    """
    Holds one patient's intake conversation state. `advance()` is the only
    way state changes; it validates the answer against the current state
    before transitioning, so a malformed answer cannot silently move the
    patient forward.
    """

    patient_id: Optional[str] = None
    state: IntakeState = IntakeState.START
    state_history: list = field(default_factory=lambda: [IntakeState.START.value])

    assisted: TriState = TriState.UNKNOWN
    human_assistance_requested: bool = False
    medical_information_consent: ConsentState = ConsentState.UNKNOWN
    age: AgeInfo = field(default_factory=AgeInfo)

    def _transition(self, new_state: IntakeState) -> None:
        self.state = new_state
        self.state_history.append(new_state.value)

    def start(self) -> IntakeState:
        if self.state != IntakeState.START:
            return self.state
        self._transition(IntakeState.ASSISTANCE_CHECK)
        return self.state

    def answer_assistance_check(self, answer: str) -> IntakeState:
        """Q1: Is anyone with you?"""
        if self.state != IntakeState.ASSISTANCE_CHECK:
            raise InvalidAnswerError(f"not awaiting assistance-check answer (state={self.state})")
        parsed = _parse_yes_no(answer)
        if parsed is None:
            raise InvalidAnswerError(f"unrecognized yes/no answer: {answer!r}")
        self.assisted = TriState.TRUE if parsed else TriState.FALSE
        self._transition(IntakeState.HUMAN_PREFERENCE)
        return self.state

    def answer_human_preference(self, answer: str) -> IntakeState:
        """Q2: Would you prefer a person? Wants human -> stop clinical questions."""
        if self.state != IntakeState.HUMAN_PREFERENCE:
            raise InvalidAnswerError(f"not awaiting human-preference answer (state={self.state})")
        parsed = _parse_yes_no(answer)
        if parsed is None:
            raise InvalidAnswerError(f"unrecognized yes/no answer: {answer!r}")
        if parsed:
            self.human_assistance_requested = True
            self._transition(IntakeState.HUMAN_ASSISTANCE_REQUESTED)
        else:
            self._transition(IntakeState.CONSENT)
        return self.state

    def answer_consent(self, answer: str) -> IntakeState:
        """Q3: Consent to use medical information (distinct from consent to treat)."""
        if self.state != IntakeState.CONSENT:
            raise InvalidAnswerError(f"not awaiting consent answer (state={self.state})")
        parsed = _parse_yes_no(answer)
        if parsed is None:
            raise InvalidAnswerError(f"unrecognized yes/no answer: {answer!r}")
        if parsed:
            self.medical_information_consent = ConsentState.GRANTED
            self._transition(IntakeState.AGE_CONTEXT)
        else:
            self.medical_information_consent = ConsentState.DECLINED
            self._transition(IntakeState.LIMITED_INFORMATION_INTAKE)
        return self.state

    def acknowledge_limited_information_intake(self) -> IntakeState:
        """Declining consent does not stop triage — proceed on observed/measured data only."""
        if self.state != IntakeState.LIMITED_INFORMATION_INTAKE:
            raise InvalidAnswerError(f"not in LIMITED_INFORMATION_INTAKE (state={self.state})")
        self._transition(IntakeState.AGE_CONTEXT)
        return self.state

    def record_age(self, age_info: AgeInfo) -> IntakeState:
        if self.state != IntakeState.AGE_CONTEXT:
            raise InvalidAnswerError(f"not awaiting age context (state={self.state})")
        self.age = age_info
        self._transition(IntakeState.CLINICAL_QUESTIONS)
        return self.state

    def complete(self) -> IntakeState:
        if self.state not in (IntakeState.CLINICAL_QUESTIONS,):
            raise InvalidAnswerError(f"cannot complete from state={self.state}")
        self._transition(IntakeState.COMPLETE)
        return self.state

    @property
    def clinical_questions_allowed(self) -> bool:
        """Once a human has been requested, the system must stop asking clinical questions."""
        return not self.human_assistance_requested

    def to_state(self) -> dict:
        return {
            "patient_id": self.patient_id,
            "state": self.state.value,
            "state_history": list(self.state_history),
            "assisted": self.assisted.value,
            "human_assistance_requested": self.human_assistance_requested,
            "medical_information_consent": self.medical_information_consent.value,
            "age": {
                "value_days": self.age.value_days,
                "source": self.age.source.value,
                "status": self.age.status.value,
                "appearance_hint": self.age.appearance_hint,
            },
        }

    @classmethod
    def from_state(cls, data: dict) -> "IntakeSession":
        age_data = data.get("age") or {}
        session = cls(
            patient_id=data.get("patient_id"),
            state=IntakeState(data["state"]),
            state_history=list(data.get("state_history", [])),
            assisted=TriState(data.get("assisted", TriState.UNKNOWN.value)),
            human_assistance_requested=data.get("human_assistance_requested", False),
            medical_information_consent=ConsentState(
                data.get("medical_information_consent", ConsentState.UNKNOWN.value)
            ),
            age=AgeInfo(
                value_days=age_data.get("value_days"),
                source=AgeSource(age_data.get("source", AgeSource.UNKNOWN.value)),
                status=AgeStatus(age_data.get("status", AgeStatus.UNKNOWN.value)),
                appearance_hint=age_data.get("appearance_hint"),
            ),
        )
        return session
