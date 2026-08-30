"""
Corpus join: backend trajectories + frontend presentation metadata.

CASE_MAP joins on case_id. 13 clean joins; 7 unjoined frontend records
get a synthesised flat trajectory from their static measurements.
"""

from __future__ import annotations

import json
import pathlib
import datetime
from dataclasses import dataclass, field
from typing import Optional, Any

from model.risk_model import PatientRecord

_CORPUS_PATH = pathlib.Path(__file__).parent.parent.parent / "data" / "corpus_20.json"

# Backend case_id → frontend encounter_id
CASE_MAP: dict[str, str] = {
    "deteriorates_while_waiting": "P-05",
    "age_pair_paediatric": "P-03",
    "age_pair_geriatric": "P-04",
    "ambiguous_epigastric_pain": "P-07",
    "spo2_bias_dark_skin": "P-08",
    "stale_vitals_3h": "P-09",
    "zero_history": "P-11",
    "ood_abstention": "P-15",
    "nurse_override_full_record": "P-14",
    "missed_rechecks_under_surge": "P-20",
    "geriatric_silent_mi": "P-06",
    "geriatric_communication_barrier": "P-13",
    "adolescent_obstetric_redflag": "P-18",
    "green_baseline": "P-02",
}

# Reverse map for lookups
_FE_TO_CASE = {v: k for k, v in CASE_MAP.items()}

# Frontend presentation metadata — ported from lib/seed/corpus.ts
_FE_META: dict[str, dict] = {
    "P-01": dict(token="201", displayName="Rajesh Kumar", ageYears=52, sex="M",
                 chiefComplaint="Crushing chest pain, diaphoretic, radiating to left arm",
                 arrivalMode="ambulance", humanAssignedBand="RED",
                 assisted=True, medicalInfoConsent=True, hasPriorRecord=False),
    "P-02": dict(token="202", displayName="Ananya Sharma", ageYears=28, sex="F",
                 chiefComplaint="Minor laceration on forearm, controlled bleeding",
                 arrivalMode="walk-in", humanAssignedBand=None,
                 assisted=True, medicalInfoConsent=True, hasPriorRecord=False),
    "P-03": dict(token="203", displayName="Arjun Mehta", ageYears=3, sex="M",
                 chiefComplaint="38.5°C fever, tachypnoeic, poor feeding since morning",
                 arrivalMode="walk-in", humanAssignedBand=None,
                 assisted=True, medicalInfoConsent=True, hasPriorRecord=False),
    "P-04": dict(token="204", displayName="Kamala Devi", ageYears=75, sex="F",
                 chiefComplaint="38.5°C fever, mildly confused, unremarkable HR",
                 arrivalMode="walk-in", humanAssignedBand=None,
                 assisted=True, medicalInfoConsent=True, hasPriorRecord=False),
    "P-05": dict(token="205", displayName="Vikram Patel", ageYears=45, sex="M",
                 chiefComplaint='Mild chest discomfort, "probably just acidity"',
                 arrivalMode="walk-in", humanAssignedBand=None,
                 assisted=True, medicalInfoConsent=True, hasPriorRecord=False),
    "P-06": dict(token="206", displayName="Suresh Rao", ageYears=78, sex="M",
                 chiefComplaint="Confusion, lethargy, no fever, no localising signs",
                 arrivalMode="walk-in", humanAssignedBand=None,
                 assisted=True, medicalInfoConsent=True, hasPriorRecord=False),
    "P-07": dict(token="207", displayName="Priya Nair", ageYears=55, sex="F",
                 chiefComplaint="Epigastric burning, nausea, could be gastritis or inferior MI",
                 arrivalMode="walk-in", humanAssignedBand=None,
                 assisted=True, medicalInfoConsent=True, hasPriorRecord=False),
    "P-08": dict(token="208", displayName="Dayo Okonkwo", ageYears=34, sex="M",
                 chiefComplaint="Dyspnoea, distressed appearance, SpO2 reads 96%",
                 arrivalMode="walk-in", humanAssignedBand=None,
                 assisted=True, medicalInfoConsent=True, hasPriorRecord=False),
    "P-09": dict(token="209", displayName="Meena Gupta", ageYears=42, sex="F",
                 chiefComplaint="Abdominal pain, vitals taken 3 hours ago",
                 arrivalMode="walk-in", humanAssignedBand=None,
                 assisted=True, medicalInfoConsent=True, hasPriorRecord=False),
    "P-10": dict(token="210", displayName="Anil Verma", ageYears=60, sex="M",
                 chiefComplaint="Chest tightness, cardiac monitor dropped out",
                 arrivalMode="walk-in", humanAssignedBand=None,
                 assisted=True, medicalInfoConsent=True, hasPriorRecord=False),
    "P-11": dict(token="211", displayName="Farhan Sheikh", ageYears=38, sex="M",
                 chiefComplaint="Severe headache, photophobia, neck stiffness",
                 arrivalMode="walk-in", humanAssignedBand=None,
                 assisted=True, medicalInfoConsent=True, hasPriorRecord=False),
    "P-12": dict(token="212", displayName="Lakshmi Iyer", ageYears=62, sex="F",
                 chiefComplaint="Recurrent chest pain, known CAD, on anticoagulants",
                 arrivalMode="walk-in", humanAssignedBand=None,
                 assisted=True, medicalInfoConsent=True, hasPriorRecord=True),
    "P-13": dict(token="213", displayName="Thanh Nguyen", ageYears=50, sex="M",
                 chiefComplaint="Abdominal distension, speaks neither Hindi nor English",
                 arrivalMode="walk-in", humanAssignedBand=None,
                 assisted=True, medicalInfoConsent=True, hasPriorRecord=False),
    "P-14": dict(token="214", displayName="Ravi Shankar", ageYears=48, sex="M",
                 chiefComplaint="Abdominal pain, initially Yellow, nurse finds rigid abdomen",
                 arrivalMode="walk-in", humanAssignedBand="YELLOW",
                 assisted=True, medicalInfoConsent=True, hasPriorRecord=False),
    "P-15": dict(token="215", displayName="Meera Nair", ageYears=29, sex="F",
                 chiefComplaint="Unusual presentation unlike anything in local distribution",
                 arrivalMode="walk-in", humanAssignedBand=None,
                 assisted=True, medicalInfoConsent=True, hasPriorRecord=False),
    "P-16": dict(token="216", displayName=None, ageYears=None, sex=None,
                 chiefComplaint="Found unresponsive near entrance, no ID, age unknown",
                 arrivalMode="brought-by-bystander", humanAssignedBand="RED",
                 assisted=False, medicalInfoConsent=True, hasPriorRecord=False),
    "P-17": dict(token="217", displayName="Deepa Iyer", ageYears=35, sex="F",
                 chiefComplaint="Palpitations, anxiety, declines to share medical history",
                 arrivalMode="walk-in", humanAssignedBand=None,
                 assisted=True, medicalInfoConsent=False, hasPriorRecord=False),
    "P-18": dict(token="218", displayName="Sunita Devi", ageYears=26, sex="F",
                 chiefComplaint="Active labour, contractions 3 min apart, vitals unremarkable",
                 arrivalMode="ambulance", humanAssignedBand="RED",
                 assisted=True, medicalInfoConsent=True, hasPriorRecord=False),
    "P-19": dict(token="219", displayName="Harish Reddy", ageYears=68, sex="M",
                 chiefComplaint='"I\'m fine" — but tachycardic, hypertensive, diaphoretic',
                 arrivalMode="walk-in", humanAssignedBand=None,
                 assisted=True, medicalInfoConsent=True, hasPriorRecord=False),
    "P-20": dict(token="220", displayName="Pooja Singh", ageYears=32, sex="F",
                 chiefComplaint="Ankle sprain, Green, but two rechecks missed under surge",
                 arrivalMode="walk-in", humanAssignedBand=None,
                 assisted=True, medicalInfoConsent=True, hasPriorRecord=False),
}

# Static vitals for unjoined frontend records (from corpus.ts)
_FE_STATIC_VITALS: dict[str, dict[str, float | None]] = {
    "P-01": {"hr": 112, "rr": 24, "bp_sys": 168, "spo2": 94, "temp_c": 37.1, "gcs": None, "pain_score": None},
    "P-10": {"hr": None, "rr": 22, "bp_sys": 148, "spo2": None, "temp_c": None, "gcs": None, "pain_score": None},
    "P-12": {"hr": 80, "rr": 18, "bp_sys": 138, "spo2": 97, "temp_c": 36.9, "gcs": None, "pain_score": None},
    "P-16": {"hr": 56, "rr": 10, "bp_sys": 84, "spo2": 88, "temp_c": None, "gcs": 6, "pain_score": None},
    "P-17": {"hr": 102, "rr": 18, "bp_sys": 128, "spo2": 99, "temp_c": 36.7, "gcs": None, "pain_score": None},
    "P-19": {"hr": 118, "rr": 24, "bp_sys": 178, "spo2": 93, "temp_c": 37.0, "gcs": None, "pain_score": 2},
}


@dataclass
class SeedRecord:
    encounter_id: str
    token: str
    display_name: Optional[str]
    age_years: Optional[float]
    age_days: Optional[int]
    stratum: str
    stratum_inferred: bool
    sex: Optional[str]
    chief_complaint: str
    arrival_mode: str
    human_assigned_band: Optional[str]
    arrived_at: str
    assisted: bool
    medical_info_consent: bool
    has_prior_record: bool
    red_flag_observations: list[str]
    reliability_flags: dict[str, bool]
    force_ood: bool
    spo2_bias_risk: bool
    trajectory: dict[str, list[dict]]
    stale_vitals_hours: float
    zero_history: bool


def _load_backend_corpus() -> dict[str, dict]:
    with open(_CORPUS_PATH, encoding="utf-8") as f:
        data = json.load(f)
    return {rec["case_id"]: rec for rec in data}


def load_seed(sim_base_iso: str) -> list[SeedRecord]:
    """Load and join the 20-record corpus. sim_base_iso is the sim T=0 timestamp."""
    be_corpus = _load_backend_corpus()
    records: list[SeedRecord] = []

    for eid in [f"P-{i:02d}" for i in range(1, 21)]:
        meta = _FE_META[eid]
        case_id = _FE_TO_CASE.get(eid)
        be_rec = be_corpus.get(case_id) if case_id else None

        # Age
        age_years = meta.get("ageYears")
        if be_rec and be_rec.get("age_days") is not None:
            age_days = be_rec["age_days"]
        elif age_years is not None:
            age_days = int(age_years * 365.25)
        else:
            age_days = None

        stratum_inferred = age_days is None
        stratum = be_rec["stratum"] if be_rec else ("adult" if age_days is None else _infer_stratum(age_days))

        # Red flags — apply conflict fixes
        red_flags = list(be_rec.get("red_flag_observations", [])) if be_rec else []
        if eid == "P-03" and "infant_not_feeding_floppy_inconsolable" in red_flags:
            red_flags.remove("infant_not_feeding_floppy_inconsolable")

        # Reliability flags — apply conflict fixes
        rel_flags = dict(be_rec.get("reliability_flags", {})) if be_rec else {}
        if eid == "P-04" and "stoic_presentation" in rel_flags:
            del rel_flags["stoic_presentation"]
        if eid == "P-19":
            rel_flags["stoic_presentation"] = True

        # SpO2 bias
        spo2_bias = False
        if be_rec:
            spo2_bias = be_rec.get("patient_flags", {}).get("spo2_bias_risk", False)
        if eid == "P-08":
            spo2_bias = True

        # Trajectory
        if be_rec and "trajectory" in be_rec:
            traj = be_rec["trajectory"]
            series = traj.get("series", traj)
            trajectory = {}
            for vital, readings in series.items():
                if isinstance(readings, list) and readings:
                    trajectory[vital] = readings
        else:
            trajectory = _synthesise_flat_trajectory(eid, sim_base_iso)

        force_ood = be_rec.get("force_ood", False) if be_rec else False
        if eid == "P-15":
            force_ood = True

        stale_hours = be_rec.get("stale_vitals_hours", 0) if be_rec else 0
        if eid == "P-09":
            stale_hours = 3.0
        zero_hist = be_rec.get("zero_history", False) if be_rec else False
        if eid == "P-11":
            zero_hist = True

        human_band = meta.get("humanAssignedBand")

        records.append(SeedRecord(
            encounter_id=eid,
            token=meta["token"],
            display_name=meta.get("displayName"),
            age_years=age_years,
            age_days=age_days,
            stratum=stratum,
            stratum_inferred=stratum_inferred,
            sex=meta.get("sex"),
            chief_complaint=meta["chiefComplaint"],
            arrival_mode=meta.get("arrivalMode", "walk-in"),
            human_assigned_band=human_band,
            arrived_at=sim_base_iso,
            assisted=meta.get("assisted", True),
            medical_info_consent=meta.get("medicalInfoConsent", True),
            has_prior_record=meta.get("hasPriorRecord", False),
            red_flag_observations=red_flags,
            reliability_flags=rel_flags,
            force_ood=force_ood,
            spo2_bias_risk=spo2_bias,
            trajectory=trajectory,
            stale_vitals_hours=stale_hours,
            zero_history=zero_hist,
        ))

    return records


def _infer_stratum(age_days: int) -> str:
    if age_days < 28:
        return "neonate"
    if age_days < 365:
        return "infant"
    if age_days < 365 * 12:
        return "child"
    if age_days < 365 * 18:
        return "adolescent"
    if age_days < 365 * 65:
        return "adult"
    return "geriatric"


def _synthesise_flat_trajectory(eid: str, t0_iso: str) -> dict[str, list[dict]]:
    """Build a flat (constant-value) trajectory for unjoined frontend records."""
    static = _FE_STATIC_VITALS.get(eid)
    if not static:
        return {}

    t0 = datetime.datetime.fromisoformat(t0_iso)
    trajectory: dict[str, list[dict]] = {}
    n_steps = 37

    for vital, value in static.items():
        if value is None:
            continue
        readings = []
        for i in range(n_steps):
            ts = t0 + datetime.timedelta(minutes=i * 5)
            readings.append({
                "value": value,
                "timestamp": ts.isoformat(),
                "source": "recheck_station",
                "validity": "valid",
                "vital": vital,
            })
        trajectory[vital] = readings

    return trajectory


def record_at(
    seed: SeedRecord,
    k_step: int,
    current_band: Optional[str],
    sim_now: datetime.datetime,
) -> PatientRecord:
    """
    Build a PatientRecord at trajectory step k_step.

    Slices series[:k_step+1], takes the last as current and the whole
    slice as vitals_history for trend features.

    Timestamps are rebased: trajectory step 0 maps to the encounter's
    arrived_at, each subsequent step is +5 min. This keeps readings
    fresh relative to sim_now regardless of the corpus's original dates.
    """
    arrived = datetime.datetime.fromisoformat(seed.arrived_at)
    if arrived.tzinfo is None:
        arrived = arrived.replace(tzinfo=datetime.timezone.utc)

    def _rebase_ts(step_idx: int) -> str:
        return (arrived + datetime.timedelta(minutes=step_idx * 5)).isoformat()

    def _vital_tuple(readings: list[dict], k: int):
        if k < 0 or not readings:
            return None
        idx = min(k, len(readings) - 1)
        r = readings[idx]
        return (r["value"], _rebase_ts(idx), r["source"], r.get("validity", "valid"))

    def _vital_history(readings: list[dict], k: int):
        if not readings:
            return None
        slice_end = min(k + 1, len(readings))
        if slice_end <= 0:
            return None
        return [
            (r["value"], _rebase_ts(i), r["source"], r.get("validity", "valid"))
            for i, r in enumerate(readings[:slice_end])
        ]

    traj = seed.trajectory
    vitals_history: dict[str, list] = {}
    vitals: dict[str, Any] = {}

    for vital_name in ["hr", "rr", "bp_sys", "spo2", "temp_c", "gcs", "pain_score"]:
        readings = traj.get(vital_name, [])
        vt = _vital_tuple(readings, k_step)
        if vt is not None:
            vitals[vital_name] = vt
        hist = _vital_history(readings, k_step)
        if hist and not seed.zero_history:
            vitals_history[vital_name] = hist

    # Handle stale vitals: shift timestamps back
    if seed.stale_vitals_hours > 0:
        shift = datetime.timedelta(hours=seed.stale_vitals_hours)
        for v_name in list(vitals.keys()):
            val, ts, src, validity = vitals[v_name]
            old_ts = datetime.datetime.fromisoformat(ts)
            new_ts = old_ts - shift
            vitals[v_name] = (val, new_ts.isoformat(), src, validity)

    return PatientRecord(
        patient_id=seed.encounter_id,
        age_days=seed.age_days,
        age_known=seed.age_days is not None,
        hr=vitals.get("hr"),
        rr=vitals.get("rr"),
        bp_sys=vitals.get("bp_sys"),
        spo2=vitals.get("spo2"),
        temp_c=vitals.get("temp_c"),
        gcs=vitals.get("gcs"),
        pain_score=vitals.get("pain_score"),
        vitals_history=vitals_history or None,
        red_flag_observations=seed.red_flag_observations,
        reliability_flags=seed.reliability_flags,
        spo2_bias_risk=seed.spo2_bias_risk,
        current_band=current_band,
        arrived_at=seed.arrived_at,
    )
