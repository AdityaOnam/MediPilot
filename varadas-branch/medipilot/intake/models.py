"""
Typed data contracts for the Stage 2 intake subsystem.

These are the structures M03-M06 produce and M07-M09 consume. Field names
follow round2-implementation-plan.html and the conceptual schema in the
Round 2 task brief, adapted to fit together as one coherent pipeline
rather than as isolated modules.

Nothing in this file computes a clinical decision. It only shapes data.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


# ---------------------------------------------------------------------------
# Age (collected by intake; RESOLVED by M08, not here — see age_stratification.py)
# ---------------------------------------------------------------------------

class AgeStratum(str, Enum):
    NEONATE = "neonate"        # < 28 days
    INFANT = "infant"          # 28 days - 1 year
    CHILD = "child"            # 1 - 12 years
    ADOLESCENT = "adolescent"  # 12 - 18 years
    ADULT = "adult"            # 18 - 65 years
    GERIATRIC = "geriatric"    # 65+ years


class AgeSource(str, Enum):
    PATIENT = "patient"
    ATTENDANT = "attendant"
    RECORD = "record"
    INFERRED = "inferred"
    UNKNOWN = "unknown"


class AgeStatus(str, Enum):
    KNOWN = "known"
    INFERRED = "inferred"
    UNKNOWN = "unknown"


@dataclass
class AgeInfo:
    """What the intake layer observed about age. Does NOT resolve a stratum."""

    value_days: Optional[int] = None
    source: AgeSource = AgeSource.UNKNOWN
    status: AgeStatus = AgeStatus.UNKNOWN
    appearance_hint: Optional[str] = None  # e.g. "appears elderly" — coarse, optional


# ---------------------------------------------------------------------------
# Consent / assistance branch (M03)
# ---------------------------------------------------------------------------

class ConsentState(str, Enum):
    GRANTED = "granted"
    DECLINED = "declined"
    UNKNOWN = "unknown"


class TriState(str, Enum):
    TRUE = "true"
    FALSE = "false"
    UNKNOWN = "unknown"


# ---------------------------------------------------------------------------
# Observations / symptoms (M04 output, M06 output)
# ---------------------------------------------------------------------------

class ObservationCode(str, Enum):
    """
    Closed vocabulary of clinically-meaningful observation codes the red-flag
    table (M07) can match against. Deliberately small and illustrative, per
    round2-implementation-plan.html §10 / intake_architecture_part3.svg —
    NOT an exhaustive clinical ontology.
    """

    CHEST_PAIN = "chest_pain"
    SWEATING = "sweating"
    BREATHLESSNESS = "breathlessness"
    RADIATING_PAIN = "radiating_pain"
    ALTERED_CONSCIOUSNESS = "altered_consciousness"
    NOT_RESPONDING = "not_responding"
    ACTIVE_LABOUR = "active_labour"
    BLEEDING_IN_PREGNANCY = "bleeding_in_pregnancy"
    DIFFICULTY_SPEAKING_FULL_SENTENCES = "difficulty_speaking_full_sentences"
    SUDDEN_ONE_SIDED_WEAKNESS = "sudden_one_sided_weakness"
    FACIAL_DROOP = "facial_droop"
    SUDDEN_SPEECH_CHANGE = "sudden_speech_change"
    UNCONTROLLED_BLEEDING = "uncontrolled_bleeding"
    PENETRATING_INJURY = "penetrating_injury"
    POISONING_OR_OVERDOSE = "poisoning_or_overdose"
    SNAKEBITE = "snakebite"
    INFANT_NOT_FEEDING = "infant_not_feeding"
    INFANT_FLOPPY = "infant_floppy"
    INFANT_INCONSOLABLE = "infant_inconsolable"
    FEVER = "fever"
    WEAKNESS_GENERAL = "weakness_general"

    # Added for the expanded complaint-category question tree (M04). Each of
    # these is a reusable fact referenced by more than one complaint
    # category below, not a one-off per question — kept deliberately small.
    VOMITING = "vomiting"
    DIARRHEA = "diarrhea"
    ABDOMINAL_PAIN = "abdominal_pain"
    SEIZURE = "seizure"
    CHOKING_OR_AIRWAY_OBSTRUCTION = "choking_or_airway_obstruction"
    VAGINAL_BLEEDING = "vaginal_bleeding"
    BURN_INJURY = "burn_injury"


@dataclass
class Observation:
    """One structured fact collected during intake, with provenance."""

    field: str
    value: object
    source: str  # "patient" | "attendant" | "clinician" | "inference" | "asr"
    raw_answer: Optional[str] = None
    confidence: Optional[float] = None


@dataclass
class StructuredNarrative:
    """
    M06 output schema. Extraction only — no diagnosis, no acuity, no band.
    Matches the FIXED-fields contract in intake_architecture_part2.svg.
    """

    chief_complaint: Optional[str] = None
    onset_minutes: Optional[int] = None
    self_reported_severity: Optional[int] = None  # 0-10
    symptoms: list = field(default_factory=list)  # list[ObservationCode]
    medications: list = field(default_factory=list)  # list[str]
    pregnancy_status: Optional[bool] = None
    relevant_history: list = field(default_factory=list)  # list[str]

    raw_transcript: str = ""
    extraction_status: str = "ok"  # "ok" | "malformed" | "empty_input" | "error"
    missing_fields: list = field(default_factory=list)
    unrecognized_terms: list = field(default_factory=list)


# ---------------------------------------------------------------------------
# Reliability signals (M09 interface — intake COLLECTS, does not weight)
# ---------------------------------------------------------------------------

@dataclass
class ReliabilitySignals:
    """
    Observable/contextual signals that may reduce the evidential weight of a
    REASSURING self-report downstream (M09). None of these are risk-model
    features on their own, and none of them touch an alarming report.
    See round2-implementation-plan.html §07.
    """

    geriatric_stratum: bool = False
    communication_barrier: TriState = TriState.UNKNOWN
    health_literacy_signal: bool = False
    stoic_presentation: bool = False  # clinician-set only, never model-guessed
    non_assisted_arrival: bool = False
    analgesia_given: bool = False


# ---------------------------------------------------------------------------
# Red-flag pass (M07)
# ---------------------------------------------------------------------------

@dataclass
class RedFlagResult:
    red_flag: bool
    rule_id: Optional[str]
    matched_observations: list = field(default_factory=list)
    description: Optional[str] = None


# ---------------------------------------------------------------------------
# Top-level intake result / downstream handoff
# ---------------------------------------------------------------------------

@dataclass
class IntakeRecord:
    """The Stage 2 output contract handed to M07-M09 and beyond."""

    patient_id: Optional[str]

    assisted: TriState = TriState.UNKNOWN
    human_assistance_requested: bool = False
    medical_information_consent: ConsentState = ConsentState.UNKNOWN
    interaction_mode: Optional[str] = None  # "voice" | "text"
    language: Optional[str] = None
    communication_barrier: TriState = TriState.UNKNOWN

    age: AgeInfo = field(default_factory=AgeInfo)

    narrative: Optional[StructuredNarrative] = None
    reliability_signals: ReliabilitySignals = field(default_factory=ReliabilitySignals)

    state_history: list = field(default_factory=list)  # ordered list of state names
    provenance: dict = field(default_factory=dict)  # field_name -> {"source":..., "confidence":...}
