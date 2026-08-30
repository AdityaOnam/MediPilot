"""
backend/triage/band_engine.py

Band assignment with asymmetric autonomy enforcement (Invariant 1).

Core rule:
  - The system MAY raise a patient's band autonomously.
  - The system MAY NEVER lower a patient's band without an attached human action.

Any code path that moves a band downward without an override record
raises AsymmetricAutonomyViolation — this is a hard error, not a warning.

SpO2 bias guard is called before any de-escalation attempt.
"""

from __future__ import annotations

import datetime
from dataclasses import dataclass
from typing import Optional

from rules.spo2_bias_guard import check_spo2_alone_deescalation, SpO2AloneDeescalationError


# Band ordering: higher index = higher acuity
BAND_ORDER = {"green": 0, "yellow": 1, "red": 2}
BAND_FROM_IDX = {0: "green", 1: "yellow", 2: "red"}


class AsymmetricAutonomyViolation(Exception):
    """
    Raised when the system attempts to lower a patient's band without
    an attached human action (override record).
    This is a safety violation, not a validation error.
    """
    pass


@dataclass
class BandAssignment:
    patient_id: str
    previous_band: Optional[str]
    new_band: str
    changed: bool
    direction: str          # "escalation" | "deescalation" | "unchanged" | "initial"
    autonomous: bool        # True if system changed band without human action
    reason: str
    assigned_at: str        # ISO-8601


def assign_band(
    patient_id: str,
    scored_band: str,              # band from ScoreObject
    current_band: Optional[str],   # currently assigned band (None = not yet assigned)
    last_human_action: Optional[str] = None,  # override record ID, if human acted
    spo2_value: Optional[float] = None,
    spo2_bias_risk: bool = False,
    other_vitals: Optional[dict] = None,
    reason: str = "model_rescore",
    now: Optional[datetime.datetime] = None,
) -> BandAssignment:
    """
    Assign a band given the model's scored band and the current band.

    Invariant 1 enforcement:
      - If new band < current band AND no human action attached → raise violation.
      - If new band > current band → always allowed (autonomous escalation).
      - If equal → unchanged.

    Args:
        patient_id: for error messages and the returned record
        scored_band: band from the model (ScoreObject.band)
        current_band: currently assigned band; None means not yet assigned
        last_human_action: override record ID if a human just acted (enables de-escalation)
        spo2_value: for SpO2 bias guard
        spo2_bias_risk: True if dark skin tone flag applies
        other_vitals: for SpO2 bias guard corroboration check
        reason: why this assignment is being made (for audit)
        now: override timestamp (for testing)
    """
    if now is None:
        now = datetime.datetime.now(tz=datetime.timezone.utc)

    if current_band is None:
        # First assignment — always allowed
        return BandAssignment(
            patient_id=patient_id,
            previous_band=None,
            new_band=scored_band,
            changed=True,
            direction="initial",
            autonomous=True,
            reason=reason,
            assigned_at=now.isoformat(),
        )

    current_idx = BAND_ORDER.get(current_band, 1)
    new_idx = BAND_ORDER.get(scored_band, 1)

    if new_idx > current_idx:
        # Escalation — autonomous is allowed (Invariant 1)
        return BandAssignment(
            patient_id=patient_id,
            previous_band=current_band,
            new_band=scored_band,
            changed=True,
            direction="escalation",
            autonomous=True,
            reason=reason,
            assigned_at=now.isoformat(),
        )

    elif new_idx < current_idx:
        # DE-ESCALATION ATTEMPT — requires human action
        if last_human_action is None:
            raise AsymmetricAutonomyViolation(
                f"AsymmetricAutonomyViolation: Attempt to lower patient '{patient_id}' "
                f"from '{current_band}' to '{scored_band}' without an attached human action. "
                "A clinician override is required for any band de-escalation. "
                "Invariant 1 violated."
            )

        # Human action attached — apply SpO2 bias guard before accepting
        if spo2_value is not None:
            try:
                check_spo2_alone_deescalation(
                    spo2_value=spo2_value,
                    spo2_bias_risk=spo2_bias_risk,
                    other_vitals=other_vitals or {},
                    proposed_direction="deescalate",
                )
            except SpO2AloneDeescalationError:
                # Even with human action, SpO2-alone de-escalation is blocked
                raise

        return BandAssignment(
            patient_id=patient_id,
            previous_band=current_band,
            new_band=scored_band,
            changed=True,
            direction="deescalation",
            autonomous=False,       # human action attached
            reason=f"human_override:{last_human_action}",
            assigned_at=now.isoformat(),
        )

    else:
        # Unchanged
        return BandAssignment(
            patient_id=patient_id,
            previous_band=current_band,
            new_band=scored_band,
            changed=False,
            direction="unchanged",
            autonomous=True,
            reason=reason,
            assigned_at=now.isoformat(),
        )
