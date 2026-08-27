"""
medipilot-model/tests/test_audit_log.py

Tests for the append-only, hash-chained audit log.
"""

import datetime
import pytest

from backend.audit_log import AuditLog, ValidationError
from model.calibration import MODEL_VERSION, CALIBRATION_VERSION

NOW = datetime.datetime(2026, 8, 22, 14, 0, tzinfo=datetime.timezone.utc)


def _make_log_with_one_record() -> tuple[AuditLog, object]:
    log = AuditLog()
    rec = log.record_override(
        patient_id="TEST-P",
        clinician_id="DR-001",
        clinician_role="consultant",
        system_band="yellow",
        clinician_band="red",
        reason_code="clinical_gestalt",
        reason_text="Clinical gestalt based on examination findings.",
        score=0.62,
        confidence=0.71,
        factors_shown=["hr_high", "rr_high"],
        inputs_hash="deadbeef1234",
        model_version=MODEL_VERSION,
        calibration_version=CALIBRATION_VERSION,
        consent_state={"clinical_use": True},
        now=NOW,
    )
    return log, rec


def test_record_has_all_15_fields():
    """All 15 §9 fields must be present in the record."""
    log, rec = _make_log_with_one_record()
    d = rec.as_dict()
    required = [
        "patient_id", "timestamp_utc", "clinician_id", "clinician_role",
        "system_band", "clinician_band", "direction", "reason_code",
        "reason_text", "score", "confidence", "factors_shown",
        "inputs_hash", "model_version", "calibration_version", "consent_state",
    ]
    for field in required:
        assert field in d, f"Missing field: {field}"


def test_hash_chain_integrity():
    """Hash chain must be valid after multiple records."""
    log = AuditLog()
    for i in range(5):
        log.record_override(
            patient_id=f"P-{i}",
            clinician_id="DR-001",
            clinician_role="nurse",
            system_band="green",
            clinician_band="yellow",
            reason_code="physical_finding_not_captured",
            reason_text=f"Observation {i}: physical finding not in vitals.",
            score=0.3,
            confidence=0.7,
            factors_shown=[],
            inputs_hash=f"hash{i}",
            model_version=MODEL_VERSION,
            calibration_version=CALIBRATION_VERSION,
            consent_state={},
            now=NOW + datetime.timedelta(minutes=i),
        )
    ok, msg = log.verify_chain()
    assert ok, f"Chain verification failed: {msg}"


def test_empty_reason_raises_validation_error():
    log = AuditLog()
    with pytest.raises(ValidationError):
        log.record_override(
            patient_id="P-X",
            clinician_id="DR-001",
            clinician_role="consultant",
            system_band="yellow",
            clinician_band="red",
            reason_code="clinical_gestalt",
            reason_text="",   # empty — rejected
            score=0.5,
            confidence=0.6,
            factors_shown=[],
            inputs_hash="x",
            model_version=MODEL_VERSION,
            calibration_version=CALIBRATION_VERSION,
            consent_state={},
            now=NOW,
        )


def test_consent_withdrawal_does_not_delete_prior_records():
    """Consent withdrawal must add a new event — never delete prior records."""
    log, rec = _make_log_with_one_record()
    count_before = len(log.records)
    log.record_consent_withdrawal(
        patient_id="TEST-P",
        withdrawn_purposes=["research"],
        now=NOW,
    )
    count_after = len(log.records)
    assert count_after == count_before, (
        "Prior audit records must not be deleted on consent withdrawal"
    )


def test_outcome_backfill():
    """outcome_ref can be back-filled after the fact."""
    log, rec = _make_log_with_one_record()
    assert rec.outcome_ref is None
    filled = log.backfill_outcome(
        patient_id="TEST-P",
        override_timestamp_utc=rec.timestamp_utc,
        outcome_ref="OUTCOME-REF-001",
    )
    assert filled is True
    updated = log.get_patient_records("TEST-P")
    assert updated[-1].outcome_ref == "OUTCOME-REF-001"


def test_direction_escalation_vs_deescalation():
    log = AuditLog()
    # Escalation: yellow → red
    esc = log.record_override(
        patient_id="P-E",
        clinician_id="D1",
        clinician_role="nurse",
        system_band="yellow",
        clinician_band="red",
        reason_code="clinical_gestalt",
        reason_text="Escalation based on examination.",
        score=0.5,
        confidence=0.6,
        factors_shown=[],
        inputs_hash="h1",
        model_version=MODEL_VERSION,
        calibration_version=CALIBRATION_VERSION,
        consent_state={},
        now=NOW,
    )
    assert esc.direction == "escalation"

    # De-escalation: red → yellow
    deesc = log.record_override(
        patient_id="P-D",
        clinician_id="D2",
        clinician_role="consultant",
        system_band="red",
        clinician_band="yellow",
        reason_code="error_correction",
        reason_text="Initial triage was in error; presentation is Yellow.",
        score=0.8,
        confidence=0.85,
        factors_shown=[],
        inputs_hash="h2",
        model_version=MODEL_VERSION,
        calibration_version=CALIBRATION_VERSION,
        consent_state={},
        now=NOW,
    )
    assert deesc.direction == "de-escalation"
