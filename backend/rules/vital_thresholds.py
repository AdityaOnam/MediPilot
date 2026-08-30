"""
backend/rules/vital_thresholds.py

Hard vital emergency rules — fires independent of the risk model.
Covers:
  - Sensor loss (no valid reading for a critical vital)
  - Value outside hard emergency range
  - Multiple critical parameters abnormal simultaneously

Separate from model/thresholds.py (which handles per-stratum normal ranges).
These are absolute emergency thresholds that apply across strata.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


# Absolute emergency thresholds — values beyond these are always emergencies
# regardless of stratum normal ranges
ABSOLUTE_EMERGENCY: dict[str, dict] = {
    "hr":        {"low": 30, "high": 200},
    "rr":        {"low": 6,  "high": 50},
    "bp_sys":    {"low": 60, "high": 220},
    "spo2":      {"low": 80, "high": None},
    "temp_c":    {"low": 32, "high": 42},
    "gcs":       {"low": 3,  "high": None},
}

# If this many critical parameters are simultaneously abnormal → emergency
MULTI_PARAMETER_CRITICAL_THRESHOLD = 3

# Vitals considered critical (sensor loss for these triggers emergency)
CRITICAL_VITALS = {"hr", "rr", "bp_sys"}


@dataclass
class VitalEmergencyResult:
    triggered: bool
    reason: str
    vitals_affected: list[str]


def check_vital_emergencies(
    vitals: dict[str, Optional[float]],
    missing_vitals: set[str],
) -> Optional[VitalEmergencyResult]:
    """
    Check for absolute vital emergencies.

    Returns VitalEmergencyResult if any emergency condition is met, else None.
    Fires independently of the risk model score.
    """
    reasons = []
    affected = []

    # 1. Sensor loss for critical vitals
    for cv in CRITICAL_VITALS:
        if cv in missing_vitals:
            reasons.append(f"sensor_loss_{cv}")
            affected.append(cv)

    # 2. Value outside hard emergency range
    critical_count = 0
    for vital, value in vitals.items():
        if value is None:
            continue
        thresholds = ABSOLUTE_EMERGENCY.get(vital)
        if thresholds is None:
            continue
        lo = thresholds.get("low")
        hi = thresholds.get("high")
        outside = (lo is not None and value < lo) or (hi is not None and value > hi)
        if outside:
            critical_count += 1
            reasons.append(f"{vital}_critical_range")
            affected.append(vital)

    # 3. Multiple parameters simultaneously critical
    if critical_count >= MULTI_PARAMETER_CRITICAL_THRESHOLD:
        reasons.append(f"multi_parameter_critical_{critical_count}")

    if reasons:
        return VitalEmergencyResult(
            triggered=True,
            reason="; ".join(reasons),
            vitals_affected=list(set(affected)),
        )
    return None
