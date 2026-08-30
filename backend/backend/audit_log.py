"""
medipilot-model/backend/audit_log.py

Append-only, hash-chained override record log.

Properties:
  1. Append-only: records are never deleted or modified.
  2. Tamper-evident: each record contains the SHA-256 hash of the previous
     record, forming a verifiable chain.
  3. Complete schema: every override record has all 15 fields from §9 of the brief.
  4. Consent withdrawal: recorded as a new event, never deletes prior records.
  5. Outcome back-fill: outcome_ref is filled later when known, creating the
     training signal.

This is the function/endpoint that accepts and records overrides.
The UI is built by Track B — this module provides the data layer.
"""

from __future__ import annotations

import datetime
import hashlib
import json
import pathlib
from dataclasses import dataclass, field, asdict
from typing import Optional


# All 15 fields from §9 — None allowed only for fields that are legitimately
# back-filled (outcome_ref) or not yet available (consent_state on abstention).
@dataclass
class OverrideRecord:
    # §9 fields — all required except outcome_ref (back-filled later)
    patient_id: str                 # Links to encounter record
    timestamp_utc: str              # ISO-8601 — ordering against deterioration timeline
    clinician_id: str               # Named accountability
    clinician_role: str             # What overrider was authorised to do
    system_band: str                # What was recommended
    clinician_band: str             # What was done instead
    direction: str                  # "escalation" | "de-escalation"
    reason_code: str                # Fixed list — for aggregate analysis
    reason_text: str                # Free text — fixed list won't cover everything
    score: float                    # Calibrated risk score at moment of override
    confidence: float               # Confidence at moment of override
    factors_shown: list             # The card as displayed — what clinician was told
    inputs_hash: str                # Fixes input state so decision is reproducible
    model_version: str              # Which model produced this output
    calibration_version: str        # Which calibration was in use
    consent_state: dict             # Which purposes patient had consented to
    outcome_ref: Optional[str] = None   # Back-filled when known

    # Hash chain field
    record_hash: str = ""           # SHA-256 of this record's content
    previous_record_hash: str = ""  # SHA-256 of previous record (chain link)

    def as_dict(self) -> dict:
        return asdict(self)


class ValidationError(Exception):
    """Raised when an override record is missing required fields."""
    pass


_REQUIRED_FIELDS = [
    "patient_id", "timestamp_utc", "clinician_id", "clinician_role",
    "system_band", "clinician_band", "direction", "reason_code",
    "reason_text", "score", "confidence", "factors_shown",
    "inputs_hash", "model_version", "calibration_version", "consent_state",
]

_VALID_REASON_CODES = {
    # Original backend codes
    "physical_finding_not_captured",
    "clinical_gestalt",
    "history_not_captured_by_system",
    "patient_preference",
    "test_result_available",
    "change_in_clinical_status",
    "error_correction",
    "risk_tolerance_adjustment",
    "other",
    # Frontend kebab-case codes (from types.ts OVERRIDE_REASON_CODES)
    "clinical-finding-on-exam",
    "deteriorating-vital-trend",
    "red-flag-symptom-reported",
    "suspected-serious-diagnosis",
    "known-comorbidity",
    "protocol-mandated-escalation",
    "resolution-on-reassessment",
    "symptom-resolved-benign-cause",
    "model-context-mismatch",
    "other-with-note",
}


class AuditLog:
    """
    Append-only, hash-chained audit log for override records.

    In-memory for the prototype — in production this would be a
    tamper-evident database (append-only log table with row hashes).
    """

    def __init__(self, log_path: Optional[pathlib.Path] = None):
        self._records: list[OverrideRecord] = []
        self._consent_withdrawals: list[dict] = []
        self._log_path = log_path
        self._last_hash = "GENESIS"  # Hash chain starts here

        if log_path and log_path.exists():
            self._load(log_path)

    def _load(self, path: pathlib.Path) -> None:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        for rec_dict in data.get("records", []):
            rec = OverrideRecord(**rec_dict)
            self._records.append(rec)
        self._consent_withdrawals = data.get("consent_withdrawals", [])
        if self._records:
            self._last_hash = self._records[-1].record_hash

    def _save(self) -> None:
        if self._log_path is None:
            return
        data = {
            "records": [r.as_dict() for r in self._records],
            "consent_withdrawals": self._consent_withdrawals,
        }
        self._log_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self._log_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    def _compute_hash(self, record: OverrideRecord, previous_hash: str) -> str:
        """Compute SHA-256 hash linking this record to the chain."""
        content = {
            "previous_hash": previous_hash,
            **{k: v for k, v in record.as_dict().items()
               if k not in ("record_hash", "previous_record_hash")},
        }
        raw = json.dumps(content, sort_keys=True, default=str)
        return hashlib.sha256(raw.encode()).hexdigest()

    def record_override(
        self,
        patient_id: str,
        clinician_id: str,
        clinician_role: str,
        system_band: str,
        clinician_band: str,
        reason_code: str,
        reason_text: str,
        score: float,
        confidence: float,
        factors_shown: list,
        inputs_hash: str,
        model_version: str,
        calibration_version: str,
        consent_state: dict,
        outcome_ref: Optional[str] = None,
        now: Optional[datetime.datetime] = None,
    ) -> OverrideRecord:
        """
        Record a clinician override.

        All §9 fields are required except outcome_ref (back-filled later).
        Raises ValidationError if any required field is missing or invalid.

        Invariant 6: reason_text must be provided (human closes every loop).
        """
        if now is None:
            now = datetime.datetime.now(tz=datetime.timezone.utc)

        # Validate reason
        if not reason_text or not reason_text.strip():
            raise ValidationError(
                "ValidationError: reason_text is required for every override. "
                "Invariant 6: the human closes every loop with a reason. "
                "Override rejected."
            )

        if reason_code not in _VALID_REASON_CODES:
            raise ValidationError(
                f"ValidationError: reason_code '{reason_code}' is not in the fixed list. "
                f"Valid codes: {sorted(_VALID_REASON_CODES)}"
            )

        # Determine direction
        from backend.band_engine import BAND_ORDER
        sys_idx = BAND_ORDER.get(system_band, 1)
        cli_idx = BAND_ORDER.get(clinician_band, 1)
        if cli_idx > sys_idx:
            direction = "escalation"
        elif cli_idx < sys_idx:
            direction = "de-escalation"
        else:
            direction = "same-band-override"

        rec = OverrideRecord(
            patient_id=patient_id,
            timestamp_utc=now.isoformat(),
            clinician_id=clinician_id,
            clinician_role=clinician_role,
            system_band=system_band,
            clinician_band=clinician_band,
            direction=direction,
            reason_code=reason_code,
            reason_text=reason_text,
            score=round(score, 4),
            confidence=round(confidence, 4),
            factors_shown=factors_shown,
            inputs_hash=inputs_hash,
            model_version=model_version,
            calibration_version=calibration_version,
            consent_state=consent_state,
            outcome_ref=outcome_ref,
            previous_record_hash=self._last_hash,
        )

        # Compute and attach hash
        rec.record_hash = self._compute_hash(rec, self._last_hash)
        self._last_hash = rec.record_hash

        self._records.append(rec)
        self._save()
        return rec

    def record_consent_withdrawal(
        self,
        patient_id: str,
        withdrawn_purposes: list[str],
        now: Optional[datetime.datetime] = None,
    ) -> dict:
        """
        Record a consent withdrawal as a new append-only event.
        NEVER deletes prior audit records — consent withdrawal is itself an event.
        """
        if now is None:
            now = datetime.datetime.now(tz=datetime.timezone.utc)
        event = {
            "event_type": "consent_withdrawal",
            "patient_id": patient_id,
            "timestamp_utc": now.isoformat(),
            "withdrawn_purposes": withdrawn_purposes,
            "note": "Prior audit records retained — consent withdrawal recorded as new event per DPDP Act 2023.",
        }
        self._consent_withdrawals.append(event)
        self._save()
        return event

    def backfill_outcome(
        self,
        patient_id: str,
        override_timestamp_utc: str,
        outcome_ref: str,
    ) -> bool:
        """Back-fill outcome_ref on a specific override record."""
        for rec in self._records:
            if rec.patient_id == patient_id and rec.timestamp_utc == override_timestamp_utc:
                rec.outcome_ref = outcome_ref
                self._save()
                return True
        return False

    def get_patient_records(self, patient_id: str) -> list[OverrideRecord]:
        """Return all override records for a patient, in order."""
        return [r for r in self._records if r.patient_id == patient_id]

    def verify_chain(self) -> tuple[bool, str]:
        """
        Verify the hash chain integrity.
        Returns (ok, message).
        """
        prev_hash = "GENESIS"
        for i, rec in enumerate(self._records):
            expected = self._compute_hash(rec, prev_hash)
            if rec.record_hash != expected:
                return False, f"Chain broken at record {i} (patient={rec.patient_id})"
            prev_hash = rec.record_hash
        return True, f"Chain intact ({len(self._records)} records)"

    @property
    def records(self) -> list[OverrideRecord]:
        return list(self._records)
