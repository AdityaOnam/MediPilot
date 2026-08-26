"""
tests/test_features.py

Guards on the feature extractor: NaN discipline, train/serve parity, and the
leakage registry.

The NaN tests matter more than they look. HistGradientBoosting learns a per-node
missing direction only from real np.nan. A -999 or 0 sentinel silently converts
"we don't know this patient's SpO2" into "this patient's SpO2 is catastrophic",
which for a triage model is the dangerous direction.
"""

import datetime

import numpy as np
import pytest

from model import features as fx
from model.features import (
    FEATURE_NAMES, N_FEATURES, FeatureInputs, VitalHistory,
    build_feature_row, from_patient_record, from_trajectory_snapshot,
)
from model.feature_registry import assert_features_permitted, LeakageViolation
from model.risk_model import PatientRecord
from model.age_stratum import resolve_stratum

UTC = datetime.timezone.utc
NOW = datetime.datetime(2026, 8, 22, 14, 0, 0, tzinfo=UTC)
NOW_ISO = NOW.isoformat()


def _inputs(vitals_now, history=None, stratum="adult"):
    return FeatureInputs(
        vitals_now=vitals_now,
        reading_age_minutes={k: 0.0 for k in vitals_now},
        stale_flags={k: False for k in vitals_now},
        stratum=stratum,
        stratum_inferred=False,
        age_days=365 * 40,
        history=history,
    )


# ---------------------------------------------------------------------------
# NaN discipline
# ---------------------------------------------------------------------------

def test_missing_vital_produces_nan_not_sentinel():
    fi = _inputs({"hr": 80, "rr": None, "bp_sys": 120, "spo2": None,
                  "temp_c": 37.0, "gcs": 15, "pain_score": 2})
    row = build_feature_row(fi)
    assert np.isnan(row[FEATURE_NAMES.index("rr_value")])
    assert np.isnan(row[FEATURE_NAMES.index("spo2_value")])
    assert not np.isnan(row[FEATURE_NAMES.index("hr_value")])


def test_no_finite_sentinel_values():
    """No column may encode 'missing' as -999 / -1 / 9999."""
    fi = _inputs({v: None for v in fx.VITALS})
    row = build_feature_row(fi)
    for sentinel in (-999.0, -1.0, 9999.0):
        assert not np.any(row == sentinel), f"sentinel {sentinel} present in feature row"


def test_nan_branch_is_actually_used():
    """
    The only test that proves native NaN handling is live rather than merely
    available: train a tiny model where NaN itself carries the signal and assert
    the prediction differs from every finite value.
    """
    from sklearn.ensemble import HistGradientBoostingClassifier

    rng = np.random.default_rng(0)
    n = 400
    X = rng.normal(0, 1, size=(n, 2))
    y = rng.integers(0, 2, size=n)
    # rows where feature 0 is NaN are always class 1
    X[y == 1, 0] = np.nan

    m = HistGradientBoostingClassifier(max_iter=50, random_state=0).fit(X, y)
    p_nan = m.predict_proba(np.array([[np.nan, 0.0]]))[0, 1]
    p_finite = [m.predict_proba(np.array([[v, 0.0]]))[0, 1] for v in (-3, -1, 0, 1, 3)]
    assert all(abs(p_nan - pf) > 0.2 for pf in p_finite), (
        "NaN is not being routed differently from finite values"
    )


def test_zero_readings_is_zero_not_nan():
    """n_readings=0 is a real observation (no history), not missing data."""
    fi = _inputs({"hr": 80}, history=None)
    row = build_feature_row(fi)
    assert row[FEATURE_NAMES.index("hr_n_readings")] == 0.0


def test_gcs_z_is_not_exploded_by_zero_width_range():
    """
    GCS normal range is 15-15 in every stratum, so the generic
    (value - mid)/half_range would divide by ~0 and a one-point drop would
    produce z ~= 100, dominating every split. Must be special-cased.
    """
    fi = _inputs({"gcs": 14})
    row = build_feature_row(fi)
    z = row[FEATURE_NAMES.index("gcs_z_stratum")]
    assert abs(z) < 10, f"gcs z-score exploded: {z}"


# ---------------------------------------------------------------------------
# Leakage registry
# ---------------------------------------------------------------------------

def test_every_shipped_feature_is_permitted():
    assert_features_permitted(FEATURE_NAMES)   # raises on violation


@pytest.mark.parametrize("bad", [
    "condition_id", "typical_band", "trajectory_shape", "severity_path",
    "acuity", "frailty", "p_event", "red_flag_observations", "current_band",
    "critical_composite_h180", "s_max_future",
])
def test_prohibited_fields_are_blocked(bad):
    with pytest.raises(LeakageViolation):
        assert_features_permitted([bad])


def test_unregistered_field_fails_closed():
    """A brand-new generator field must fail the build until classified."""
    with pytest.raises(LeakageViolation):
        assert_features_permitted(["some_field_nobody_classified_yet"])


def test_prohibited_fields_absent_from_serving_input():
    """Structural check: PatientRecord cannot even carry the latent."""
    rec = PatientRecord(patient_id="X")
    for banned in ("severity_path", "acuity", "frailty", "condition_id", "p_event"):
        assert not hasattr(rec, banned), f"PatientRecord exposes {banned}"


# ---------------------------------------------------------------------------
# Train/serve parity
# ---------------------------------------------------------------------------

def test_train_and_serve_adapters_agree():
    """
    The same patient, built through both adapters, must produce identical rows.

    If training reads raw series values while serving reads freshness-filtered
    ones, every model input differs in production and nothing else would report
    it.
    """
    ts = NOW.isoformat()
    traj = {
        "patient_id": "P", "condition_id": "C01", "stratum": "adult",
        "age_days": 365 * 40, "t0": ts,
        "series": {
            v: [{"value": 80.0, "timestamp": ts, "source": "recheck_station",
                 "validity": "valid", "vital": v}]
            for v in fx.VITALS
        },
    }
    fi_train = from_trajectory_snapshot(traj, k_step=0, stratum="adult")
    row_train = build_feature_row(fi_train)

    rec = PatientRecord(
        patient_id="P", age_days=365 * 40,
        **{v: (80.0, ts, "recheck_station", "valid") for v in fx.VITALS},
    )
    fi_serve = from_patient_record(rec, resolve_stratum(365 * 40, True), NOW)
    row_serve = build_feature_row(fi_serve)

    assert len(row_train) == len(row_serve) == N_FEATURES
    for i, name in enumerate(FEATURE_NAMES):
        a, b = row_train[i], row_serve[i]
        if np.isnan(a) and np.isnan(b):
            continue
        assert a == pytest.approx(b, abs=1e-9), (
            f"train/serve skew on '{name}': train={a} serve={b}"
        )


def test_serve_adapter_with_history_populates_trend_features():
    """
    B1 guard: when vitals_history is passed through the API path (as
    PatientRecord.vitals_history), the serving adapter must populate
    slope_per_hour / delta_30min — the same features the training adapter
    builds from a trajectory with multiple readings.

    This is the live-API-shaped fixture required by the B1 implementation plan.
    Without this test, from_patient_record() could silently drop the history
    dict and the train/serve gap would reopen invisibly.
    """
    # Two HR readings 30 minutes apart, rising from 70 -> 100 bpm.
    ts_old = datetime.datetime(2026, 8, 22, 13, 30, 0, tzinfo=UTC).isoformat()
    ts_now = NOW.isoformat()

    history_dict = {
        "hr": [
            (70.0, ts_old, "recheck_station", "valid"),
            (100.0, ts_now, "recheck_station", "valid"),
        ]
    }
    rec = PatientRecord(
        patient_id="P2",
        age_days=365 * 40,
        hr=(100.0, ts_now, "recheck_station", "valid"),
        vitals_history=history_dict,
    )
    fi = from_patient_record(rec, resolve_stratum(365 * 40, True), NOW)
    row = build_feature_row(fi)

    # slope_per_hour for HR: delta = +30 bpm over 30 min = +60 bpm/hr
    slope_idx = FEATURE_NAMES.index("hr_slope_per_hour")
    delta_idx = FEATURE_NAMES.index("hr_delta_30min")

    assert not np.isnan(row[slope_idx]), (
        "slope_per_hour is NaN — vitals_history is not reaching from_patient_record()"
    )
    assert row[slope_idx] == pytest.approx(60.0, abs=5.0), (
        f"slope_per_hour expected ~60 bpm/hr, got {row[slope_idx]:.2f}"
    )
    assert not np.isnan(row[delta_idx]), (
        "delta_30min is NaN — vitals_history is not reaching from_patient_record()"
    )


def test_feature_names_are_frozen_and_ordered():
    assert len(FEATURE_NAMES) == N_FEATURES
    assert len(set(FEATURE_NAMES)) == N_FEATURES, "duplicate feature name"
    assert FEATURE_NAMES == fx._build_names(), "feature order is not deterministic"
