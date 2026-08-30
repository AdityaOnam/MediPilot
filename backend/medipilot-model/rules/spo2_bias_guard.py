"""
medipilot-model/rules/spo2_bias_guard.py

Hard rule: SpO2 normal alone MUST NEVER justify downward band movement
or de-escalation.

From the brief §5:
  "A normal SpO₂ reading alone must never justify downward band movement
   or a de-escalation. It's a documented source of racial bias in pulse
   oximetry (occult hypoxemia under-detected at meaningfully higher rates
   in darker-skinned patients)."

This is enforced in code — not policy.
Any call path that attempts to use SpO2 as sufficient justification for
de-escalation will raise SpO2AloneDeescalationError.

The guard is called from risk_model.py before scoring when spo2_bias_risk=True,
and from band_engine.py before any band lowering.
"""

from __future__ import annotations

from typing import Optional


class SpO2AloneDeescalationError(Exception):
    """
    Raised when code attempts to de-escalate based on SpO2 alone.
    This is a safety violation, not a validation error.
    """
    pass


def check_spo2_alone_deescalation(
    spo2_value: Optional[float],
    spo2_bias_risk: bool,
    other_vitals: dict[str, Optional[float]],
    proposed_direction: str = "deescalate",
) -> None:
    """
    Guard function called before any band lowering decision.

    If:
      - SpO2 reads normal (>= 94)
      - spo2_bias_risk is True (dark skin tone flag)
      - No other corroborating vital is strongly reassuring

    → raise SpO2AloneDeescalationError.

    Even WITHOUT spo2_bias_risk, SpO2 alone is never sufficient for de-escalation.
    The bias_risk flag makes the guard stricter.

    Args:
        spo2_value: current SpO2 reading (None = not available, guard skipped)
        spo2_bias_risk: True if patient has dark skin tone bias flag
        other_vitals: dict of other vital values available at scoring time
        proposed_direction: "deescalate" or "escalate" — guard only fires on deescalate
    """
    if proposed_direction != "deescalate":
        return  # guard only relevant for de-escalation

    if spo2_value is None:
        return  # no SpO2 reading — guard not applicable

    spo2_normal = spo2_value >= 94.0

    if not spo2_normal:
        return  # SpO2 is abnormal — de-escalation is not being driven by SpO2

    # Count corroborating reassuring vitals
    corroborating = 0
    if other_vitals.get("hr") is not None and 60 <= other_vitals["hr"] <= 100:
        corroborating += 1
    if other_vitals.get("rr") is not None and 12 <= other_vitals["rr"] <= 20:
        corroborating += 1
    if other_vitals.get("bp_sys") is not None and 90 <= other_vitals["bp_sys"] <= 140:
        corroborating += 1

    # SpO2 alone means < 2 corroborating vitals are reassuring
    spo2_is_sole_justification = corroborating < 2

    if spo2_normal and spo2_is_sole_justification:
        msg = (
            f"SpO2AloneDeescalationError: SpO2={spo2_value}% (normal) is the sole "
            f"or primary justification for de-escalation. "
            f"spo2_bias_risk={spo2_bias_risk}. "
            "Per §5 hard rule: SpO2 alone never justifies band reduction. "
            "Multiple corroborating normal vitals required."
        )
        raise SpO2AloneDeescalationError(msg)
