"""
backend/model/thresholds.py

Per-stratum vital thresholds — what counts as abnormal for this stratum.

This is MECHANISM 1 of the two separate mechanisms required by the brief:
  - Thresholds: what counts as abnormal (THIS FILE)
  - Calibration: how an abnormality maps to risk (calibration.py)

Conflating them produces a model that is right about vitals and wrong about danger.
"""

from __future__ import annotations

import pathlib
from dataclasses import dataclass
from typing import Optional

import yaml


_CONFIG_PATH = pathlib.Path(__file__).parent.parent / "config" / "age_strata.yaml"


@dataclass
class ThresholdResult:
    vital: str
    value: float
    stratum: str
    is_abnormal: bool
    direction: str          # "high" | "low" | "normal"
    deviation_sigma: float  # how many sigma from normal midpoint


class VitalThresholds:
    """
    Loads per-stratum threshold config and exposes abnormality checks.
    Thresholds are CONFIGURABLE — never hard-coded constants.
    """

    def __init__(self, config_path: pathlib.Path = _CONFIG_PATH):
        with open(config_path, encoding="utf-8") as f:
            cfg = yaml.safe_load(f)
        self._strata = cfg["strata"]

    def _get_normal(self, vital: str, stratum: str) -> Optional[tuple[float, float]]:
        """Return (lo, hi) normal range for vital in stratum, or None if not defined."""
        s = self._strata.get(stratum, self._strata.get("adult"))
        vn = s.get("vitals_normal", {})
        lo_key = f"{vital}_min"
        hi_key = f"{vital}_max"
        if lo_key in vn and hi_key in vn:
            return float(vn[lo_key]), float(vn[hi_key])
        return None

    def normal_range(self, vital: str, stratum: str) -> Optional[tuple[float, float]]:
        """
        Public accessor for the stratum's normal range.

        model/features.py uses this to compute per-vital z-scores against the
        SAME ranges the rules layer uses, so the model and the explanation layer
        cannot disagree about what "normal" means for a stratum.
        """
        return self._get_normal(vital, stratum)

    def is_vital_abnormal(self, vital: str, value: float, stratum: str) -> ThresholdResult:
        """
        Assess whether a vital value is abnormal for this stratum.

        Returns ThresholdResult with is_abnormal flag and directional info.
        """
        normal_range = self._get_normal(vital, stratum)
        if normal_range is None:
            # Unknown vital for this stratum — treat as unknown, not normal
            return ThresholdResult(
                vital=vital, value=value, stratum=stratum,
                is_abnormal=False, direction="unknown", deviation_sigma=0.0,
            )

        lo, hi = normal_range
        mid = (lo + hi) / 2.0
        half_range = max((hi - lo) / 2.0, 0.01)

        if value < lo:
            direction = "low"
            is_abnormal = True
            deviation_sigma = (lo - value) / half_range
        elif value > hi:
            direction = "high"
            is_abnormal = True
            deviation_sigma = (value - hi) / half_range
        else:
            direction = "normal"
            is_abnormal = False
            deviation_sigma = 0.0

        return ThresholdResult(
            vital=vital,
            value=value,
            stratum=stratum,
            is_abnormal=is_abnormal,
            direction=direction,
            deviation_sigma=round(deviation_sigma, 3),
        )

    def count_abnormal_vitals(
        self, vitals: dict[str, float], stratum: str
    ) -> tuple[int, list[ThresholdResult]]:
        """
        Check all provided vitals and return (count_abnormal, [ThresholdResult]).
        Used by the emergency rule engine to detect multiple-critical-parameters cases.
        """
        results = [
            self.is_vital_abnormal(vital, value, stratum)
            for vital, value in vitals.items()
        ]
        n_abnormal = sum(1 for r in results if r.is_abnormal)
        return n_abnormal, results


# Module-level singleton
_thresholds: Optional[VitalThresholds] = None


def get_thresholds() -> VitalThresholds:
    global _thresholds
    if _thresholds is None:
        _thresholds = VitalThresholds()
    return _thresholds
