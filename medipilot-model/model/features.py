"""
medipilot-model/model/features.py

THE single feature extractor. Both training and serving go through this module
and nothing else builds a feature matrix.

Why this matters more than it looks: if training reads `series[-1]` raw while
`score_patient()` reads a freshness-filtered value, every model input differs
between train and production and no test reports it. That is train/serve skew,
and it is silent by construction. `tests/test_train_serve_parity.py` builds the
same patient through both adapters and asserts identical rows.

Missing-value discipline: missing vitals stay as np.nan. No imputation, no
sentinel, no fillna. HistGradientBoosting learns a per-node missing direction
only from real NaN — a -999 sentinel silently converts "unknown" into "extremely
abnormal", which for a triage model is the dangerous direction.
"""

from __future__ import annotations

import datetime
from dataclasses import dataclass
from typing import Iterable, Optional

import numpy as np

from model.feature_registry import assert_features_permitted
from model.freshness import check_freshness, reading_age_minutes

FEATURE_VERSION = "fx-v1"

VITALS = ("hr", "rr", "bp_sys", "spo2", "temp_c", "gcs", "pain_score")

# Order must match config/age_strata.yaml so stratum_ord is meaningful.
STRATA = ("neonate", "infant", "child", "adolescent", "adult", "geriatric")

_PER_VITAL_SUFFIXES = (
    "value",
    "z_stratum",
    "age_minutes",
    "slope_per_hour",
    "delta_30min",
    "n_readings",
)

_GLOBAL_FEATURES = (
    "age_days",
    "stratum_ord",
    *[f"stratum_is_{s}" for s in STRATA],
    "stratum_inferred",
    "n_vitals_present",
    "n_vitals_missing",
    "n_vitals_stale",
    "max_reading_age_minutes",
    "history_span_minutes",
    "total_readings",
    "frac_readings_sensor_fail",
    "aux_derangement_oof",
)


def _build_names() -> tuple[str, ...]:
    names: list[str] = []
    for v in VITALS:
        for s in _PER_VITAL_SUFFIXES:
            names.append(f"{v}_{s}")
    names.extend(_GLOBAL_FEATURES)
    return tuple(names)


FEATURE_NAMES: tuple[str, ...] = _build_names()

# Enforced at import: it is not possible to load this module with a feature set
# that contains a prohibited column.
assert_features_permitted(FEATURE_NAMES)

_INDEX = {n: i for i, n in enumerate(FEATURE_NAMES)}
N_FEATURES = len(FEATURE_NAMES)

# GCS has a normal range of 15-15 in every stratum, so the generic
# (value - mid) / half_range formula divides by ~0 and a one-point drop yields a
# z of ~100, which would dominate every split. Special-cased.
_GCS_MAX = 15.0


@dataclass(frozen=True)
class VitalHistory:
    """Trailing readings for one vital, oldest -> newest."""
    values: tuple[float, ...]
    ages_minutes: tuple[float, ...]     # positive = older
    validities: tuple[str, ...]


@dataclass(frozen=True)
class FeatureInputs:
    """
    Everything the extractor needs, already freshness-filtered.

    Building this is the adapters' job; the extractor itself does no I/O and no
    freshness logic, so both paths are guaranteed to have applied the same rules.
    """
    vitals_now: dict[str, Optional[float]]
    reading_age_minutes: dict[str, Optional[float]]
    stale_flags: dict[str, bool]
    stratum: str
    stratum_inferred: bool
    age_days: Optional[int]
    history: Optional[dict[str, VitalHistory]] = None
    aux_derangement: Optional[float] = None


def feature_names() -> tuple[str, ...]:
    return FEATURE_NAMES


# ---------------------------------------------------------------------------
# Derived quantities
# ---------------------------------------------------------------------------

def _z_stratum(vital: str, value: float, stratum: str) -> float:
    """Signed deviation from the stratum's own normal range."""
    from model.thresholds import get_thresholds

    if vital == "gcs":
        return _GCS_MAX - value          # 0 = normal, larger = worse

    th = get_thresholds()
    rng = th.normal_range(vital, stratum) if hasattr(th, "normal_range") else None
    if not rng:
        return float("nan")
    lo, hi = rng
    if lo is None or hi is None:
        return float("nan")
    mid = (lo + hi) / 2.0
    half = max((hi - lo) / 2.0, 1e-6)
    return (value - mid) / half


def _slope_per_hour(hist: Optional[VitalHistory], window_min: float = 30.0) -> float:
    """OLS slope over the trailing window. NaN with fewer than 2 valid points."""
    if hist is None:
        return float("nan")
    pts = [
        (a, v)
        for a, v, ok in zip(hist.ages_minutes, hist.values, hist.validities)
        if ok == "valid" and a is not None and a <= window_min
    ]
    if len(pts) < 2:
        return float("nan")
    x = np.array([-p[0] for p in pts], dtype=float)   # time increasing
    y = np.array([p[1] for p in pts], dtype=float)
    if np.ptp(x) < 1e-9:
        return float("nan")
    slope_per_min = float(np.polyfit(x, y, 1)[0])
    return slope_per_min * 60.0


def _delta_30min(hist: Optional[VitalHistory], now_value: Optional[float]) -> float:
    if hist is None or now_value is None:
        return float("nan")
    # Need at least 2 points (the now_value and a reference ~30min ago).
    # With only one reading the delta is undefined, not 0.
    cands = [
        (abs(a - 30.0), v)
        for a, v, ok in zip(hist.ages_minutes, hist.values, hist.validities)
        if ok == "valid" and a > 0.5   # exclude the "now" reading itself
    ]
    if not cands:
        return float("nan")
    _, ref = min(cands, key=lambda t: t[0])
    return float(now_value - ref)


def _n_readings(hist: Optional[VitalHistory], window_min: float = 60.0) -> float:
    """
    Count trailing readings in the window. 0 is a real value, not NaN.

    Excludes the 'now' reading itself (age < 0.5 min): the current snapshot is
    always in vitals_now; including it here would cause train/serve skew when the
    serving adapter has no history object (and the training adapter always has
    at least the k_step reading at age=0).
    """
    if hist is None:
        return 0.0
    return float(sum(
        1 for a in hist.ages_minutes
        if a is not None and 0.5 <= a <= window_min
    ))


# ---------------------------------------------------------------------------
# Extraction
# ---------------------------------------------------------------------------

def build_feature_row(fi: FeatureInputs) -> np.ndarray:
    """Build one (N_FEATURES,) row. Missing values are np.nan by design."""
    row = np.full(N_FEATURES, np.nan, dtype=np.float64)

    n_present = 0
    n_missing = 0
    n_stale = 0
    ages: list[float] = []

    for v in VITALS:
        val = fi.vitals_now.get(v)
        hist = (fi.history or {}).get(v)

        if val is None:
            n_missing += 1
        else:
            n_present += 1
            row[_INDEX[f"{v}_value"]] = float(val)
            row[_INDEX[f"{v}_z_stratum"]] = _z_stratum(v, float(val), fi.stratum)

        age = fi.reading_age_minutes.get(v)
        if age is not None:
            row[_INDEX[f"{v}_age_minutes"]] = float(age)
            ages.append(float(age))

        if fi.stale_flags.get(v):
            n_stale += 1

        row[_INDEX[f"{v}_slope_per_hour"]] = _slope_per_hour(hist)
        row[_INDEX[f"{v}_delta_30min"]] = _delta_30min(hist, val)
        row[_INDEX[f"{v}_n_readings"]] = _n_readings(hist)

    if fi.age_days is not None:
        row[_INDEX["age_days"]] = float(fi.age_days)

    row[_INDEX["stratum_ord"]] = float(
        STRATA.index(fi.stratum) if fi.stratum in STRATA else -1
    )
    for s in STRATA:
        row[_INDEX[f"stratum_is_{s}"]] = 1.0 if fi.stratum == s else 0.0

    row[_INDEX["stratum_inferred"]] = 1.0 if fi.stratum_inferred else 0.0
    row[_INDEX["n_vitals_present"]] = float(n_present)
    row[_INDEX["n_vitals_missing"]] = float(n_missing)
    row[_INDEX["n_vitals_stale"]] = float(n_stale)
    row[_INDEX["max_reading_age_minutes"]] = float(max(ages)) if ages else np.nan

    if fi.history:
        spans = [
            max(h.ages_minutes) - min(h.ages_minutes)
            for h in fi.history.values() if h.ages_minutes
        ]
        row[_INDEX["history_span_minutes"]] = float(max(spans)) if spans else 0.0
        total = sum(len(h.values) for h in fi.history.values())
        row[_INDEX["total_readings"]] = float(total)
        bad = sum(
            sum(1 for x in h.validities if x != "valid") for h in fi.history.values()
        )
        row[_INDEX["frac_readings_sensor_fail"]] = (
            float(bad) / float(total) if total else 0.0
        )
    else:
        row[_INDEX["history_span_minutes"]] = 0.0
        row[_INDEX["total_readings"]] = float(n_present)
        row[_INDEX["frac_readings_sensor_fail"]] = 0.0

    if fi.aux_derangement is not None:
        row[_INDEX["aux_derangement_oof"]] = float(fi.aux_derangement)

    return row


def build_feature_matrix(rows: Iterable[FeatureInputs]) -> np.ndarray:
    mats = [build_feature_row(r) for r in rows]
    if not mats:
        return np.empty((0, N_FEATURES), dtype=np.float64)
    return np.vstack(mats)


# ---------------------------------------------------------------------------
# The two adapters — the only entry points
# ---------------------------------------------------------------------------

def from_patient_record(record, stratum_result, now: datetime.datetime) -> FeatureInputs:
    """SERVING adapter: PatientRecord -> FeatureInputs."""
    current_band = getattr(record, "current_band", None) or "yellow"

    vitals_now: dict[str, Optional[float]] = {}
    ages: dict[str, Optional[float]] = {}
    stale: dict[str, bool] = {}

    for v in VITALS:
        vt = getattr(record, v, None)
        val, is_stale, is_missing = check_freshness(vt, current_band, now)
        vitals_now[v] = None if is_missing else val
        stale[v] = bool(is_stale)
        ages[v] = reading_age_minutes(vt[1], now) if vt else None

    history = None
    raw_hist = getattr(record, "vitals_history", None)
    if raw_hist:
        history = {}
        for v in VITALS:
            entries = raw_hist.get(v) or []
            vals, ags, vals_ok = [], [], []
            for e in entries:
                value, ts_iso, _src, validity = e
                age = reading_age_minutes(ts_iso, now)
                if age is None:
                    continue
                vals.append(float(value))
                ags.append(float(age))
                vals_ok.append(validity)
            if vals:
                history[v] = VitalHistory(tuple(vals), tuple(ags), tuple(vals_ok))

    return FeatureInputs(
        vitals_now=vitals_now,
        reading_age_minutes=ages,
        stale_flags=stale,
        stratum=stratum_result.stratum,
        stratum_inferred=bool(stratum_result.inferred),
        age_days=getattr(record, "age_days", None),
        history=history,
    )


def from_trajectory_snapshot(
    traj: dict,
    k_step: int,
    stratum: str,
    stratum_inferred: bool = False,
    current_band: str = "yellow",
    t_step_min: int = 5,
) -> FeatureInputs:
    """
    TRAINING adapter: a serialised PatientTrajectory + prediction index k.

    Only readings at steps <= k are visible — the label lives strictly after k,
    so this cutoff is what makes the task prognostic rather than reconstructive.
    Applies the SAME freshness rules as the serving adapter.
    """
    series = traj.get("series", {})
    now = datetime.datetime.fromisoformat(traj["t0"]) + datetime.timedelta(
        minutes=k_step * t_step_min
    )

    vitals_now: dict[str, Optional[float]] = {}
    ages: dict[str, Optional[float]] = {}
    stale: dict[str, bool] = {}
    history: dict[str, VitalHistory] = {}

    for v in VITALS:
        readings = series.get(v, [])[: k_step + 1]
        if not readings:
            vitals_now[v] = None
            ages[v] = None
            stale[v] = False
            continue

        last = readings[-1]
        tup = (last["value"], last["timestamp"], last["source"], last["validity"])
        val, is_stale, is_missing = check_freshness(tup, current_band, now)
        vitals_now[v] = None if is_missing else val
        stale[v] = bool(is_stale)
        ages[v] = reading_age_minutes(last["timestamp"], now)

        vals, ags, oks = [], [], []
        for r in readings:
            age = reading_age_minutes(r["timestamp"], now)
            if age is None:
                continue
            vals.append(float(r["value"]))
            ags.append(float(age))
            oks.append(r["validity"])
        if vals:
            history[v] = VitalHistory(tuple(vals), tuple(ags), tuple(oks))

    return FeatureInputs(
        vitals_now=vitals_now,
        reading_age_minutes=ages,
        stale_flags=stale,
        stratum=stratum,
        stratum_inferred=stratum_inferred,
        age_days=traj.get("age_days"),
        history=history or None,
    )
