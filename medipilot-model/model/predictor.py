"""
medipilot-model/model/predictor.py

The serve-time seam between the trained artifact and score_patient().

Returns a calibrated probability of the primary outcome plus the source that
produced it. When anything goes wrong — no artifact, drifted feature contract,
an exception inside predict — this returns (None, "fallback_heuristic") and the
caller uses the hand-coded scorer. It never raises into the triage path.
"""

from __future__ import annotations

from typing import Optional

import numpy as np

from model.artifact import get_artifact, note_predict_error

SOURCE_MODEL = "model"
SOURCE_FALLBACK = "fallback_heuristic"
SOURCE_RED_FLAG = "red_flag_rule"


def _apply_calibration_one(art, p_raw: float, stratum: str) -> float:
    method = art.methods.get(str(stratum), "pooled_fallback")
    cal = art.calibrators.get(str(stratum)) if method != "pooled_fallback" else art.calibrators.get("__pooled__")
    if cal is None:
        cal = art.calibrators.get("__pooled__")
        method = "isotonic"

    if method == "platt":
        eps = 1e-6
        pc = float(np.clip(p_raw, eps, 1 - eps))
        z = np.log(pc / (1 - pc))
        out = float(cal.predict_proba(np.array([[z]]))[0, 1])
    else:
        out = float(cal.predict(np.array([p_raw]))[0])
    return float(np.clip(out, 1e-4, 1 - 1e-4))


def predict_p_critical(
    feature_row: np.ndarray,
    stratum: str,
) -> tuple[Optional[float], str]:
    """
    Calibrated P(critical composite) for one patient.

    Returns (probability, source). A None probability means the caller must fall
    back to the hand-coded scorer.
    """
    art = get_artifact()
    if art is None:
        return None, SOURCE_FALLBACK

    try:
        row = np.asarray(feature_row, dtype=np.float64).reshape(1, -1)

        # The auxiliary (stacked) head fills its own column at serve time.
        from model.features import FEATURE_NAMES
        aux_col = FEATURE_NAMES.index("aux_derangement_oof")
        row[0, aux_col] = float(art.aux.predict(row)[0])

        p_raw = float(art.clf.predict_proba(row)[0, 1])
        return _apply_calibration_one(art, p_raw, stratum), SOURCE_MODEL
    except Exception:
        # A model exception must never 500 the triage API. Count it so
        # /model-status can surface it, then degrade to the rule card.
        note_predict_error()
        return None, SOURCE_FALLBACK


def band_thresholds() -> Optional[tuple[float, float]]:
    """(p*_yellow, p*_red) from the artifact, or None when unavailable."""
    art = get_artifact()
    if art is None:
        return None
    t = art.thresholds
    return float(t["p_star_yellow"]), float(t["p_star_red"])


def conformal_spec() -> Optional[dict]:
    art = get_artifact()
    return art.conformal if art else None
