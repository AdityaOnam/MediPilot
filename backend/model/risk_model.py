"""
backend/model/risk_model.py

Main scoring entry-point. Orchestrates the full pipeline:

  1. Stratum resolution (age_stratum.py)
  2. Vital freshness check (Invariant 4)
  3. Deterministic red-flag engine (rules/red_flag_engine.py) — fires first
  4. Vital threshold assessment (thresholds.py)
  5. Raw risk scoring (feature-weighted)
  6. Calibration (calibration.py) — per-stratum
  7. Reliability weighting (reliability.py) — asymmetric
  8. Conformal uncertainty (conformal.py)
  9. Band assignment (conformal result → ScoreObject or AbstentionObject)

Output contract (§7): either a fully-populated ScoreObject or an
AbstentionObject — never a partially-populated object (Invariant 2).
"""

from __future__ import annotations

import datetime
import hashlib
import json
from dataclasses import dataclass, field, asdict
from typing import Optional, Any

import numpy as np

from model.age_stratum import resolve_stratum
from model.thresholds import get_thresholds
from model.freshness import (
    VITAL_CADENCE_MINUTES,
    reading_age_minutes,
    check_freshness,
)
from model.calibration import calibrate, get_reassurance_decay, MODEL_VERSION, CALIBRATION_VERSION
from model.reliability import compute_reliability_discount
from model.conformal import compute_confidence, DEFAULT_COST_RATIO_R
from model.artifact import artifact_status, current_versions
from rules.red_flag_engine import RedFlagEngine
from rules.spo2_bias_guard import check_spo2_alone_deescalation


# ---------------------------------------------------------------------------
# Output contracts — §7
# ---------------------------------------------------------------------------

@dataclass
class ScoreObject:
    """Fully-populated score object — the output contract per §7."""
    patient_id: str
    band: str
    confidence: float
    confidence_reason: Optional[str]
    factors_for: list[str]
    factors_against: list[str]
    age_stratum: str
    age_stratum_inferred: bool
    reliability_discounts_applied: list[str]
    abstained: bool
    model_version: str
    calibration_version: str
    computed_at: str                # ISO-8601
    score_source: str = "heuristic"  # "model" | "heuristic" | "red_flag_rule"

    def __post_init__(self) -> None:
        # Defense in depth for Invariant 5: no path in score_patient() emits
        # ScoreObject with abstained=True today, but a future caller must not
        # be able to construct that state with band="green".
        if self.abstained and self.band == "green":
            raise ValueError(
                f"AsymmetricAutonomyViolation: ScoreObject cannot be "
                f"abstained=True with band='green' (Invariant 5) for "
                f"patient '{self.patient_id}'."
            )

    def as_dict(self) -> dict:
        return asdict(self)

    def inputs_hash(self, inputs: dict) -> str:
        """SHA-256 of the inputs — used in audit records."""
        raw = json.dumps(inputs, sort_keys=True, default=str)
        return hashlib.sha256(raw.encode()).hexdigest()


@dataclass
class AbstentionObject:
    """
    Emitted when confidence cannot be computed (Invariant 2, 5).
    band is always 'yellow' (Invariant 5 — abstained patient never Green).
    """
    patient_id: str
    band: str = "yellow"             # Invariant 5
    abstained: bool = True
    confidence: float = 0.0
    confidence_reason: str = "abstention"
    age_stratum: str = "unknown"
    age_stratum_inferred: bool = True
    reliability_discounts_applied: list[str] = field(default_factory=list)
    factors_for: list[str] = field(default_factory=list)
    factors_against: list[str] = field(default_factory=list)
    model_version: str = MODEL_VERSION
    calibration_version: str = CALIBRATION_VERSION
    computed_at: str = ""

    def __post_init__(self) -> None:
        # Invariant 5 must be a guard, not a default — a caller passing
        # band="green" explicitly must be rejected, not silently accepted.
        if self.band != "yellow":
            raise ValueError(
                f"AsymmetricAutonomyViolation: AbstentionObject band must be "
                f"'yellow' (Invariant 5 — abstained patient never Green), got "
                f"'{self.band}' for patient '{self.patient_id}'."
            )
        if not self.abstained:
            raise ValueError(
                f"AbstentionObject.abstained must be True for patient "
                f"'{self.patient_id}' — an unabstained object should be a "
                f"ScoreObject instead."
            )

    def as_dict(self) -> dict:
        return asdict(self)


# ---------------------------------------------------------------------------
# Input record schema (consumed from Track A)
# ---------------------------------------------------------------------------

@dataclass
class PatientRecord:
    """
    Structured record from Track A (intake/LLM).
    All fields are Optional — the model handles missing data gracefully.
    """
    patient_id: str

    # Age
    age_days: Optional[int] = None
    age_known: bool = True

    # Vitals — each is Optional[tuple[value, timestamp_iso, source, validity]]
    hr: Optional[tuple] = None
    rr: Optional[tuple] = None
    bp_sys: Optional[tuple] = None
    spo2: Optional[tuple] = None
    temp_c: Optional[tuple] = None
    gcs: Optional[tuple] = None
    pain_score: Optional[tuple] = None

    # Optional trailing history for trend features (list of tuples per vital).
    # Format: {"hr": [(value, ts_iso, source, validity), ...], ...}
    # When present, features.py extracts slopes and deltas; absent → NaN (native).
    vitals_history: Optional[dict] = None

    # Red-flag observations from Track A narrative extraction
    red_flag_observations: list[str] = field(default_factory=list)

    # Reliability flags (from Track A or clinician)
    reliability_flags: dict[str, bool] = field(default_factory=dict)

    # Patient-level flags
    spo2_bias_risk: bool = False     # dark skin tone flag → SpO2 bias guard applies

    # Prior band (for asymmetric autonomy enforcement in band_engine.py)
    current_band: Optional[str] = None

    # Context
    arrived_at: Optional[str] = None    # ISO-8601


# ---------------------------------------------------------------------------
# Freshness check (Invariant 4) — implementation lives in model/freshness.py
# so that training and serving share one code path (train/serve skew guard).

_VITAL_CADENCE_MINUTES = VITAL_CADENCE_MINUTES   # backwards-compatible alias
_reading_age_minutes = reading_age_minutes
_check_freshness = check_freshness


# ---------------------------------------------------------------------------
# Raw risk scoring (feature-weighted)
# ---------------------------------------------------------------------------

# Feature weights for raw risk score
_VITAL_WEIGHTS = {
    "hr":        0.15,
    "rr":        0.20,   # RR is an early reliable sign
    "bp_sys":    0.20,
    "spo2":      0.15,
    "temp_c":    0.15,   # increased — fever is a strong signal
    "gcs":       0.10,
    "pain_score": 0.05,
}


# Below this reassurance_decay, a "normal" reading is weak evidence of
# safety in this stratum (currently: geriatric at 0.25). The factor string
# gets an explicit qualifier so the explanation channel says what the score
# already knows — see F2 in FIX_PLAN.md: the score was stratum-aware and the
# explanation wasn't, so two patients treated differently got identical cards.
_WEAK_REASSURANCE_DECAY_THRESHOLD = 0.4


def _raw_risk_score(
    threshold_results: list,
    missing_vitals: set[str],
    stratum: str,
    reassurance_decay: float,
) -> tuple[float, list[str], list[str]]:
    """
    Compute raw risk score as weighted sum of abnormality severity.
    Returns (score, factors_for, factors_against).

    factors_against carries the vital name as a stable, machine-parseable
    prefix ("hr_normal") with an optional human-readable qualifier suffix
    when this stratum's reassurance_decay means "normal" isn't strongly
    reassuring here. This keeps the §7 output contract (list[str]) unchanged
    for the frontend while making the explanation stratum-aware.
    """
    score = 0.0
    factors_for = []
    factors_against = []
    weak_reassurance = reassurance_decay < _WEAK_REASSURANCE_DECAY_THRESHOLD

    for tr in threshold_results:
        w = _VITAL_WEIGHTS.get(tr.vital, 0.05)
        if tr.is_abnormal:
            contribution = w * min(tr.deviation_sigma, 3.0) / 3.0
            score += contribution
            factors_for.append(
                f"{tr.vital}_{tr.direction} (σ={tr.deviation_sigma:.1f})"
            )
        else:
            if tr.vital not in missing_vitals:
                if weak_reassurance:
                    factors_against.append(f"{tr.vital}_normal (weak reassurance — {stratum})")
                else:
                    factors_against.append(f"{tr.vital}_normal")

    # Cap at 1.0 and sort by contribution
    score = float(np.clip(score, 0.0, 1.0))
    return score, factors_for[:3], factors_against[:2]


# ---------------------------------------------------------------------------
# Main scorer
# ---------------------------------------------------------------------------

_red_flag_engine: Optional[RedFlagEngine] = None

def _get_red_flag_engine() -> RedFlagEngine:
    global _red_flag_engine
    if _red_flag_engine is None:
        _red_flag_engine = RedFlagEngine()
    return _red_flag_engine


def score_patient_verbose(
    record: PatientRecord,
    cost_ratio_R: float = DEFAULT_COST_RATIO_R,
    now: Optional[datetime.datetime] = None,
    ood_flag: bool = False,
) -> tuple[ScoreObject | AbstentionObject, Optional[float], Optional[Any]]:
    """
    Like score_patient but also returns (result, p_model, ConformalResult).

    The orchestrator needs p_model (calibrated probability) for live R re-sort
    and ConformalResult for the frontend's conformal set / prediction_set fields.
    """
    if now is None:
        now = datetime.datetime.now(tz=datetime.timezone.utc)

    computed_at = now.isoformat()

    # 1. Stratum resolution (Invariant 3)
    stratum_result = resolve_stratum(record.age_days, record.age_known)

    # 2. Red-flag check — independent of model, fires first
    rfe = _get_red_flag_engine()
    red_flag_result = rfe.check(record.red_flag_observations)
    if red_flag_result is not None:
        # Red flag fires → Red band, no model consultation needed
        mv, cv = current_versions()
        return ScoreObject(
            patient_id=record.patient_id,
            band="red",
            confidence=0.95,
            confidence_reason=f"deterministic_red_flag: {red_flag_result.flag_id}",
            factors_for=[red_flag_result.description],
            factors_against=[],
            age_stratum=stratum_result.stratum,
            age_stratum_inferred=stratum_result.inferred,
            reliability_discounts_applied=[],
            abstained=False,
            model_version=mv,
            calibration_version=cv,
            computed_at=computed_at,
            score_source="red_flag_rule",
        ), None, None

    # 3. OOD flag → abstain (Invariant 2, 5)
    if ood_flag:
        conf_result = compute_confidence(
            calibrated_score=0.5,
            uncertainty_inflation=0.0,
            inferred_stratum=stratum_result.inferred,
            stale_reading=False,
            ood_flag=True,
            cost_ratio_R=cost_ratio_R,
        )
        return AbstentionObject(
            patient_id=record.patient_id,
            band="yellow",
            abstained=True,
            confidence=0.0,
            confidence_reason="out_of_distribution",
            age_stratum=stratum_result.stratum,
            age_stratum_inferred=stratum_result.inferred,
            computed_at=computed_at,
        ), None, conf_result

    # 4. Extract vitals with freshness check (Invariant 4)
    current_band = record.current_band or "yellow"
    vitals_raw: dict[str, Any] = {}
    stale_any = False
    missing_vitals: set[str] = set()

    for vital in ["hr", "rr", "bp_sys", "spo2", "temp_c", "gcs", "pain_score"]:
        vt = getattr(record, vital, None)
        val, stale, missing = _check_freshness(vt, current_band, now)
        if missing:
            missing_vitals.add(vital)
        elif stale:
            vitals_raw[vital] = val
            stale_any = True
        else:
            vitals_raw[vital] = val

    # If ALL vitals missing → must abstain (Invariant 2)
    if len(missing_vitals) == len(["hr", "rr", "bp_sys", "spo2", "temp_c", "gcs", "pain_score"]):
        return AbstentionObject(
            patient_id=record.patient_id,
            band="yellow",
            abstained=True,
            confidence=0.0,
            confidence_reason="all_vitals_missing_or_stale",
            age_stratum=stratum_result.stratum,
            age_stratum_inferred=stratum_result.inferred,
            computed_at=computed_at,
        ), None, None

    # 5. SpO2 bias guard: note — the guard fires on DE-ESCALATION decisions,
    # not during scoring. It lives in band_engine.py. During scoring, SpO2
    # is used as one input among many; its weight is NOT boosted just because
    # spo2_bias_risk=True (that would be the wrong direction).
    # The guard is explicitly NOT called here — only in band_engine.py.

    # 6. Threshold assessment (thresholds.py)
    thresholds = get_thresholds()
    n_abnormal, threshold_results = thresholds.count_abnormal_vitals(
        {k: v for k, v in vitals_raw.items() if v is not None},
        stratum_result.stratum,
    )
    n_total = len([k for k in vitals_raw if vitals_raw[k] is not None])

    # 7. Reliability weighting (reliability.py — asymmetric)
    # Determine if the overall answer is reassuring (majority of vitals normal)
    is_reassuring_answer = n_abnormal < n_total * 0.4
    reliability_result = compute_reliability_discount(
        flags=record.reliability_flags,
        stratum=stratum_result.stratum,
        is_reassuring_answer=is_reassuring_answer,
    )

    # 8a. Heuristic raw risk score + calibration (always computed; used as
    #     fallback explanation source and fallback band when model unavailable).
    reassurance_decay_for_stratum = get_reassurance_decay(stratum_result.stratum)
    raw_score, factors_for, factors_against = _raw_risk_score(
        threshold_results, missing_vitals, stratum_result.stratum, reassurance_decay_for_stratum
    )

    # Missing vitals add uncertainty — also add to factors
    if missing_vitals:
        factors_for_extras = [f"missing_{v}" for v in sorted(missing_vitals)]
        factors_for = (factors_for + factors_for_extras)[:3]

    cal_result = calibrate(
        raw_score=raw_score,
        stratum=stratum_result.stratum,
        n_abnormal_vitals=n_abnormal,
        n_total_vitals=n_total,
        trend_slope=0.0,
    )

    # 8b. Trained model path (with fallback).
    #     The model supplies a calibrated P(critical composite) which replaces
    #     the heuristic calibrated_score in the conformal step. Explanation
    #     strings are still threshold-derived (keeps test_p03 string assertions).
    p_model: Optional[float] = None
    score_source = "heuristic"
    try:
        from model.features import from_patient_record, build_feature_row
        from model.predictor import predict_p_critical
        fi = from_patient_record(record, stratum_result, now)
        feat_row = build_feature_row(fi)
        p_model, score_source = predict_p_critical(feat_row, stratum_result.stratum, record)
    except Exception:
        pass  # any failure → heuristic fallback; never raises into triage path

    # 8c. Hard safety guarantee 1: abnormal_vital_floor (stratum-specific).
    #     A febrile toddler or geriatric with any abnormal vital must never
    #     score below Yellow. Floor read from cal_result (already enforced on
    #     heuristic path) and translated to model-probability space.
    if p_model is not None and cal_result.abnormal_vital_floor_applied:
        try:
            from model.artifact import get_artifact
            art = get_artifact()
            if art is not None:
                from model.conformal import _thresholds_from_R
                p_yellow, _ = _thresholds_from_R(art, cost_ratio_R, stratum_result.stratum)
            else:
                p_yellow = 0.35
        except Exception:
            p_yellow = 0.35
        p_model = max(p_model, p_yellow + 1e-4)

    # 8d. Hard safety guarantee 2: multi-vital distress floor (all strata).
    #     ≥4 simultaneously abnormal vitals meets SIRS/shock criteria regardless
    #     of stratum. The model may be uncertain on 1-snapshot extremes (sparse
    #     in training) — the rule card must protect those patients.
    #     4 is conservative: SIRS needs 2, but we add margin for noisy sensors.
    _MULTI_VITAL_FLOOR_N = 4
    if p_model is not None and n_abnormal >= _MULTI_VITAL_FLOOR_N:
        try:
            from model.artifact import get_artifact
            art = get_artifact()
            if art is not None:
                from model.conformal import _thresholds_from_R
                p_yellow_mv, _ = _thresholds_from_R(art, cost_ratio_R, stratum_result.stratum)
            else:
                p_yellow_mv = 0.35
        except Exception:
            p_yellow_mv = 0.35
        p_model = max(p_model, p_yellow_mv + 1e-4)

    # 8e. Hard safety guarantee 3: CRITICAL-DERANGEMENT floor -> Red.
    #
    #     Guarantee 2 only lifts to Yellow, which left a real hole: a patient
    #     with HR 190 / RR 44 / SBP 60 / SpO2 72 / GCS 4 scored YELLOW, because
    #     the model's probability for a single extreme snapshot sat between the
    #     Yellow and Red cut points. Single-snapshot extremes are sparse in
    #     training, so the model is genuinely unsure about them — which is
    #     exactly when the rule card, not the model, must decide.
    #
    #     These are individually life-threatening values, not a composite score.
    #     Any ONE of them is peri-arrest physiology in any stratum.
    _CRITICAL_SINGLE_VITAL = {
        "gcs": lambda v: v <= 8,          # unresponsive / airway at risk
        "spo2": lambda v: v < 85,         # severe hypoxaemia
        "bp_sys": lambda v: v < 70,       # decompensated shock
    }
    _CRITICAL_MULTI_N = 6                 # near-total derangement

    critical_reasons: list[str] = []
    for _tr in threshold_results:
        rule = _CRITICAL_SINGLE_VITAL.get(_tr.vital)
        if rule is not None and _tr.value is not None:
            try:
                if rule(float(_tr.value)):
                    critical_reasons.append(f"{_tr.vital}={_tr.value:g}")
            except (TypeError, ValueError):
                pass
    if n_abnormal >= _CRITICAL_MULTI_N:
        critical_reasons.append(f"{n_abnormal}_vitals_abnormal")

    if p_model is not None and critical_reasons:
        try:
            from model.artifact import get_artifact
            art = get_artifact()
            if art is not None:
                from model.conformal import _thresholds_from_R
                _, p_red_crit = _thresholds_from_R(art, cost_ratio_R, stratum_result.stratum)
            else:
                p_red_crit = 0.65
        except Exception:
            p_red_crit = 0.65
        p_model = max(p_model, p_red_crit + 1e-4)

    # 9. Conformal uncertainty (real when p_model available, heuristic otherwise)
    conf_result = compute_confidence(
        calibrated_score=cal_result.calibrated_score,
        uncertainty_inflation=reliability_result.uncertainty_inflation,
        inferred_stratum=stratum_result.inferred,
        stale_reading=stale_any,
        ood_flag=False,
        cost_ratio_R=cost_ratio_R,
        stratum=stratum_result.stratum,
        p_model=p_model,
    )

    # If conformal says abstain → emit AbstentionObject (Invariant 2)
    if conf_result.abstain:
        return AbstentionObject(
            patient_id=record.patient_id,
            band="yellow",
            abstained=True,
            confidence=0.0,
            confidence_reason=conf_result.confidence_reason or "abstention",
            age_stratum=stratum_result.stratum,
            age_stratum_inferred=stratum_result.inferred,
            reliability_discounts_applied=reliability_result.discounts_applied,
            factors_for=factors_for,
            factors_against=factors_against,
            model_version=MODEL_VERSION,
            calibration_version=CALIBRATION_VERSION,
            computed_at=computed_at,
        ), p_model, conf_result

    # 10. Fully-populated ScoreObject
    mv, cv = current_versions()   # picks up artifact versions when loaded
    return ScoreObject(
        patient_id=record.patient_id,
        band=conf_result.band,
        confidence=conf_result.confidence,
        confidence_reason=conf_result.confidence_reason,
        factors_for=factors_for,
        factors_against=factors_against,
        age_stratum=stratum_result.stratum,
        age_stratum_inferred=stratum_result.inferred,
        reliability_discounts_applied=reliability_result.discounts_applied,
        abstained=False,
        model_version=mv,
        calibration_version=cv,
        computed_at=computed_at,
        score_source=score_source,
    ), p_model, conf_result


def score_patient(
    record: PatientRecord,
    cost_ratio_R: float = DEFAULT_COST_RATIO_R,
    now: Optional[datetime.datetime] = None,
    ood_flag: bool = False,
) -> ScoreObject | AbstentionObject:
    """
    Score a patient and return a fully-populated ScoreObject or AbstentionObject.

    This is the main entry-point consumed by the band engine and the API.
    Never returns a partially-populated object (Invariant 2).
    """
    result, _, _ = score_patient_verbose(record, cost_ratio_R, now, ood_flag)
    return result
