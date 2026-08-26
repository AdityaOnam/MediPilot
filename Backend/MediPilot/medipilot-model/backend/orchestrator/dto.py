"""
camelCase DTOs mirroring frontend/lib/api/types.ts one-for-one.

Pydantic models with alias_generator = to_camel so JSON is camelCase
while Python code uses snake_case.
"""

from __future__ import annotations

from typing import Optional, Any
from pydantic import BaseModel, Field


def to_camel(name: str) -> str:
    parts = name.split("_")
    return parts[0] + "".join(w.capitalize() for w in parts[1:])


class _CamelModel(BaseModel):
    model_config = {"alias_generator": to_camel, "populate_by_name": True}


# ---- Measurement ----

class MeasurementDTO(_CamelModel):
    code: str
    value: Optional[float] = None
    unit: str
    taken_at: str
    source: str
    validity: str
    band_for_stratum: Optional[str] = None
    de_escalation_authority: Optional[bool] = None


# ---- Cadence ----

class CadenceDTO(_CamelModel):
    rescore_sec: int
    remeasure_sec: int
    ceiling_sec: int
    next_rescore_at: str
    next_remeasure_at: str
    ceiling_breaches_at: str
    breached: bool
    breach_kind: Optional[str] = None


# ---- Encounter ----

class EncounterDTO(_CamelModel):
    encounter_id: str
    token: str
    display_name: Optional[str] = None
    age_years: Optional[float] = None
    age_stratum: str
    age_stratum_inferred: bool
    sex: Optional[str] = None
    chief_complaint: Optional[str] = None
    arrived_at: str
    arrival_mode: str = "walk-in"
    human_assigned_band: Optional[str] = None
    current_band: Optional[str] = None
    measurements: list[MeasurementDTO] = Field(default_factory=list)
    cadence: CadenceDTO
    has_prior_record: bool = False
    assisted: bool = True
    human_assistance_requested: bool = False
    medical_info_consent: bool = True
    state: str = "waiting"
    last_scored_at: Optional[str] = None


# ---- Score response ----

class FactorDTO(_CamelModel):
    label: str
    direction: str
    magnitude: float
    source: str


class RedFlagDTO(_CamelModel):
    observation: str
    maps_to: str = "RED"
    locked_downward: bool = True


class TimelineEventDTO(_CamelModel):
    at: str
    kind: str
    detail: str


class ReliabilityDiscountDTO(_CamelModel):
    factor: str
    applies_to: str = "reassuring-only"
    label: str = ""


class ExplanationDTO(_CamelModel):
    channel1: list[FactorDTO] = Field(default_factory=list)
    channel2: dict = Field(default_factory=dict)
    channel3: dict = Field(default_factory=dict)


class ScoreResponseDTO(_CamelModel):
    encounter_id: str
    server_time: str
    sim_time: str
    abstained: bool
    abstention_reason: Optional[str] = None
    effective_band: str
    band: Optional[str] = None
    probability: Optional[float] = None
    conformal_set: Optional[list[str]] = None
    coverage: Optional[float] = None
    confidence: Optional[str] = None
    confidence_reduced_by: Optional[list[str]] = None
    inputs_used: Optional[list[str]] = None
    red_flags: Optional[list[RedFlagDTO]] = None
    explanation: Optional[ExplanationDTO] = None
    suggests_review: Optional[bool] = None
    suggests_review_reason: Optional[str] = None
    threshold_used: float
    cost_ratio_r: float = Field(alias="costRatioR")
    model_version: str
    calibration_version: str
    audit_id: str


# ---- Override record ----

class OverrideRecordDTO(_CamelModel):
    patient_id: str
    timestamp_utc: str
    clinician_id: str
    clinician_role: str
    system_band: str
    clinician_band: str
    direction: str
    reason_code: str
    reason_text: str
    score: float
    confidence: str
    factors_shown: list[FactorDTO] = Field(default_factory=list)
    inputs_hash: str
    model_version: str
    calibration_version: str
    consent_state: str
    outcome_ref: Optional[str] = None
    hash: Optional[str] = None
    prev_hash: Optional[str] = None


# ---- Recheck task ----

class RecheckTaskDTO(_CamelModel):
    encounter_id: str
    owner: str
    trust: str
    due_at: str
    can_close_bands: list[str] = Field(default_factory=list)


# ---- Surge ----

class SurgeStretchDTO(_CamelModel):
    band: str
    from_sec: int
    to_sec: int


class SurgeStateDTO(_CamelModel):
    active: bool
    multiplier: float
    stretched: list[SurgeStretchDTO] = Field(default_factory=list)
    refusals: list[str] = Field(default_factory=list)


# ---- R control ----

class RControlResponseDTO(_CamelModel):
    r: float = Field(alias="R")
    p_star: float
    moved: dict
    note: str
    census: list[EncounterDTO]


# ---- Site config ----

class SiteConfigDTO(_CamelModel):
    cost_ratio_r: float = Field(alias="costRatioR")
    r_bounds: dict = Field(alias="rBounds")
    cadences: dict
    strata: list[dict]
    model_version: str
    calibration_version: str


# ---- Decision input ----

class DecisionInputDTO(_CamelModel):
    encounter_id: str
    action: str
    band: Optional[str] = None
    reason_code: Optional[str] = None
    reason_text: Optional[str] = None
    clinician_id: str
    clinician_role: str
    factors_shown: Optional[list[FactorDTO]] = None
    score_at_decision: Optional[dict] = None


# ---- Stream event ----

class StreamEventDTO(_CamelModel):
    type: str
    encounter_id: Optional[str] = None
    band: Optional[str] = None
    sim_time: Optional[str] = None
    from_band: Optional[str] = Field(None, alias="from")
    to_band: Optional[str] = Field(None, alias="to")
    cause: Optional[str] = None
    audit_id: Optional[str] = None
    kind: Optional[str] = None
    band_changed: Optional[bool] = None
    owner: Optional[str] = None
    active: Optional[bool] = None
    multiplier: Optional[float] = None
