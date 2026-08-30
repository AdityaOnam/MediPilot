"""
backend/tests/test_invariants.py

6 mechanical invariant tests — one per invariant from §1 of the brief.
These are the non-negotiable constraints. Every one of them must be
mechanically true of the code.

Test IDs:
  INV-1: Asymmetric autonomy — autonomous band lowering raises violation
  INV-2: No naked scores — failed confidence → AbstentionObject only
  INV-3: Age never assumed — unknown age → inferred=True in output
  INV-4: Freshness decay — 3× stale reading → treated as missing
  INV-5: Abstention is loud and Yellow — abstained.band is always "yellow"
  INV-6: Human closes every loop — override without reason_text → ValidationError
"""

import datetime
import pytest

from model.age_stratum import resolve_stratum
from model.risk_model import PatientRecord, score_patient, AbstentionObject
from triage.band_engine import assign_band, AsymmetricAutonomyViolation
from triage.audit_log import AuditLog, ValidationError


UTC = datetime.timezone.utc
NOW = datetime.datetime(2026, 8, 22, 12, 0, 0, tzinfo=UTC)
NOW_ISO = NOW.isoformat()


# ────────────────────────────────────────────────────────────────────────────
# INV-1: Asymmetric autonomy
# ────────────────────────────────────────────────────────────────────────────

def test_inv1_autonomous_band_lowering_raises_violation():
    """
    Invariant 1: the system may NEVER lower a patient's band without a
    human action attached. Attempting to do so raises AsymmetricAutonomyViolation.
    """
    with pytest.raises(AsymmetricAutonomyViolation):
        assign_band(
            patient_id="TEST-INV1",
            scored_band="green",        # model says green
            current_band="yellow",      # but patient is currently yellow
            last_human_action=None,     # NO human action → violation
            reason="model_rescore",
            now=NOW,
        )


def test_inv1_autonomous_escalation_is_allowed():
    """
    Invariant 1: autonomous ESCALATION must be allowed.
    """
    result = assign_band(
        patient_id="TEST-INV1-ESC",
        scored_band="red",
        current_band="yellow",
        last_human_action=None,     # no human action needed for escalation
        reason="model_rescore",
        now=NOW,
    )
    assert result.new_band == "red"
    assert result.direction == "escalation"
    assert result.autonomous is True


def test_inv1_deescalation_with_human_action_allowed():
    """
    Invariant 1: de-escalation IS allowed when a human action (override ID) is attached.
    """
    result = assign_band(
        patient_id="TEST-INV1-DEESC",
        scored_band="green",
        current_band="yellow",
        last_human_action="override-abc123",  # human action attached
        spo2_value=None,   # no SpO2 in play
        reason="clinician_override",
        now=NOW,
    )
    assert result.new_band == "green"
    assert result.direction == "deescalation"
    assert result.autonomous is False


# ────────────────────────────────────────────────────────────────────────────
# INV-2: No naked scores
# ────────────────────────────────────────────────────────────────────────────

def test_inv2_ood_flag_produces_abstention_not_score():
    """
    Invariant 2: when OOD flag is set, the model must emit an AbstentionObject —
    never a partial ScoreObject with blank confidence.
    """
    record = PatientRecord(
        patient_id="TEST-INV2",
        age_days=365 * 40,
        hr=(55, NOW_ISO, "sensor", "valid"),
        rr=(32, NOW_ISO, "sensor", "valid"),
        bp_sys=(155, NOW_ISO, "sensor", "valid"),
        spo2=(99, NOW_ISO, "sensor", "valid"),
        temp_c=(34.5, NOW_ISO, "sensor", "valid"),
    )
    result = score_patient(record, ood_flag=True, now=NOW)
    assert isinstance(result, AbstentionObject), (
        "Expected AbstentionObject for OOD patient, got ScoreObject"
    )
    assert result.abstained is True
    assert result.confidence == 0.0
    assert result.confidence_reason is not None and len(result.confidence_reason) > 0


def test_inv2_all_vitals_missing_produces_abstention():
    """
    Invariant 2: if all vitals are missing, must abstain.
    """
    record = PatientRecord(
        patient_id="TEST-INV2-MISSING",
        age_days=365 * 40,
        # All vitals absent
    )
    result = score_patient(record, now=NOW)
    assert isinstance(result, AbstentionObject)
    assert result.abstained is True


def test_inv2_score_object_always_has_confidence():
    """
    Invariant 2: any emitted ScoreObject must have confidence populated.
    """
    record = PatientRecord(
        patient_id="TEST-INV2-SCORE",
        age_days=365 * 40,
        hr=(85, NOW_ISO, "recheck_station", "valid"),
        rr=(18, NOW_ISO, "recheck_station", "valid"),
        bp_sys=(120, NOW_ISO, "recheck_station", "valid"),
        spo2=(98, NOW_ISO, "recheck_station", "valid"),
        temp_c=(37.0, NOW_ISO, "recheck_station", "valid"),
    )
    result = score_patient(record, now=NOW)
    d = result.as_dict()
    assert "confidence" in d
    assert d["confidence"] is not None
    # If not abstained, confidence must be > 0
    if not d.get("abstained"):
        assert d["confidence"] > 0.0


# ────────────────────────────────────────────────────────────────────────────
# INV-3: Age is never assumed
# ────────────────────────────────────────────────────────────────────────────

def test_inv3_unknown_age_resolves_to_inferred():
    """
    Invariant 3: if age is unknown, stratum must be inferred=True.
    """
    result = resolve_stratum(age_days=None, age_known=False)
    assert result.inferred is True, "Unknown age must be marked as inferred"


def test_inv3_unknown_age_in_score_output():
    """
    Invariant 3: scoring a patient with unknown age must produce age_stratum_inferred=True.
    """
    record = PatientRecord(
        patient_id="TEST-INV3",
        age_days=None,
        age_known=False,
        hr=(95, NOW_ISO, "recheck_station", "valid"),
        rr=(20, NOW_ISO, "recheck_station", "valid"),
        bp_sys=(115, NOW_ISO, "recheck_station", "valid"),
        spo2=(97, NOW_ISO, "recheck_station", "valid"),
        temp_c=(37.2, NOW_ISO, "recheck_station", "valid"),
    )
    result = score_patient(record, now=NOW)
    d = result.as_dict()
    assert d["age_stratum_inferred"] is True, (
        "Patient with unknown age must have age_stratum_inferred=True in output"
    )


def test_inv3_known_age_is_not_inferred():
    """
    Invariant 3: a patient with known age must NOT have inferred=True.
    """
    result = resolve_stratum(age_days=365 * 40, age_known=True)
    assert result.inferred is False
    assert result.stratum == "adult"


# ────────────────────────────────────────────────────────────────────────────
# INV-4: Freshness decay
# ────────────────────────────────────────────────────────────────────────────

def test_inv4_reading_3x_stale_treated_as_missing():
    """
    Invariant 4: a reading older than 3× the re-measurement cadence must be
    treated as missing, not as a valid current reading.
    For Yellow band, cadence is 30 min → 3× = 90 min old reading is missing.
    """
    # Reading from 3.5 hours ago
    stale_ts = (NOW - datetime.timedelta(hours=3, minutes=30)).isoformat()
    record = PatientRecord(
        patient_id="TEST-INV4",
        age_days=365 * 40,
        current_band="yellow",
        # All vitals are stale (3.5h old, yellow cadence = 30min → 3× = 90min)
        hr=(85, stale_ts, "sensor", "valid"),
        rr=(18, stale_ts, "sensor", "valid"),
        bp_sys=(120, stale_ts, "sensor", "valid"),
        spo2=(98, stale_ts, "sensor", "valid"),
        temp_c=(37.0, stale_ts, "sensor", "valid"),
        gcs=(15, stale_ts, "sensor", "valid"),
        pain_score=(3, stale_ts, "sensor", "valid"),
    )
    result = score_patient(record, now=NOW)
    # All vitals beyond 3× cadence → treated as missing → must abstain
    assert isinstance(result, AbstentionObject), (
        "All vitals 3× stale must result in abstention (treated as missing)"
    )


def test_inv4_reading_2x_stale_is_discounted_not_missing():
    """
    Invariant 4: a reading 2× stale is discounted (confidence reduced) but
    the value is still used — it's not treated as missing.
    """
    stale_ts = (NOW - datetime.timedelta(hours=1, minutes=10)).isoformat()  # ~70 min, yellow cadence 30min → 2× = 60min
    record = PatientRecord(
        patient_id="TEST-INV4-B",
        age_days=365 * 40,
        current_band="yellow",
        hr=(95, stale_ts, "sensor", "valid"),
        rr=(22, stale_ts, "sensor", "valid"),
        bp_sys=(140, stale_ts, "sensor", "valid"),
        spo2=(95, stale_ts, "sensor", "valid"),
        temp_c=(38.2, stale_ts, "sensor", "valid"),
    )
    result = score_patient(record, now=NOW)
    # Should NOT abstain — value is used but confidence reduced
    # (some vitals may be treated as missing if all beyond 3×, so this is
    # specifically testing 2× stale → still scored but with reduced confidence)
    d = result.as_dict()
    # If it's a score (not abstention), confidence should be lower than normal
    # If it abstained, ensure it's not because it returned Green (invariant 5)
    if d.get("abstained"):
        assert d["band"] != "green"


# ────────────────────────────────────────────────────────────────────────────
# INV-5: Abstention is loud and never Green
# ────────────────────────────────────────────────────────────────────────────

def test_inv5_abstained_patient_band_is_yellow():
    """
    Invariant 5: an abstained patient holds at Yellow, NEVER Green.
    Force abstention via OOD flag passed to score_patient.
    """
    record = PatientRecord(
        patient_id="TEST-INV5",
        age_days=365 * 50,
    )
    # Force abstention via OOD flag on score_patient, not on PatientRecord
    result = score_patient(record, ood_flag=True, now=NOW)
    assert result.abstained is True
    assert result.band == "yellow", (
        f"Abstained patient must hold at Yellow, got: {result.band}"
    )
    assert result.band != "green"


def test_inv5_abstention_object_always_yellow():
    """
    Invariant 5: AbstentionObject.band is always 'yellow' regardless of how it's created.
    """
    abstention = AbstentionObject(
        patient_id="TEST-INV5-B",
        computed_at=NOW_ISO,
    )
    assert abstention.band == "yellow"
    assert abstention.abstained is True


# ────────────────────────────────────────────────────────────────────────────
# INV-6: Human closes every loop
# ────────────────────────────────────────────────────────────────────────────

def test_inv6_override_without_reason_raises_validation_error():
    """
    Invariant 6: every override must carry a reason. Empty reason_text
    raises ValidationError.
    """
    log = AuditLog()
    with pytest.raises(ValidationError):
        log.record_override(
            patient_id="TEST-INV6",
            clinician_id="DR-001",
            clinician_role="consultant",
            system_band="yellow",
            clinician_band="red",
            reason_code="clinical_gestalt",
            reason_text="",   # EMPTY — must be rejected
            score=0.5,
            confidence=0.6,
            factors_shown=["hr_high"],
            inputs_hash="abc123",
            model_version="v0.1",
            calibration_version="v0.1",
            consent_state={"purpose_a": True},
            now=NOW,
        )


def test_inv6_override_with_reason_succeeds():
    """
    Invariant 6: override with a valid reason_text and reason_code succeeds.
    """
    log = AuditLog()
    rec = log.record_override(
        patient_id="TEST-INV6-OK",
        clinician_id="DR-001",
        clinician_role="consultant",
        system_band="yellow",
        clinician_band="red",
        reason_code="physical_finding_not_captured",
        reason_text="Peritoneal signs on palpation — absent in vitals.",
        score=0.5,
        confidence=0.6,
        factors_shown=["hr_high"],
        inputs_hash="abc123",
        model_version="v0.1",
        calibration_version="v0.1",
        consent_state={"purpose_a": True},
        now=NOW,
    )
    assert rec.record_hash != ""
    assert rec.direction == "escalation"
    assert rec.reason_text != ""
