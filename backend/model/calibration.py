"""
backend/model/calibration.py

Per-stratum risk calibration — MECHANISM 2 of the two separate mechanisms.
  - Thresholds: what counts as abnormal (thresholds.py)
  - Calibration: how a given abnormality maps to risk, for this stratum (THIS FILE)

Conflating them produces a model that is right about vitals and wrong about danger.

Key geriatric insight from the brief:
  "Normal vitals carry much weaker reassurance in the geriatric stratum."
  → A 75-year-old with the SAME vital numbers as a 30-year-old gets a
    HIGHER calibrated risk score, because the reassurance_decay is lower.

Model version and calibration version are tracked in every output object.
"""

from __future__ import annotations

import pathlib
from dataclasses import dataclass
from typing import Optional

import yaml
import numpy as np


_CONFIG_PATH = pathlib.Path(__file__).parent.parent / "config" / "age_strata.yaml"

MODEL_VERSION = "medipilot-model-v0.1.0"
CALIBRATION_VERSION = "synthetic-isotonic-v0.1.0"


@dataclass
class CalibrationResult:
    raw_score: float            # pre-calibration risk score [0, 1]
    calibrated_score: float     # post-calibration risk score [0, 1]
    stratum: str
    calibration_weight: float   # from config
    reassurance_decay: float    # from config
    abnormal_vital_floor_applied: bool  # True if the stratum floor raised the score
    model_version: str
    calibration_version: str


class StratumCalibrator:
    """
    Applies per-stratum calibration to a raw risk score.

    The calibration_weight multiplier means that a given deviation from
    normal in a high-risk stratum (neonate, geriatric) results in a
    proportionally larger calibrated risk.

    The reassurance_decay controls how much normal vitals reduce the risk
    estimate. In the geriatric stratum (decay=0.25), normal vitals offer
    very little reassurance.
    """

    def __init__(self, config_path: pathlib.Path = _CONFIG_PATH):
        with open(config_path, encoding="utf-8") as f:
            cfg = yaml.safe_load(f)
        self._strata = cfg["strata"]

    def get_reassurance_decay(self, stratum: str) -> float:
        """
        Reassurance-decay lookup, exposed so the explanation layer
        (_raw_risk_score in risk_model.py) can label factors_against entries
        with how much reassurance a normal reading actually carries in this
        stratum, without duplicating the YAML load.
        """
        s = self._strata.get(stratum, self._strata["adult"])
        return float(s["reassurance_decay"])

    def calibrate(
        self,
        raw_score: float,
        stratum: str,
        n_abnormal_vitals: int,
        n_total_vitals: int,
        trend_slope: float = 0.0,   # positive = deteriorating
    ) -> CalibrationResult:
        """
        Calibrate a raw risk score for a specific stratum.

        The calibration accounts for:
        1. Stratum calibration_weight — abnormalities are more dangerous in
           vulnerable strata.
        2. Reassurance_decay — normal vitals are less reassuring in geriatric/neonate.
        3. Trend — a deteriorating trend amplifies the risk estimate (per the
           brief: "trend beats snapshot" for the child stratum).

        Args:
            raw_score: [0, 1] base risk score from the feature-weighted model
            stratum: resolved stratum key
            n_abnormal_vitals: how many vitals are outside normal range
            n_total_vitals: total vitals assessed
            trend_slope: direction of change (positive = worsening)
        """
        s = self._strata.get(stratum, self._strata["adult"])
        cal_weight = float(s["calibration_weight"])
        reassurance_decay = float(s["reassurance_decay"])

        # Fraction of normal vitals (higher = more reassuring, but decayed by stratum)
        n_normal = max(0, n_total_vitals - n_abnormal_vitals)
        normal_frac = n_normal / max(n_total_vitals, 1)

        # How much the normal vitals reduce the raw score — decayed by stratum
        reassurance_reduction = normal_frac * reassurance_decay * 0.25

        # Trend amplifier: deteriorating trend adds up to 15% to the score
        trend_amplifier = max(0.0, trend_slope * 0.15)

        # Calibrated score:
        # Start from raw_score, apply weight (lifts score in vulnerable strata),
        # subtract reassurance, add trend
        calibrated = raw_score * cal_weight - reassurance_reduction + trend_amplifier

        # Vulnerable-stratum floor: explicit per-stratum config, not a magic
        # number gated on calibration_weight. A stratum opts into the floor by
        # setting abnormal_vital_floor in age_strata.yaml; strata that should
        # never floor (adult, adolescent) set it to null. This is what fixed
        # the bug where "child" (calibration_weight 1.3) fell through an
        # implicit ">1.4" gate and a febrile toddler scored Green.
        floor = s.get("abnormal_vital_floor")
        floor_applied = False
        if floor is not None and n_abnormal_vitals > 0 and calibrated < float(floor):
            calibrated = float(floor)
            floor_applied = True

        calibrated = float(np.clip(calibrated, 0.0, 1.0))

        return CalibrationResult(
            raw_score=round(raw_score, 4),
            calibrated_score=round(calibrated, 4),
            stratum=stratum,
            calibration_weight=cal_weight,
            reassurance_decay=reassurance_decay,
            abnormal_vital_floor_applied=floor_applied,
            model_version=MODEL_VERSION,
            calibration_version=CALIBRATION_VERSION,
        )


# Module-level singleton
_calibrator: Optional[StratumCalibrator] = None


def get_calibrator() -> StratumCalibrator:
    global _calibrator
    if _calibrator is None:
        _calibrator = StratumCalibrator()
    return _calibrator


def calibrate(
    raw_score: float,
    stratum: str,
    n_abnormal_vitals: int,
    n_total_vitals: int,
    trend_slope: float = 0.0,
) -> CalibrationResult:
    """Convenience wrapper."""
    return get_calibrator().calibrate(
        raw_score, stratum, n_abnormal_vitals, n_total_vitals, trend_slope
    )


def get_reassurance_decay(stratum: str) -> float:
    """Convenience wrapper."""
    return get_calibrator().get_reassurance_decay(stratum)
