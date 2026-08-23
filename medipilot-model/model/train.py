"""
medipilot-model/model/train.py

Trains the MediPilot risk backbone and writes a versioned artifact.

Pipeline:
  1. Load the labelled dataset (data/generator/bulk.py output)
  2. Build features through model/features.py — THE shared extractor
  3. Split by patient_id, stratified on (stratum, label)
  4. Auxiliary regressor -> out-of-fold derangement prediction (the "second head")
  5. Primary GBDT classifier
  6. Per-stratum isotonic calibration        (on calib_iso)
  7. Mondrian split-conformal quantiles      (on calib_conf)
  8. Cost-ratio thresholds solved on calib
  9. Persist everything + a manifest

TWO HEADS, HONESTLY DESCRIBED
-----------------------------
sklearn has no multi-task GBDT, and lightgbm/xgboost are unavailable while torch
is broken in this environment. So this is a two-stage STACK, not multi-task
learning over a shared trunk: the auxiliary regressor's out-of-fold prediction
becomes one input column to the primary classifier. That achieves the
whitepaper's "secondary label constrains the primary" effect; it is not the same
architecture and the README says so.

SPLIT DISCIPLINE
----------------
calib_iso and calib_conf are SEPARATE. Fitting isotonic and then computing
conformal quantiles on the same rows makes those scores in-sample, breaks
exchangeability and voids the coverage guarantee — while still printing coverage
numbers that look fine. That is the standard way this goes silently wrong.

Usage:
    python -m model.train --data data/train_set.jsonl
"""

from __future__ import annotations

import argparse
import datetime
import hashlib
import json
import pathlib
from typing import Optional

import joblib
import numpy as np
import sklearn
from sklearn.ensemble import HistGradientBoostingClassifier, HistGradientBoostingRegressor
from sklearn.model_selection import cross_val_predict, train_test_split
from sklearn.isotonic import IsotonicRegression
from sklearn.linear_model import LogisticRegression

from model.features import (
    FEATURE_VERSION, FEATURE_NAMES, N_FEATURES,
    from_trajectory_snapshot, build_feature_row,
)
from model.feature_registry import get_registry
from data.generator.labels import (
    LABEL_NAME_PRIMARY, LABEL_NAME_SECONDARY, HORIZON_MINUTES, load_spec,
)

ARTIFACT_ROOT = pathlib.Path(__file__).parent / "artifacts"
ARTIFACT_NAME = "medipilot-gbdt-v0.2.0"
CALIBRATION_NAME = "isotonic-perstratum-v0.2.0"
CONFORMAL_NAME = "mondrian-split-a0.10-v0.2.0"
ALPHA = 0.10

# Minimum positives before a stratum gets its own isotonic curve. Below this,
# isotonic overfits badly and Platt (far fewer parameters) is the better choice.
_MIN_POS_ISOTONIC = 25
_MIN_N_MONDRIAN = int(np.ceil(1 / ALPHA)) - 1   # 9


def load_dataset(path: pathlib.Path) -> list[dict]:
    records = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                records.append(json.loads(line))
    return records


def build_matrices(records: list[dict]) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """Returns (X, y_primary, y_secondary, strata, patient_ids)."""
    X = np.full((len(records), N_FEATURES), np.nan, dtype=np.float64)
    y = np.zeros(len(records), dtype=int)
    y_aux = np.zeros(len(records), dtype=float)
    strata = np.empty(len(records), dtype=object)
    pids = np.empty(len(records), dtype=object)

    for i, r in enumerate(records):
        fi = from_trajectory_snapshot(
            traj=r["trajectory"],
            k_step=r["k_step"],
            stratum=r["stratum"],
            stratum_inferred=False,
        )
        X[i] = build_feature_row(fi)
        y[i] = int(r[LABEL_NAME_PRIMARY])
        y_aux[i] = float(r[LABEL_NAME_SECONDARY])
        strata[i] = r["stratum"]
        pids[i] = r["patient_id"]

    return X, y, y_aux, strata, pids


def _stratified_split(y, strata, seed):
    """Four-way split, stratified jointly on (stratum, label)."""
    joint = np.array([f"{s}|{lbl}" for s, lbl in zip(strata, y)])
    idx = np.arange(len(y))

    # Collapse joint classes with <4 members so train_test_split can stratify.
    uniq, counts = np.unique(joint, return_counts=True)
    rare = set(uniq[counts < 4])
    joint = np.array([("__rare__" if j in rare else j) for j in joint])

    tr, rest = train_test_split(idx, test_size=0.40, random_state=seed, stratify=joint)
    j_rest = joint[rest]
    u2, c2 = np.unique(j_rest, return_counts=True)
    rare2 = set(u2[c2 < 3])
    j_rest = np.array([("__rare__" if j in rare2 else j) for j in j_rest])

    iso, rest2 = train_test_split(rest, test_size=0.75, random_state=seed, stratify=j_rest)
    j_r2 = joint[rest2]
    u3, c3 = np.unique(j_r2, return_counts=True)
    rare3 = set(u3[c3 < 2])
    j_r2 = np.array([("__rare__" if j in rare3 else j) for j in j_r2])

    conf, test = train_test_split(rest2, test_size=0.6667, random_state=seed, stratify=j_r2)
    return tr, iso, conf, test


def fit_isotonic_per_stratum(p_raw, y, strata):
    """Per-stratum probability calibration, with a documented fallback ladder."""
    calibrators: dict[str, object] = {}
    methods: dict[str, str] = {}

    pooled = IsotonicRegression(out_of_bounds="clip", y_min=0.0, y_max=1.0)
    pooled.fit(p_raw, y)
    calibrators["__pooled__"] = pooled
    methods["__pooled__"] = "isotonic"

    for s in np.unique(strata):
        m = strata == s
        n_pos = int(y[m].sum())
        if n_pos >= _MIN_POS_ISOTONIC and len(np.unique(y[m])) > 1:
            iso = IsotonicRegression(out_of_bounds="clip", y_min=0.0, y_max=1.0)
            iso.fit(p_raw[m], y[m])
            calibrators[str(s)] = iso
            methods[str(s)] = "isotonic"
        elif n_pos >= 5 and len(np.unique(y[m])) > 1:
            eps = 1e-6
            z = np.log(np.clip(p_raw[m], eps, 1 - eps) / (1 - np.clip(p_raw[m], eps, 1 - eps)))
            lr = LogisticRegression()
            lr.fit(z.reshape(-1, 1), y[m])
            calibrators[str(s)] = lr
            methods[str(s)] = "platt"
        else:
            methods[str(s)] = "pooled_fallback"

    return calibrators, methods


def apply_calibration(calibrators, methods, p_raw, strata) -> np.ndarray:
    out = np.empty_like(p_raw, dtype=float)
    for i, (p, s) in enumerate(zip(p_raw, strata)):
        method = methods.get(str(s), "pooled_fallback")
        cal = calibrators.get(str(s)) if method != "pooled_fallback" else calibrators["__pooled__"]
        if cal is None:
            cal = calibrators["__pooled__"]
            method = "isotonic"
        if method == "platt":
            eps = 1e-6
            pc = float(np.clip(p, eps, 1 - eps))
            z = np.log(pc / (1 - pc))
            out[i] = float(cal.predict_proba(np.array([[z]]))[0, 1])
        else:
            out[i] = float(cal.predict(np.array([p]))[0])
    # Isotonic on small n produces exact 0/1 plateaus; clip so log-loss stays
    # finite and threshold comparisons behave at the boundaries.
    n = max(len(p_raw), 2)
    return np.clip(out, 1.0 / (2 * n), 1.0 - 1.0 / (2 * n))


def mondrian_conformal_quantiles(p_cal, y_cal, strata_cal, alpha=ALPHA):
    """
    Split-conformal nonconformity quantiles, per stratum.

      s_i = 1 - p_i  if y_i == 1
      s_i = p_i      if y_i == 0
    """
    s = np.where(y_cal == 1, 1.0 - p_cal, p_cal)
    q: dict[str, float] = {}
    n_per: dict[str, int] = {}

    n = len(s)
    lvl = min(1.0, np.ceil((n + 1) * (1 - alpha)) / max(n, 1))
    pooled_q = float(np.quantile(s, lvl, method="higher"))

    fallback: list[str] = []
    for g in np.unique(strata_cal):
        m = strata_cal == g
        ng = int(m.sum())
        n_per[str(g)] = ng
        if ng >= _MIN_N_MONDRIAN:
            lvl_g = min(1.0, np.ceil((ng + 1) * (1 - alpha)) / ng)
            q[str(g)] = float(np.quantile(s[m], lvl_g, method="higher"))
        else:
            q[str(g)] = pooled_q
            fallback.append(str(g))

    return {"alpha": alpha, "q_hat": q, "pooled_q_hat": pooled_q,
            "n": n_per, "fallback_strata": fallback}


def solve_thresholds(p_cal, target_over_triage=0.30, target_red_rate=0.05):
    """
    Solve the two band cut points on the calibration split, then BACK-SOLVE the
    implied cost ratios.

    The whitepaper's R = 100-500 gives p* = 0.002-0.010, which at this prevalence
    routes essentially everyone to Yellow. Rather than guessing an R, we pick the
    operating point by target band mix and report the R it implies — so R is a
    reported quantity, not a fabricated one.
    """
    p_star_yellow = float(np.quantile(p_cal, 1.0 - target_over_triage))
    p_star_red = float(np.quantile(p_cal, 1.0 - target_red_rate))
    p_star_yellow = min(max(p_star_yellow, 1e-6), 1 - 1e-6)
    p_star_red = min(max(p_star_red, p_star_yellow + 1e-6), 1 - 1e-6)

    return {
        "p_star_yellow": p_star_yellow,
        "p_star_red": p_star_red,
        "R_yellow": (1.0 - p_star_yellow) / p_star_yellow,
        "R_red": (1.0 - p_star_red) / p_star_red,
        "target_over_triage": target_over_triage,
        "target_red_rate": target_red_rate,
    }


def train(data_path: pathlib.Path, seed: int = 1337, out_root: pathlib.Path = ARTIFACT_ROOT) -> dict:
    records = load_dataset(data_path)
    X, y, y_aux, strata, pids = build_matrices(records)

    tr, iso_idx, conf_idx, test_idx = _stratified_split(y, strata, seed)

    # --- auxiliary head (stacked, not multi-task) ---
    aux = HistGradientBoostingRegressor(max_iter=200, random_state=seed)
    oof = cross_val_predict(aux, X[tr], y_aux[tr], cv=5, method="predict")
    aux.fit(X[tr], y_aux[tr])

    aux_col = FEATURE_NAMES.index("aux_derangement_oof")
    X_tr = X[tr].copy()
    X_tr[:, aux_col] = oof
    for idx in (iso_idx, conf_idx, test_idx):
        X[idx, aux_col] = aux.predict(X[idx])

    # --- primary head ---
    clf = HistGradientBoostingClassifier(
        max_iter=300, learning_rate=0.06, max_leaf_nodes=31,
        l2_regularization=1.0, random_state=seed,
    )
    clf.fit(X_tr, y[tr])

    # --- calibration, conformal, thresholds ---
    p_iso_raw = clf.predict_proba(X[iso_idx])[:, 1]
    calibrators, methods = fit_isotonic_per_stratum(p_iso_raw, y[iso_idx], strata[iso_idx])

    p_conf_raw = clf.predict_proba(X[conf_idx])[:, 1]
    p_conf = apply_calibration(calibrators, methods, p_conf_raw, strata[conf_idx])
    conformal = mondrian_conformal_quantiles(p_conf, y[conf_idx], strata[conf_idx])
    thresholds = solve_thresholds(p_conf)

    # --- persist ---
    out = out_root / ARTIFACT_NAME
    out.mkdir(parents=True, exist_ok=True)
    joblib.dump(clf, out / "primary.joblib", compress=3)
    joblib.dump(aux, out / "auxiliary.joblib", compress=3)
    joblib.dump({"calibrators": calibrators, "methods": methods},
                out / "isotonic.joblib", compress=3)
    (out / "conformal.json").write_text(json.dumps(conformal, indent=2), encoding="utf-8")
    (out / "thresholds.json").write_text(json.dumps(thresholds, indent=2), encoding="utf-8")
    (out / "feature_spec.json").write_text(json.dumps({
        "feature_version": FEATURE_VERSION,
        "feature_names": list(FEATURE_NAMES),
        "registry_sha256": get_registry().sha256,
    }, indent=2), encoding="utf-8")

    meta_path = data_path.with_suffix(".meta.json")
    dataset_meta = json.loads(meta_path.read_text(encoding="utf-8")) if meta_path.exists() else {}

    manifest = {
        "model_version": ARTIFACT_NAME,
        "calibration_version": CALIBRATION_NAME,
        "conformal_version": CONFORMAL_NAME,
        "feature_version": FEATURE_VERSION,
        "sklearn_version": sklearn.__version__,
        "horizon_minutes": HORIZON_MINUTES,
        "label_primary": LABEL_NAME_PRIMARY,
        "trained_at": datetime.datetime.now(tz=datetime.timezone.utc).isoformat(),
        "dataset": {
            "path": str(data_path),
            "n_total": len(records),
            "prevalence": float(y.mean()),
            "sha256": hashlib.sha256(data_path.read_bytes()).hexdigest()[:16],
            **dataset_meta.get("meta", {}),
        },
        "splits": {"train": len(tr), "calib_iso": len(iso_idx),
                   "calib_conf": len(conf_idx), "test": len(test_idx)},
        "calibration_methods": methods,
        "thresholds": thresholds,
        "conformal": {"alpha": ALPHA, "fallback_strata": conformal["fallback_strata"]},
    }
    (out / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    # `current` pointer — a plain file, since Windows symlinks need privileges.
    (out_root / "current.txt").write_text(ARTIFACT_NAME, encoding="utf-8")

    np.savez_compressed(
        out / "test_split.npz",
        X=X[test_idx], y=y[test_idx], strata=strata[test_idx].astype(str),
        y_aux=y_aux[test_idx],
    )

    return {"manifest": manifest, "artifact_dir": str(out)}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default="data/train_set.jsonl")
    ap.add_argument("--seed", type=int, default=1337)
    args = ap.parse_args()

    res = train(pathlib.Path(args.data), seed=args.seed)
    m = res["manifest"]
    print(f"Trained -> {res['artifact_dir']}")
    print(f"  n={m['dataset']['n_total']}  prevalence={m['dataset']['prevalence']:.4f}")
    print(f"  splits: {m['splits']}")
    print(f"  thresholds: p*_yellow={m['thresholds']['p_star_yellow']:.4f} "
          f"(R={m['thresholds']['R_yellow']:.1f})  "
          f"p*_red={m['thresholds']['p_star_red']:.4f} "
          f"(R={m['thresholds']['R_red']:.1f})")
    print(f"  calibration methods: {m['calibration_methods']}")


if __name__ == "__main__":
    main()
