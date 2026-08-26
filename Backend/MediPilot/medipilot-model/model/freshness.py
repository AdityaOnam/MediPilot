"""
medipilot-model/model/freshness.py

Reading-age and staleness logic (Invariant 4), extracted so that TRAINING and
SERVING share one implementation.

This extraction is a correctness requirement, not tidiness. If the training
pipeline reads `series[-1]` raw while `score_patient()` reads a
freshness-filtered value, every feature downstream is computed on different
inputs in training than in production — and nothing in the test suite would
report it. That is train/serve skew, and it is silent by nature.

Invariant 4:
  - reading older than 3x its band's cadence  -> treat as MISSING
  - reading older than 2x its band's cadence  -> STALE (value kept, discounted)
  - otherwise                                 -> FRESH
"""

from __future__ import annotations

import datetime
from typing import Optional


# Re-measurement cadence per band, in minutes. Mirrors config/band_cadence.yaml.
VITAL_CADENCE_MINUTES = {
    "red": 5,
    "yellow": 30,
    "green": 60,
}


def reading_age_minutes(
    timestamp_iso: Optional[str],
    now: datetime.datetime,
) -> Optional[float]:
    """Age of a reading in minutes. None when the timestamp is absent/unparseable."""
    if timestamp_iso is None:
        return None
    try:
        ts = datetime.datetime.fromisoformat(timestamp_iso)
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=datetime.timezone.utc)
        return (now - ts).total_seconds() / 60.0
    except Exception:
        return None


def check_freshness(
    vital_tuple: Optional[tuple],
    current_band: str,
    now: datetime.datetime,
) -> tuple[Optional[float], bool, bool]:
    """
    Returns (value, is_stale, is_missing) for a vital reading.

    vital_tuple is the (value, timestamp_iso, source, validity) tuple.
    """
    if vital_tuple is None:
        return None, False, True

    value, ts_iso, source, validity = vital_tuple
    if validity != "valid":
        return None, False, True

    cadence = VITAL_CADENCE_MINUTES.get(current_band or "yellow", 30)
    age_min = reading_age_minutes(ts_iso, now)

    if age_min is None:
        return float(value), False, False

    if age_min > 3 * cadence:
        return None, False, True            # treat as missing
    elif age_min > 2 * cadence:
        return float(value), True, False    # stale — discounted
    else:
        return float(value), False, False   # fresh
