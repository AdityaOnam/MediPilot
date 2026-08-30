"""
medipilot-model/backend/api.py

FastAPI application — the interface between this track and Track A/B.

Endpoints:
  POST /score           — Accept a Track A structured record, return ScoreObject
  POST /override        — Accept a clinician override, write audit record
  GET  /queue           — Patient queue sorted by risk × time-waiting
  POST /recheck/{pid}   — Mark recheck complete
  GET  /surge-status    — Current surge state and active cadence policy
  GET  /audit/{pid}     — Audit chain for a patient
  POST /demo/arrival    — Simulate an arrival (for surge demo)

Also exposes demo_cost_ratio_sweep() for the live demo.
"""

from __future__ import annotations

import datetime
import hashlib
import json
from typing import Any, Optional

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from model.risk_model import (
    PatientRecord, ScoreObject, AbstentionObject, score_patient
)
from model.calibration import MODEL_VERSION, CALIBRATION_VERSION
from backend.band_engine import assign_band, AsymmetricAutonomyViolation
from backend.recheck_scheduler import RecheckScheduler, PatientScheduleState
from backend.surge_controller import SurgeController, SurgeState, SurgeViolation
from backend.audit_log import AuditLog, ValidationError


app = FastAPI(
    title="MediPilot Risk Model API",
    description=(
        "Data/Model/Risk track for MediPilot ED triage prototype. "
        "Accepts Track A structured records; emits score objects for Track B."
    ),
    version="0.1.0",
)

# ---------------------------------------------------------------------------
# In-memory state (prototype — replace with DB in production)
# ---------------------------------------------------------------------------
_audit_log = AuditLog()
_scheduler = RecheckScheduler()
_surge_ctrl = SurgeController()
_surge_state = SurgeState()
_patient_states: dict[str, PatientScheduleState] = {}
_scored_patients: dict[str, dict] = {}   # patient_id → last ScoreObject dict
_current_R: float = 2.0   # cost ratio

# ---------------------------------------------------------------------------
# Request / Response schemas
# ---------------------------------------------------------------------------

class VitalReading(BaseModel):
    value: float
    timestamp: str     # ISO-8601
    source: str        # "recheck_station" | "nurse" | "sensor" | etc.
    validity: str = "valid"


class VitalHistoryEntry(BaseModel):
    """A single historical vital reading for trend-feature extraction.

    Format mirrors PatientRecord.vitals_history internally:
      {vital_name: [(value, ts_iso, source, validity), ...]}

    Track A should populate this with all readings accumulated since
    the patient registered — the model's slope/delta features only fire
    when at least 2 readings exist. A single reading silently degrades
    to NaN for those columns (native NaN behaviour, not an error).
    """
    value: float
    timestamp: str   # ISO-8601
    source: str
    validity: str = "valid"


class ScoreRequest(BaseModel):
    patient_id: str
    age_days: Optional[int] = None
    age_known: bool = True
    hr: Optional[VitalReading] = None
    rr: Optional[VitalReading] = None
    bp_sys: Optional[VitalReading] = None
    spo2: Optional[VitalReading] = None
    temp_c: Optional[VitalReading] = None
    gcs: Optional[VitalReading] = None
    pain_score: Optional[VitalReading] = None
    red_flag_observations: list[str] = Field(default_factory=list)
    reliability_flags: dict[str, bool] = Field(default_factory=dict)
    spo2_bias_risk: bool = False
    current_band: Optional[str] = None
    arrived_at: Optional[str] = None
    ood_flag: bool = False
    # Within-encounter history for slope/delta trend features.
    # Keys are vital names; each list is oldest-first.
    # Absent or empty → trend features stay NaN (model trained with 40%
    # history dropout handles this gracefully).
    vitals_history: Optional[dict[str, list[VitalHistoryEntry]]] = None

class OverrideRequest(BaseModel):
    patient_id: str
    clinician_id: str
    clinician_role: str
    clinician_band: str
    reason_code: str
    reason_text: str
    consent_state: dict = Field(default_factory=dict)
    outcome_ref: Optional[str] = None

class RecheckRequest(BaseModel):
    performer: str   # "recheck_station" | "nurse" | "family" | "self_report"

class ArrivalRequest(BaseModel):
    patient_id: str

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _vital_to_tuple(v: Optional[VitalReading]) -> Optional[tuple]:
    if v is None:
        return None
    return (v.value, v.timestamp, v.source, v.validity)


def _history_to_dict(
    h: Optional[dict[str, list[VitalHistoryEntry]]],
) -> Optional[dict]:
    """Convert VitalHistoryEntry lists to the tuple format PatientRecord expects.

    PatientRecord.vitals_history format:
        {vital: [(value, ts_iso, source, validity), ...]}
    """
    if not h:
        return None
    out: dict[str, list[tuple]] = {}
    for vital, entries in h.items():
        if entries:
            out[vital] = [(e.value, e.timestamp, e.source, e.validity)
                          for e in entries]
    return out or None


def _score_to_dict(result: ScoreObject | AbstentionObject) -> dict:
    return result.as_dict()


def _inputs_hash(req: ScoreRequest) -> str:
    raw = req.model_dump_json()
    return hashlib.sha256(raw.encode()).hexdigest()


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@app.post("/score", summary="Score a patient")
def score_endpoint(req: ScoreRequest) -> dict:
    """
    Accept a Track A structured record and return a ScoreObject or AbstentionObject.
    Never returns a partially-populated object (Invariant 2).
    """
    now = datetime.datetime.now(tz=datetime.timezone.utc)

    record = PatientRecord(
        patient_id=req.patient_id,
        age_days=req.age_days,
        age_known=req.age_known,
        hr=_vital_to_tuple(req.hr),
        rr=_vital_to_tuple(req.rr),
        bp_sys=_vital_to_tuple(req.bp_sys),
        spo2=_vital_to_tuple(req.spo2),
        temp_c=_vital_to_tuple(req.temp_c),
        gcs=_vital_to_tuple(req.gcs),
        pain_score=_vital_to_tuple(req.pain_score),
        red_flag_observations=req.red_flag_observations,
        reliability_flags=req.reliability_flags,
        spo2_bias_risk=req.spo2_bias_risk,
        current_band=req.current_band,
        arrived_at=req.arrived_at,
        # B1: wire within-encounter history for slope/delta trend features.
        # features.py::from_patient_record() already reads this field;
        # previously the API never populated it, causing a train/serve gap
        # (RISK_ENGINE.md §5.8, §9.1).
        vitals_history=_history_to_dict(req.vitals_history),
    )

    result = score_patient(record, cost_ratio_R=_current_R, now=now, ood_flag=req.ood_flag)
    result_dict = _score_to_dict(result)

    # Register patient in scheduler if first time
    if req.patient_id not in _patient_states:
        arrived = now
        if req.arrived_at:
            try:
                arrived = datetime.datetime.fromisoformat(req.arrived_at)
                if arrived.tzinfo is None:
                    arrived = arrived.replace(tzinfo=datetime.timezone.utc)
            except Exception:
                pass
        _patient_states[req.patient_id] = PatientScheduleState(
            patient_id=req.patient_id,
            current_band=result_dict["band"],
            last_remeasure_at=now,
            admitted_at=arrived,
            abstained=result_dict.get("abstained", False),
        )

    # Assign band via band engine (enforces Invariant 1)
    state = _patient_states[req.patient_id]
    try:
        assignment = assign_band(
            patient_id=req.patient_id,
            scored_band=result_dict["band"],
            current_band=state.current_band,
            last_human_action=None,  # no human action for model rescores
            reason="model_rescore",
            now=now,
        )
        state.current_band = assignment.new_band
    except AsymmetricAutonomyViolation:
        # Model tried to lower band without human action — keep current band
        result_dict["band"] = state.current_band
        result_dict["confidence_reason"] = (
            (result_dict.get("confidence_reason") or "") +
            "; band_held_autonomous_deescalation_blocked"
        )

    _scored_patients[req.patient_id] = result_dict
    return result_dict


@app.post("/override", summary="Clinician override")
def override_endpoint(req: OverrideRequest) -> dict:
    """
    Accept a clinician override. Writes a complete §9 audit record.
    Invariant 6: reason_text is required — empty string is rejected.
    """
    now = datetime.datetime.now(tz=datetime.timezone.utc)

    last_score = _scored_patients.get(req.patient_id, {})
    system_band = last_score.get("band", "yellow")
    score_val = last_score.get("confidence", 0.0)
    confidence_val = last_score.get("confidence", 0.0)
    factors_shown = last_score.get("factors_for", []) + last_score.get("factors_against", [])
    model_ver = last_score.get("model_version", MODEL_VERSION)
    cal_ver = last_score.get("calibration_version", CALIBRATION_VERSION)
    inputs_hash_val = last_score.get("inputs_hash", "")

    if not inputs_hash_val:
        inputs_hash_val = hashlib.sha256(json.dumps(last_score, default=str).encode()).hexdigest()

    try:
        record = _audit_log.record_override(
            patient_id=req.patient_id,
            clinician_id=req.clinician_id,
            clinician_role=req.clinician_role,
            system_band=system_band,
            clinician_band=req.clinician_band,
            reason_code=req.reason_code,
            reason_text=req.reason_text,
            score=score_val,
            confidence=confidence_val,
            factors_shown=factors_shown,
            inputs_hash=inputs_hash_val,
            model_version=model_ver,
            calibration_version=cal_ver,
            consent_state=req.consent_state,
            outcome_ref=req.outcome_ref,
            now=now,
        )
    except ValidationError as e:
        raise HTTPException(status_code=422, detail=str(e))

    # Apply band change via band engine (human action attached)
    state = _patient_states.get(req.patient_id)
    if state:
        try:
            assignment = assign_band(
                patient_id=req.patient_id,
                scored_band=req.clinician_band,
                current_band=state.current_band,
                last_human_action=record.record_hash,
                reason=f"clinician_override:{req.reason_code}",
                now=now,
            )
            state.current_band = assignment.new_band
        except AsymmetricAutonomyViolation as e:
            raise HTTPException(status_code=409, detail=str(e))

    return {"status": "recorded", "record_hash": record.record_hash, "direction": record.direction}


@app.get("/queue", summary="Patient queue")
def queue_endpoint() -> list[dict]:
    """
    Return the current patient queue sorted by risk × time-waiting.
    Alerts are never suppressed.
    """
    now = datetime.datetime.now(tz=datetime.timezone.utc)
    patients = []
    for pid, last_score in _scored_patients.items():
        state = _patient_states.get(pid)
        time_waiting_s = 0
        if state:
            time_waiting_s = (now - state.admitted_at).total_seconds()
        patients.append({
            "patient_id": pid,
            "band": last_score.get("band", "yellow"),
            "risk_score": 1.0 - last_score.get("confidence", 0.5),
            "confidence": last_score.get("confidence", 0.5),
            "time_waiting_s": time_waiting_s,
            "abstained": last_score.get("abstained", False),
            "age_stratum": last_score.get("age_stratum", "unknown"),
        })
    return _surge_ctrl.rank_alerts(patients)


@app.post("/recheck/{patient_id}", summary="Mark recheck complete")
def recheck_endpoint(patient_id: str, req: RecheckRequest) -> dict:
    """Mark a re-measurement as completed."""
    now = datetime.datetime.now(tz=datetime.timezone.utc)
    state = _patient_states.get(patient_id)
    if not state:
        raise HTTPException(status_code=404, detail=f"Patient {patient_id} not found")

    accepted, reason = _scheduler.complete_recheck(state, req.performer, now)
    return {"accepted": accepted, "reason": reason}


@app.get("/surge-status", summary="Surge status")
def surge_status_endpoint() -> dict:
    """Return current surge mode, trigger, and active cadence policy."""
    return {
        "in_surge": _surge_state.in_surge,
        "current_arrival_rate_per_hour": _surge_state.current_arrival_rate,
        "active_policy": _surge_ctrl.current_policy(_surge_state),
        "log_tail": [e.as_dict() for e in _surge_state.log[-5:]],
    }


@app.post("/demo/arrival", summary="Simulate patient arrival (surge demo)")
def demo_arrival(req: ArrivalRequest) -> dict:
    """Simulate an arrival for surge detection demo."""
    now = datetime.datetime.now(tz=datetime.timezone.utc)
    _surge_ctrl.record_arrival(_surge_state, now)
    return {
        "patient_id": req.patient_id,
        "in_surge": _surge_state.in_surge,
        "rate_per_hour": _surge_state.current_arrival_rate,
    }


@app.get("/audit/{patient_id}", summary="Audit chain for a patient")
def audit_endpoint(patient_id: str) -> dict:
    """Return all override records for a patient and chain integrity status."""
    records = _audit_log.get_patient_records(patient_id)
    chain_ok, chain_msg = _audit_log.verify_chain()
    return {
        "patient_id": patient_id,
        "records": [r.as_dict() for r in records],
        "chain_integrity": {"ok": chain_ok, "message": chain_msg},
    }


# ---------------------------------------------------------------------------
# Demo: cost ratio sweep (for live demo §10)
# ---------------------------------------------------------------------------

def demo_cost_ratio_sweep(
    patient_records: Optional[list[PatientRecord]] = None,
    R_values: Optional[list[float]] = None,
) -> None:
    """
    Sweep cost ratio R from 1.0 to 3.0 and show how the queue re-sorts.
    Demonstrates that the system is deliberately biased toward escalation
    under uncertainty.
    """
    if R_values is None:
        R_values = [1.0, 1.5, 2.0, 2.5, 3.0]

    if patient_records is None:
        # Create a small demo set with borderline patients
        from model.risk_model import PatientRecord
        import datetime
        now = datetime.datetime.now(tz=datetime.timezone.utc)
        now_iso = now.isoformat()
        patient_records = [
            PatientRecord(
                patient_id="DEMO-A",
                age_days=365*45,
                hr=(88, now_iso, "recheck_station", "valid"),
                rr=(19, now_iso, "recheck_station", "valid"),
                bp_sys=(128, now_iso, "recheck_station", "valid"),
                spo2=(96, now_iso, "recheck_station", "valid"),
                temp_c=(37.1, now_iso, "recheck_station", "valid"),
                gcs=(15, now_iso, "recheck_station", "valid"),
                pain_score=(4, now_iso, "recheck_station", "valid"),
            ),
            PatientRecord(
                patient_id="DEMO-B",
                age_days=365*72,
                hr=(80, now_iso, "recheck_station", "valid"),
                rr=(18, now_iso, "recheck_station", "valid"),
                bp_sys=(138, now_iso, "recheck_station", "valid"),
                spo2=(95, now_iso, "recheck_station", "valid"),
                temp_c=(38.5, now_iso, "recheck_station", "valid"),
                gcs=(14, now_iso, "recheck_station", "valid"),
                pain_score=(3, now_iso, "recheck_station", "valid"),
            ),
        ]

    print("\n=== Cost Ratio R Sweep Demo ===")
    print(f"{'R':>5} | {'Patient':>10} | {'Band':>8} | {'Confidence':>12}")
    print("-" * 45)

    for R in R_values:
        for pr in patient_records:
            result = score_patient(pr, cost_ratio_R=R)
            result_dict = result.as_dict()
            print(
                f"{R:>5.1f} | {pr.patient_id:>10} | "
                f"{result_dict['band']:>8} | "
                f"{result_dict['confidence']:>12.4f}"
            )
        print()

    print("=== End Sweep ===\n")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("backend.api:app", host="0.0.0.0", port=8000, reload=True)
