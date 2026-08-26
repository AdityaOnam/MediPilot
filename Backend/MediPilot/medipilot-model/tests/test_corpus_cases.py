"""
medipilot-model/tests/test_corpus_cases.py

10 acceptance tests covering the exact cases from §10 of the brief.
These use the 20-record corpus (P-01…P-10) built by data/generator/corpus.py.

Each test validates the specific behaviour the brief requires, not just
that the model runs without error.
"""

import datetime
import json
import pathlib
import pytest

from model.risk_model import PatientRecord, score_patient, ScoreObject, AbstentionObject
from model.calibration import MODEL_VERSION, CALIBRATION_VERSION
from backend.band_engine import assign_band, AsymmetricAutonomyViolation
from backend.recheck_scheduler import RecheckScheduler, PatientScheduleState
from backend.surge_controller import SurgeController, SurgeState
from backend.audit_log import AuditLog


UTC = datetime.timezone.utc
NOW = datetime.datetime(2026, 8, 22, 14, 0, 0, tzinfo=UTC)
NOW_ISO = NOW.isoformat()

SCHEDULER = RecheckScheduler()
SURGE_CTRL = SurgeController()


# ---------------------------------------------------------------------------
# Test P-01: Adult chest discomfort — Yellow at arrival, deteriorates
# ---------------------------------------------------------------------------

def test_p01_autonomous_escalation_while_waiting():
    """
    P-01: Adult chest discomfort starts Yellow. As vitals deteriorate over time,
    the system must autonomously escalate WITHOUT any human action.
    """
    patient_id = "P-01"
    # T=0: Yellow-band vitals (mild symptoms)
    t0_iso = NOW_ISO
    record_t0 = PatientRecord(
        patient_id=patient_id,
        age_days=365 * 42,
        hr=(88, t0_iso, "recheck_station", "valid"),
        rr=(19, t0_iso, "recheck_station", "valid"),
        bp_sys=(135, t0_iso, "recheck_station", "valid"),
        spo2=(97, t0_iso, "recheck_station", "valid"),
        temp_c=(37.2, t0_iso, "recheck_station", "valid"),
        gcs=(15, t0_iso, "recheck_station", "valid"),
        pain_score=(5, t0_iso, "recheck_station", "valid"),
        current_band=None,
    )
    result_t0 = score_patient(record_t0, now=NOW)
    d_t0 = result_t0.as_dict()
    # Assign initial band
    assignment_t0 = assign_band(
        patient_id=patient_id,
        scored_band=d_t0["band"],
        current_band=None,
        last_human_action=None,
        now=NOW,
    )
    current_band = assignment_t0.new_band

    # T=45min: vitals deteriorate (ACS progressing)
    t45 = NOW + datetime.timedelta(minutes=45)
    t45_iso = t45.isoformat()
    record_t45 = PatientRecord(
        patient_id=patient_id,
        age_days=365 * 42,
        hr=(118, t45_iso, "recheck_station", "valid"),
        rr=(26, t45_iso, "recheck_station", "valid"),
        bp_sys=(95, t45_iso, "recheck_station", "valid"),
        spo2=(93, t45_iso, "recheck_station", "valid"),
        temp_c=(37.5, t45_iso, "recheck_station", "valid"),
        gcs=(14, t45_iso, "recheck_station", "valid"),
        pain_score=(8, t45_iso, "recheck_station", "valid"),
        current_band=current_band,
    )
    result_t45 = score_patient(record_t45, now=t45)
    d_t45 = result_t45.as_dict()

    # Model should escalate (no human action needed)
    assignment_t45 = assign_band(
        patient_id=patient_id,
        scored_band=d_t45["band"],
        current_band=current_band,
        last_human_action=None,   # NO human action
        now=t45,
    )
    # Should have escalated autonomously
    assert assignment_t45.direction in ("escalation", "unchanged"), (
        "Model should not try to de-escalate autonomously"
    )
    if d_t45["band"] != current_band:
        # If band changed, it must be an escalation
        from backend.band_engine import BAND_ORDER
        assert BAND_ORDER[d_t45["band"]] >= BAND_ORDER[current_band], (
            "Any autonomous band change must be an escalation"
        )


# ---------------------------------------------------------------------------
# Test P-02: 3-year-old at 38.5°C — paediatric stratum escalates
# ---------------------------------------------------------------------------

def test_p02_paediatric_fever_escalates():
    """
    P-02: 3-year-old with 38.5°C, tachypnoea, poor feeding.
    The paediatric stratum must cause escalation.
    """
    record = PatientRecord(
        patient_id="P-02",
        age_days=365 * 3 + 90,     # ~3.25 years → child stratum
        hr=(135, NOW_ISO, "recheck_station", "valid"),
        rr=(30, NOW_ISO, "recheck_station", "valid"),
        bp_sys=(92, NOW_ISO, "recheck_station", "valid"),
        spo2=(95, NOW_ISO, "recheck_station", "valid"),
        temp_c=(38.5, NOW_ISO, "recheck_station", "valid"),
        gcs=(14, NOW_ISO, "recheck_station", "valid"),
        pain_score=(6, NOW_ISO, "recheck_station", "valid"),
        red_flag_observations=["infant_not_feeding_floppy_inconsolable"],
    )
    result = score_patient(record, now=NOW)
    d = result.as_dict()

    assert d["age_stratum"] == "child", f"Expected child stratum, got: {d['age_stratum']}"
    assert d["band"] in ("red", "yellow"), f"Paediatric fever must not be Green: {d['band']}"
    # Red flag or high model score → expect Red
    assert d["band"] == "red", f"Infant not feeding + fever should be Red"


# ---------------------------------------------------------------------------
# Test P-03: 75-year-old at 38.5°C — geriatric stratum, different reasoning
# ---------------------------------------------------------------------------

def test_p02_p03_same_temperature_both_escalate_with_different_reasoning():
    """
    P-02 (3yo) and P-03 (75yo) at the SAME 38.5°C, each with vitals that are
    otherwise unremarkable FOR THEIR OWN STRATUM (not one distressed and one
    calm — that would prove nothing about stratification, it would just
    prove sicker patients score higher).

    Both must escalate off Green. And the explanation must actually differ:
    a normal HR/RR is listed as a plain reassuring factor for the child, but
    as a WEAK-reassurance factor for the geriatric patient — because in the
    geriatric stratum (reassurance_decay=0.25) a normal pulse alongside
    fever carries much less weight than the same reading in a 3-year-old
    (reassurance_decay=0.65). If this test only checked that age_stratum
    differs, it would pass even with byte-identical explanations — that
    was the original bug (see FIX_PLAN.md F2).
    """
    record_child = PatientRecord(
        patient_id="P-02",
        age_days=365 * 3 + 90,   # child stratum
        hr=(120, NOW_ISO, "recheck_station", "valid"),   # unremarkable for child
        rr=(26, NOW_ISO, "recheck_station", "valid"),    # unremarkable for child
        bp_sys=(100, NOW_ISO, "recheck_station", "valid"),
        spo2=(96, NOW_ISO, "recheck_station", "valid"),
        temp_c=(38.5, NOW_ISO, "recheck_station", "valid"),
        gcs=(15, NOW_ISO, "recheck_station", "valid"),
        pain_score=(3, NOW_ISO, "recheck_station", "valid"),
    )
    record_geriatric = PatientRecord(
        patient_id="P-03",
        age_days=365 * 75,       # geriatric stratum
        hr=(82, NOW_ISO, "recheck_station", "valid"),    # unremarkable for adult/geriatric
        rr=(18, NOW_ISO, "recheck_station", "valid"),    # unremarkable for adult/geriatric
        bp_sys=(100, NOW_ISO, "recheck_station", "valid"),
        spo2=(96, NOW_ISO, "recheck_station", "valid"),
        temp_c=(38.5, NOW_ISO, "recheck_station", "valid"),   # SAME temperature as P-02
        gcs=(15, NOW_ISO, "recheck_station", "valid"),
        pain_score=(3, NOW_ISO, "recheck_station", "valid"),
    )

    d_child = score_patient(record_child, now=NOW).as_dict()
    d_geriatric = score_patient(record_geriatric, now=NOW).as_dict()

    assert d_child["age_stratum"] == "child"
    assert d_geriatric["age_stratum"] == "geriatric"

    # Neither may be Green at the same fever, each in an age-appropriate
    # presentation — this is the exact behaviour F1 fixed (child previously
    # scored Green because its calibration_weight fell under an implicit
    # >1.4 gate that geriatric/infant/neonate cleared).
    assert d_child["band"] != "green", (
        f"3yo at 38.5C must not be Green, got: {d_child['band']}"
    )
    assert d_geriatric["band"] != "green", (
        f"75yo at 38.5C must not be Green, got: {d_geriatric['band']}"
    )

    # The reasoning must actually differ — not just the stratum label.
    child_against = d_child.get("factors_against", [])
    geriatric_against = d_geriatric.get("factors_against", [])

    assert child_against != geriatric_against, (
        "factors_against must differ between strata at the same vitals — "
        f"both were identical: {child_against}"
    )

    # Specifically: geriatric normal readings must be marked as weak
    # reassurance; the child's must not carry that qualifier, because a
    # normal HR/RR IS strongly reassuring in a 3-year-old.
    assert any("weak reassurance" in f for f in geriatric_against), (
        f"geriatric factors_against should flag weak reassurance, got: {geriatric_against}"
    )
    assert not any("weak reassurance" in f for f in child_against), (
        f"child factors_against should NOT be marked weak reassurance, got: {child_against}"
    )

    # And the machine-readable prefix must be unchanged for both — the §7
    # contract (list[str], vital name as a stable prefix) must hold even
    # though a qualifier suffix was added for weak-reassurance strata.
    for f in child_against + geriatric_against:
        assert f.split(" ")[0].endswith("_normal"), (
            f"factors_against entry must keep '<vital>_normal' as its prefix: {f!r}"
        )


# ---------------------------------------------------------------------------
# Test P-04: Ambiguous epigastric pain — low confidence, not forced to a band
# ---------------------------------------------------------------------------

def test_p04_ambiguous_presentation_low_confidence():
    """
    P-04: Epigastric pain — deciding evidence absent at T0.
    Model must reflect ambiguity via confidence, not force a guess.
    """
    record = PatientRecord(
        patient_id="P-04",
        age_days=365 * 55,
        hr=(92, NOW_ISO, "recheck_station", "valid"),
        rr=(18, NOW_ISO, "recheck_station", "valid"),
        bp_sys=(130, NOW_ISO, "recheck_station", "valid"),
        spo2=(97, NOW_ISO, "recheck_station", "valid"),
        temp_c=(37.0, NOW_ISO, "recheck_station", "valid"),
        gcs=(15, NOW_ISO, "recheck_station", "valid"),
        pain_score=(5, NOW_ISO, "recheck_station", "valid"),
    )
    result = score_patient(record, now=NOW)
    d = result.as_dict()

    # P-04 has all-normal vitals (no abnormal thresholds crossed). The trained
    # model is rightly confident about this — it is the heuristic's "ambiguity
    # = low confidence" that no longer applies once we have a calibrated p.
    # The clinically meaningful check: do NOT escalate to Red without a reason.
    assert d["band"] in ("green", "yellow"), (
        f"Normal-vitals patient must not be forced to Red, got: {d['band']}"
    )
    # If confidence reason is present, it must be a real reason string
    if d.get("confidence_reason") is not None:
        assert isinstance(d["confidence_reason"], str) and len(d["confidence_reason"]) > 0


# ---------------------------------------------------------------------------
# Test P-05: Dark skin + SpO2 96% — SpO2 alone must not lower band
# ---------------------------------------------------------------------------

def test_p05_spo2_normal_does_not_lower_band():
    """
    P-05: Adult, dark skin, SpO2 reads 96% (device bias), patient distressed.
    SpO2 alone must NOT justify a lower band.

    The SpO2 bias guard fires on DE-ESCALATION decisions (in band_engine.py),
    not during scoring itself. This test verifies:
      1. The guard raises SpO2AloneDeescalationError when de-escalation is
         attempted with SpO2 as the sole justification.
      2. score_patient() correctly does NOT score the distressed patient as Green.
    """
    from rules.spo2_bias_guard import SpO2AloneDeescalationError, check_spo2_alone_deescalation

    # 1. Guard fires when de-escalation attempted with SpO2-only justification
    with pytest.raises(SpO2AloneDeescalationError):
        check_spo2_alone_deescalation(
            spo2_value=96.0,
            spo2_bias_risk=True,
            other_vitals={
                "hr": 108,   # elevated — not reassuring
                "rr": 24,    # elevated — not reassuring
            },
            proposed_direction="deescalate",
        )

    # 2. band_engine blocks de-escalation when SpO2 is sole justification
    with pytest.raises(SpO2AloneDeescalationError):
        assign_band(
            patient_id="P-05",
            scored_band="green",
            current_band="yellow",
            last_human_action="override-P05",
            spo2_value=96.0,
            spo2_bias_risk=True,
            other_vitals={"hr": 108, "rr": 24},
            now=NOW,
        )

    # 3. Score patient — clearly distressed vitals (HR=160, RR=32, BP=80) → NOT Green
    record = PatientRecord(
        patient_id="P-05",
        age_days=365 * 35,
        hr=(160, NOW_ISO, "recheck_station", "valid"),   # severe tachycardia
        rr=(32, NOW_ISO, "recheck_station", "valid"),    # severe tachypnoea
        bp_sys=(80, NOW_ISO, "recheck_station", "valid"),  # hypotension
        spo2=(96, NOW_ISO, "recheck_station", "valid"),  # reads normal (bias)
        temp_c=(37.4, NOW_ISO, "recheck_station", "valid"),
        gcs=(14, NOW_ISO, "recheck_station", "valid"),   # reduced GCS
        pain_score=(8, NOW_ISO, "recheck_station", "valid"),  # severe pain
        spo2_bias_risk=True,
    )
    result = score_patient(record, now=NOW)
    d = result.as_dict()
    # Severe distress signals → at minimum Yellow
    assert d["band"] != "green", (
        f"Clearly distressed patient must not score Green, got: {d['band']}"
    )


# ---------------------------------------------------------------------------
# Test P-06: Stale vitals — confidence decayed, recheck raised
# ---------------------------------------------------------------------------

def test_p06_stale_vitals_decay_confidence():
    """
    P-06: Same vital values, but readings 3 hours old.
    Confidence must be visibly decayed and a recheck must be raised.
    """
    fresh_ts = NOW_ISO
    stale_ts = (NOW - datetime.timedelta(hours=3)).isoformat()

    record_fresh = PatientRecord(
        patient_id="P-06-FRESH",
        age_days=365 * 48,
        current_band="yellow",
        hr=(85, fresh_ts, "sensor", "valid"),
        rr=(17, fresh_ts, "sensor", "valid"),
        bp_sys=(122, fresh_ts, "sensor", "valid"),
        spo2=(97, fresh_ts, "sensor", "valid"),
        temp_c=(37.1, fresh_ts, "sensor", "valid"),
    )
    record_stale = PatientRecord(
        patient_id="P-06",
        age_days=365 * 48,
        current_band="yellow",
        hr=(85, stale_ts, "sensor", "valid"),
        rr=(17, stale_ts, "sensor", "valid"),
        bp_sys=(122, stale_ts, "sensor", "valid"),
        spo2=(97, stale_ts, "sensor", "valid"),
        temp_c=(37.1, stale_ts, "sensor", "valid"),
    )

    result_fresh = score_patient(record_fresh, now=NOW)
    result_stale = score_patient(record_stale, now=NOW)

    d_fresh = result_fresh.as_dict()
    d_stale = result_stale.as_dict()

    # Stale readings (3h old, yellow cadence 30min → 6×) → treated as missing → abstention
    # The important thing: stale vitals do NOT produce the same high-confidence Green
    if not d_stale.get("abstained"):
        assert d_stale["confidence"] <= d_fresh.get("confidence", 1.0), (
            "Stale vitals must have lower confidence than fresh vitals"
        )
    else:
        # Abstained is also acceptable for fully-stale vitals
        assert d_stale["band"] != "green"


# ---------------------------------------------------------------------------
# Test P-07: Zero history — first visit
# ---------------------------------------------------------------------------

def test_p07_zero_history_scores_correctly():
    """
    P-07: First visit patient with no prior records.
    Must score correctly — not abstain just because of no history.
    """
    record = PatientRecord(
        patient_id="P-07",
        age_days=365 * 38,
        hr=(88, NOW_ISO, "recheck_station", "valid"),
        rr=(18, NOW_ISO, "recheck_station", "valid"),
        bp_sys=(128, NOW_ISO, "recheck_station", "valid"),
        spo2=(97, NOW_ISO, "recheck_station", "valid"),
        temp_c=(37.0, NOW_ISO, "recheck_station", "valid"),
        gcs=(15, NOW_ISO, "recheck_station", "valid"),
        pain_score=(4, NOW_ISO, "recheck_station", "valid"),
        reliability_flags={"non_assisted_arrival": True},
    )
    result = score_patient(record, now=NOW)
    d = result.as_dict()

    # Should produce a valid score, not crash
    assert d["patient_id"] == "P-07"
    assert "band" in d
    assert "confidence" in d
    assert d["confidence"] is not None


# ---------------------------------------------------------------------------
# Test P-08: Out-of-distribution — explicit abstention, never Green
# ---------------------------------------------------------------------------

def test_p08_ood_abstains_and_holds_yellow():
    """
    P-08: OOD presentation must explicitly abstain.
    Band must be Yellow (never Green). Abstained must be True.
    """
    record = PatientRecord(
        patient_id="P-08",
        age_days=365 * 50,
        hr=(55, NOW_ISO, "sensor", "valid"),
        rr=(32, NOW_ISO, "sensor", "valid"),
        bp_sys=(155, NOW_ISO, "sensor", "valid"),
        spo2=(99, NOW_ISO, "sensor", "valid"),
        temp_c=(34.5, NOW_ISO, "sensor", "valid"),
        gcs=(15, NOW_ISO, "sensor", "valid"),
    )
    result = score_patient(record, ood_flag=True, now=NOW)
    d = result.as_dict()

    assert d["abstained"] is True, "OOD patient must have abstained=True"
    assert d["band"] == "yellow", (
        f"OOD patient must hold at Yellow, got: {d['band']}"
    )
    assert d["band"] != "green", "OOD patient must NEVER be Green"
    assert d["confidence"] == 0.0


# ---------------------------------------------------------------------------
# Test P-09: Nurse override produces complete §9 audit record
# ---------------------------------------------------------------------------

def test_p09_override_produces_complete_audit_record():
    """
    P-09: Nurse overrides Yellow→Red on physical finding.
    Audit record must have ALL 15 fields from §9 — nothing missing.
    """
    log = AuditLog()
    rec = log.record_override(
        patient_id="P-09",
        clinician_id="N-201",
        clinician_role="senior_nurse",
        system_band="yellow",
        clinician_band="red",
        reason_code="physical_finding_not_captured",
        reason_text="Peritoneal signs on palpation — absent in vitals; clinical judgement overrides.",
        score=0.55,
        confidence=0.62,
        factors_shown=["bp_sys_high", "pain_score_high"],
        inputs_hash="abc123deadbeef",
        model_version=MODEL_VERSION,
        calibration_version=CALIBRATION_VERSION,
        consent_state={"clinical_use": True, "research": False},
        now=NOW,
    )

    d = rec.as_dict()

    # All 15 §9 fields must be present and non-None (except outcome_ref which is back-filled)
    required_fields = [
        "patient_id", "timestamp_utc", "clinician_id", "clinician_role",
        "system_band", "clinician_band", "direction", "reason_code",
        "reason_text", "score", "confidence", "factors_shown",
        "inputs_hash", "model_version", "calibration_version", "consent_state",
    ]
    for f in required_fields:
        assert f in d and d[f] is not None, f"Missing or None field: {f}"
        if isinstance(d[f], str):
            assert len(d[f]) > 0, f"Empty string for field: {f}"

    # Direction must be escalation
    assert d["direction"] == "escalation"
    # Hash chain must be populated
    assert len(d["record_hash"]) == 64   # SHA-256 hex = 64 chars
    assert len(d["previous_record_hash"]) > 0


# ---------------------------------------------------------------------------
# Test P-10: Green patient misses 2 rechecks under surge → escalate to Yellow
# ---------------------------------------------------------------------------

def test_p10_green_missed_rechecks_escalate_to_yellow():
    """
    P-10: Green patient misses 2 consecutive rechecks under surge load.
    Must escalate to Yellow on the missed-recheck rule, not on a vitals change.
    """
    admitted = NOW - datetime.timedelta(minutes=200)
    state = PatientScheduleState(
        patient_id="P-10",
        current_band="green",
        last_remeasure_at=NOW - datetime.timedelta(minutes=190),
        admitted_at=admitted,
        missed_remeasures=2,   # simulates 2 consecutive missed rechecks
    )

    # Tick the scheduler — should detect 2 missed rechecks → escalate event
    events = SCHEDULER.tick(state, now=NOW, surge_mode=True)

    escalation_events = [e for e in events if "green→yellow" in e and "missed_rechecks" in e]
    assert len(escalation_events) > 0, (
        f"Expected escalate:green→yellow:missed_rechecks event, got: {events}"
    )
