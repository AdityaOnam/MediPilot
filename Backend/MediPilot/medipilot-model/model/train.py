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
# Isotonic overfits below ~2,000 calibration cases (Niculescu-Mizil & Caruana);
# below this we use Platt, which has 2 parameters and targets the slope directly.
_MIN_N_ISOTONIC = 2000
_MIN_N_MONDRIAN = int(np.ceil(1 / ALPHA)) - 1   # 9

# ---------------------------------------------------------------------------
# Model factory (C-Group-1: GBDT bake-off)
# ---------------------------------------------------------------------------

# Clinically motivated monotone features: these should be non-decreasing with
# risk. A higher n_abnormal_vitals or lower GCS can only increase risk.
# Format for HistGBDT: +1 (increasing), -1 (decreasing), 0 (unconstrained).
_MONO_INCREASING = {"n_abnormal_vitals", "aux_derangement_oof"}
_MONO_DECREASING = {"gcs_z_stratum", "spo2_z_stratum"}   # z-score: neg = worse

MODEL_KINDS = ("hist", "lgbm", "xgboost", "hist-mono")


def _build_primary_clf(kind: str, seed: int, sample_weight_sum: float):
    """
    Build the primary classifier for Track C Group 1 bake-off.

    The ONLY variable across model kinds is the boosting implementation.
    Hyperparameter philosophy is matched across all three:
      - Moderate depth / leaves
      - L2 regularization
      - Early stopping on a 15% internal validation split
      - Positive class upweighting = 3x (same sample_weight logic)

    'hist-mono' adds monotonic constraints to the HistGBDT on clinically
    motivated features (RISK_ENGINE.md §9.2).
    """
    if kind == "hist":
        return HistGradientBoostingClassifier(
            max_iter=400, learning_rate=0.06, max_leaf_nodes=31,
            min_samples_leaf=40, l2_regularization=1.0,
            early_stopping=True, validation_fraction=0.15,
            n_iter_no_change=25, random_state=seed,
        )

    if kind == "hist-mono":
        cst = np.zeros(N_FEATURES, dtype=int)
        for i, name in enumerate(FEATURE_NAMES):
            if name in _MONO_INCREASING:
                cst[i] = 1
            elif name in _MONO_DECREASING:
                cst[i] = -1
        return HistGradientBoostingClassifier(
            max_iter=400, learning_rate=0.06, max_leaf_nodes=31,
            min_samples_leaf=40, l2_regularization=1.0,
            early_stopping=True, validation_fraction=0.15,
            n_iter_no_change=25, random_state=seed,
            monotonic_cst=cst.tolist(),
        )

    if kind == "lgbm":
        import lightgbm as lgb
        return lgb.LGBMClassifier(
            n_estimators=400, learning_rate=0.06, num_leaves=31,
            min_child_samples=40, reg_lambda=1.0,
            early_stopping_rounds=25, random_state=seed,
            verbose=-1,
        )

    if kind == "xgboost":
        import xgboost as xgb
        scale_pos = (sample_weight_sum - 3.0 * sample_weight_sum / 4.0) / (
            3.0 * sample_weight_sum / 4.0
        ) if sample_weight_sum > 0 else 1.0  # approximate; xgb handles via scale_pos_weight
        # xgboost uses scale_pos_weight instead of sample_weight for class balance
        return xgb.XGBClassifier(
            n_estimators=400, learning_rate=0.06, max_leaves=31,
            min_child_weight=40, reg_lambda=1.0,
            early_stopping_rounds=25, random_state=seed,
            eval_metric="logloss", verbosity=0, device="cpu",
        )

    raise ValueError(f"Unknown model kind: {kind!r}. Choose from {MODEL_KINDS}")



def load_dataset(path: pathlib.Path) -> list[dict]:
    records = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                records.append(json.loads(line))
    return records


# Fraction of training rows built WITHOUT vitals history.
#
# Measured skew this corrects: trend features (slope, delta) were populated in
# 94% of training rows and 0% at serve time, because the training adapter always
# has k_step>=6 prior readings while a PatientRecord arriving from intake
# usually carries a single snapshot. The model therefore learned to lean on
# trends it does not receive in production.
#
# This is the whitepaper's "train-time modality dropout", which was specified
# and never implemented for the trend block: force the model to produce a usable
# estimate from any subset of available modalities.
HISTORY_DROPOUT_RATE = 0.40


def build_matrices(records: list[dict], history_dropout: float = HISTORY_DROPOUT_RATE,
                   seed: int = 0):
    """Returns (X, y_primary, y_secondary, strata, patient_ids, s_max_future)."""
    import dataclasses
    rng_drop = np.random.default_rng(seed)
    X = np.full((len(records), N_FEATURES), np.nan, dtype=np.float64)
    y = np.zeros(len(records), dtype=int)
    y_aux = np.zeros(len(records), dtype=float)
    strata = np.empty(len(records), dtype=object)
    pids = np.empty(len(records), dtype=object)
    s_max = np.zeros(len(records), dtype=float)

    for i, r in enumerate(records):
        fi = from_trajectory_snapshot(
            traj=r["trajectory"],
            k_step=r["k_step"],
            stratum=r["stratum"],
            stratum_inferred=False,
        )
        # Modality dropout: some patients genuinely arrive with no history.
        if history_dropout > 0 and rng_drop.random() < history_dropout:
            fi = dataclasses.replace(fi, history=None)

        X[i] = build_feature_row(fi)
        y[i] = int(r[LABEL_NAME_PRIMARY])
        y_aux[i] = float(r[LABEL_NAME_SECONDARY])
        strata[i] = r["stratum"]
        pids[i] = r["patient_id"]
        # PROHIBITED as a feature — carried only so evaluate.py can compute the
        # severity-oracle ceiling on the held-out split.
        s_max[i] = float(r["s_max_future"])

    return X, y, y_aux, strata, pids, s_max


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


def _fit_platt(p_raw, y):
    """Logistic regression on logit(p) — 2 parameters, hard to overfit."""
    eps = 1e-6
    pc = np.clip(p_raw, eps, 1 - eps)
    z = np.log(pc / (1 - pc)).reshape(-1, 1)
    return LogisticRegression().fit(z, y)


def fit_isotonic_per_stratum(p_raw, y, strata):
    """
    Per-stratum probability calibration.

    METHOD CHOICE IS DELIBERATE. Isotonic is the stronger method given enough
    data, but it is unconstrained and overfits below roughly 2,000 calibration
    cases (Niculescu-Mizil & Caruana). Our calibration split is ~2,000 rows in
    TOTAL, so every individual stratum is far below that — and the symptom
    showed up exactly as the literature predicts: overall ECE looked fine
    (0.025) while the reliability SLOPE sat at 0.612 against an ideal of 1.0,
    i.e. probabilities systematically over-dispersed.
    #
    Platt scaling has two parameters and is fit on the logit scale, so it
    targets that slope directly and cannot overfit the way a step function can.
    It is therefore the default here, with isotonic reserved for strata that
    genuinely clear the data threshold.
    """
    calibrators: dict[str, object] = {}
    methods: dict[str, str] = {}

    # Pooled fallback: enough data to justify isotonic.
    if len(p_raw) >= _MIN_N_ISOTONIC and len(np.unique(y)) > 1:
        pooled = IsotonicRegression(out_of_bounds="clip", y_min=0.0, y_max=1.0)
        pooled.fit(p_raw, y)
        calibrators["__pooled__"] = pooled
        methods["__pooled__"] = "isotonic"
    else:
        calibrators["__pooled__"] = _fit_platt(p_raw, y)
        methods["__pooled__"] = "platt"

    for s in np.unique(strata):
        m = strata == s
        n_pos = int(y[m].sum())
        n_rows = int(m.sum())
        if n_rows >= _MIN_N_ISOTONIC and n_pos >= _MIN_POS_ISOTONIC and len(np.unique(y[m])) > 1:
            iso = IsotonicRegression(out_of_bounds="clip", y_min=0.0, y_max=1.0)
            iso.fit(p_raw[m], y[m])
            calibrators[str(s)] = iso
            methods[str(s)] = "isotonic"
        elif n_pos >= 5 and len(np.unique(y[m])) > 1:
            calibrators[str(s)] = _fit_platt(p_raw[m], y[m])
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


def solve_thresholds(p_cal, y_cal, max_green_miss=0.10, red_recall=0.40):
    """
    Solve the two band cut points from an UNDER-TRIAGE BUDGET, then back-solve
    the implied cost ratios.

    This replaces the previous band-mix formulation (p*_yellow at the 70th
    percentile of predictions), which was symmetric thinking applied to an
    asymmetric problem: it produced a model that sent 42% of critical patients to
    the Green queue while technically hitting its "30% over-triage" target. For a
    triage system the budget that matters is the one on MISSES.

      p*_yellow : the threshold that keeps at most `max_green_miss` of critical
                  patients out of Yellow-or-above. Set from the quantile of
                  predictions AMONG POSITIVES, so it is a recall guarantee.
      p*_red    : catches the top `red_recall` share of positives, keeping Red
                  actionable rather than flooding it.

    The resulting over-triage rate is a REPORTED consequence, not a target. That
    is the correct direction for the whitepaper's asymmetric cost structure: fix
    the harm you cannot undo, then pay whatever false-alarm cost that implies.
    """
    p_cal = np.asarray(p_cal, dtype=float)
    y_cal = np.asarray(y_cal)
    pos = p_cal[y_cal == 1]

    if len(pos) < 10:  # noqa: SIM108 — kept explicit for the fallback comment
        # Not enough positives to set a recall-based threshold; fall back to a
        # band-mix split and say so in the artifact.
        p_star_yellow = float(np.quantile(p_cal, 0.70))
        p_star_red = float(np.quantile(p_cal, 0.95))
        basis = "band_mix_fallback_insufficient_positives"
    else:
        p_star_yellow = float(np.quantile(pos, max_green_miss))
        p_star_red = float(np.quantile(pos, 1.0 - red_recall))
        basis = "under_triage_budget"

    p_star_yellow = min(max(p_star_yellow, 1e-6), 1 - 1e-6)
    p_star_red = min(max(p_star_red, p_star_yellow + 1e-6), 1 - 1e-6)

    # Consequences, measured on the calibration split.
    yellow_or_above = p_cal >= p_star_yellow
    neg = y_cal == 0
    achieved = {
        "green_miss_rate": float(((~yellow_or_above) & (y_cal == 1)).sum() / max((y_cal == 1).sum(), 1)),
        "over_triage_rate": float((yellow_or_above & neg).sum() / max(neg.sum(), 1)),
        "red_rate": float((p_cal >= p_star_red).mean()),
        "yellow_or_above_rate": float(yellow_or_above.mean()),
    }

    return {
        "p_star_yellow": p_star_yellow,
        "p_star_red": p_star_red,
        "R_yellow": (1.0 - p_star_yellow) / p_star_yellow,
        "R_red": (1.0 - p_star_red) / p_star_red,
        "basis": basis,
        "max_green_miss": max_green_miss,
        "red_recall": red_recall,
        "achieved_on_calibration": achieved,
        "target_over_triage": achieved["over_triage_rate"],
        "target_red_rate": achieved["red_rate"],
    }


def solve_per_stratum_thresholds(p_cal, y_cal, strata_cal, max_green_miss=0.10,
                                 min_pos=20):
    """
    Per-stratum Yellow cut points, each giving the SAME recall.

    Equalising FNR across groups mathematically requires group-differential
    decision thresholds — a single global cut produces equal *scores* but
    unequal *miss rates* whenever the score distribution differs by group, which
    it does here (each stratum has its own calibrator). Measured consequence of
    the single global cut: FNR ranged from 0.000 (adolescent) to 0.212 (child).

    The child case is not a modelling artefact — it is the physiology the
    generator encodes and the paediatric literature describes: children
    compensate until reserves are exhausted, holding near-normal vitals while
    deteriorating, so a snapshot-weighted score under-ranks them. Giving that
    stratum its own cut is how the recall guarantee is honoured for children
    rather than only on average.

    Strata with too few positives to estimate a quantile fall back to the global
    cut and are listed, never silently pooled.
    """
    p_cal = np.asarray(p_cal, dtype=float)
    y_cal = np.asarray(y_cal)
    strata_cal = np.asarray(strata_cal).astype(str)

    per: dict[str, float] = {}
    fallback: list[str] = []
    n_pos_per: dict[str, int] = {}

    for s in np.unique(strata_cal):
        m = strata_cal == s
        pos = p_cal[m & (y_cal == 1)]
        n_pos_per[str(s)] = int(len(pos))
        if len(pos) >= min_pos:
            per[str(s)] = float(np.quantile(pos, max_green_miss))
        else:
            fallback.append(str(s))

    return {"per_stratum_yellow": per,
            "fallback_strata": fallback,
            "n_pos": n_pos_per,
            "max_green_miss": max_green_miss}


def train(data_path: pathlib.Path, seed: int = 1337, out_root: pathlib.Path = ARTIFACT_ROOT,
          enable_pruning: bool = False, model_kind: str = "hist",
          artifact_name: Optional[str] = None) -> dict:
    records = load_dataset(data_path)
    X, y, y_aux, strata, pids, s_max = build_matrices(records)

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

    # --- primary head, cost-sensitive ---
    # The whitepaper's asymmetric loss: a missed critical costs far more than a
    # false alarm, so positives are upweighted at TRAINING time rather than the
    # asymmetry being bolted on at the threshold alone. Without this the model
    # optimises symmetric log-loss and then gets asked to behave asymmetrically,
    # which is how you end up with a well-calibrated model that still misses
    # most of the patients you care about.
    #
    # POSITIVE_WEIGHT is deliberately modest, not the whitepaper's 100-1000x
    # clinical cost ratio: extreme weights wreck probability calibration, and
    # calibration is what the conformal layer and the R-derived thresholds both
    # depend on. The clinical asymmetry is expressed in the THRESHOLD (which is
    # solved against an under-triage budget); this weight only stops the
    # majority class from dominating the splits.
    POSITIVE_WEIGHT = 3.0
    sample_weight = np.where(y[tr] == 1, POSITIVE_WEIGHT, 1.0)

    # Build primary classifier via factory (supports hist/lgbm/xgboost/hist-mono)
    clf_base = _build_primary_clf(model_kind, seed, float(sample_weight.sum()))

    # LightGBM and XGBoost use eval_set for early stopping rather than
    # validation_fraction. We carve out a small internal val from the train split.
    is_sklearn_compat = model_kind in ("hist", "hist-mono")
    if is_sklearn_compat:
        clf = clf_base
        clf.fit(X_tr, y[tr], sample_weight=sample_weight)
    else:
        # lgbm / xgboost need explicit eval_set; use 15% of tr as internal val
        from sklearn.model_selection import train_test_split as _tts
        _tr2, _val2 = _tts(
            np.arange(len(X_tr)), test_size=0.15,
            random_state=seed, stratify=y[tr],
        )
        
        # Ensure contiguous arrays to prevent LightGBM Windows segfaults
        X_tr_fit = np.ascontiguousarray(X_tr[_tr2])
        y_tr_fit = np.ascontiguousarray(y[tr][_tr2])
        sw_tr_fit = np.ascontiguousarray(sample_weight[_tr2])
        
        X_val_fit = np.ascontiguousarray(X_tr[_val2])
        y_val_fit = np.ascontiguousarray(y[tr][_val2])
        sw_val_fit = np.ascontiguousarray(sample_weight[_val2])
        
        if model_kind == "lgbm":
            clf = clf_base
            clf.fit(
                X_tr_fit, y_tr_fit,
                sample_weight=sw_tr_fit,
                eval_set=[(X_val_fit, y_val_fit)],
                callbacks=None,
            )
        elif model_kind == "xgboost":
            clf = clf_base
            clf.fit(
                X_tr_fit, y_tr_fit,
                sample_weight=sw_tr_fit,
                eval_set=[(X_val_fit, y_val_fit)],
                verbose=False,
            )

    # --- feature importance, measured on a HELD-OUT split that is not test ---
    #
    # Any feature-selection decision made from test-set importance is selection
    # on the evaluation set, which silently inflates the final number. Importance
    # is therefore computed on calib_iso: held out from fitting, and not the set
    # the model is graded on.
    try:
        from sklearn.inspection import permutation_importance
        imp = permutation_importance(
            clf, X[iso_idx], y[iso_idx], n_repeats=5,
            random_state=seed, scoring="average_precision", n_jobs=1,
        )
        importance = {
            name: float(imp.importances_mean[i])
            for i, name in enumerate(FEATURE_NAMES)
        }
    except Exception:
        importance = {}

    # --- prune features with no measured signal, then refit ---
    #
    # Half the feature set (34 of 68) had non-positive importance on the held-out
    # split. With ~1,170 positives in train, every noise column is variance the
    # model pays for. Selection uses calib_iso importance ONLY — never the test
    # set, which would inflate the final number.
    #
    # features.py still builds the full row (the extractor contract and the
    # registry stay stable); the artifact records which columns the classifier
    # actually consumes, and predictor.py applies the same subset.
    selected_idx = [i for i, n in enumerate(FEATURE_NAMES)
                    if importance.get(n, 0.0) > 0.0] if (importance and enable_pruning) else list(range(N_FEATURES))
    if len(selected_idx) < 8:            # degenerate importance -> keep everything
        selected_idx = list(range(N_FEATURES))

    clf_pruned = HistGradientBoostingClassifier(
        max_iter=400, learning_rate=0.06, max_leaf_nodes=31,
        min_samples_leaf=40, l2_regularization=1.0,
        early_stopping=True, validation_fraction=0.15, n_iter_no_change=25,
        random_state=seed,
    )
    clf_pruned.fit(X_tr[:, selected_idx], y[tr], sample_weight=sample_weight)

    # Keep the pruned model only if it beats the full one on the held-out split.
    # Pruning is a hypothesis, not an act of faith.
    from sklearn.metrics import average_precision_score as _ap
    ap_full = _ap(y[iso_idx], clf.predict_proba(X[iso_idx])[:, 1])
    ap_pruned = _ap(y[iso_idx], clf_pruned.predict_proba(X[iso_idx][:, selected_idx])[:, 1])
    # MEASURED: calib-selected pruning does NOT transfer. It raised calib AP
    # 0.183 -> 0.211 while LOWERING test AUPRC 0.174 -> 0.165 and wrecking the
    # reliability slope (0.954 -> 0.765). Selecting features by permutation
    # importance on 2,000 rows with ~195 positives selects noise, and the
    # improvement is measured on the very split the selection overfit.
    # Disabled by default; --prune re-enables it for experiments.
    pruning_applied = bool(enable_pruning and ap_pruned > ap_full)
    if pruning_applied:
        clf = clf_pruned
    else:
        selected_idx = list(range(N_FEATURES))

    def _pred_raw(Xm):
        return clf.predict_proba(Xm[:, selected_idx])[:, 1]

    # --- calibration, conformal, thresholds ---
    p_iso_raw = _pred_raw(X[iso_idx])
    calibrators, methods = fit_isotonic_per_stratum(p_iso_raw, y[iso_idx], strata[iso_idx])

    p_conf_raw = _pred_raw(X[conf_idx])
    p_conf = apply_calibration(calibrators, methods, p_conf_raw, strata[conf_idx])
    conformal = mondrian_conformal_quantiles(p_conf, y[conf_idx], strata[conf_idx])
    thresholds = solve_thresholds(p_conf, y[conf_idx])
    thresholds["per_stratum"] = solve_per_stratum_thresholds(
        p_conf, y[conf_idx], strata[conf_idx]
    )

    # --- persist ---
    _artifact_name = artifact_name or (
        ARTIFACT_NAME if model_kind == "hist" else
        f"medipilot-{model_kind}-v0.2.0-s{seed}"
    )
    out = out_root / _artifact_name
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
        # Measured on calib_iso, never on test — safe to use for selection.
        "permutation_importance_calib": importance,
        # Columns the classifier actually consumes. features.py still builds the
        # full row; predictor.py subsets with these before predict_proba.
        "selected_feature_indices": [int(i) for i in selected_idx],
        "selected_feature_names": [FEATURE_NAMES[i] for i in selected_idx],
        "pruning_applied": pruning_applied,
        "ap_calib_full": float(ap_full),
        "ap_calib_pruned": float(ap_pruned),
    }, indent=2), encoding="utf-8")

    meta_path = data_path.with_suffix(".meta.json")
    dataset_meta = json.loads(meta_path.read_text(encoding="utf-8")) if meta_path.exists() else {}

    manifest = {
        "model_version": _artifact_name,
        "model_kind": model_kind,
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
        # For the severity-oracle ceiling in evaluate.py. Never a feature.
        s_max=s_max[test_idx],
    )

    return {"manifest": manifest, "artifact_dir": str(out)}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default="data/train_set.jsonl")
    ap.add_argument("--seed", type=int, default=1337)
    ap.add_argument("--prune", action="store_true",
                    help="Enable calib-importance feature pruning (does not transfer; see train()).")
    ap.add_argument(
        "--model", default="hist", choices=MODEL_KINDS,
        help=(
            "Primary classifier implementation. 'hist' = shipped baseline "
            "(HistGradientBoosting), 'lgbm' = LightGBM, 'xgboost' = XGBoost, "
            "'hist-mono' = HistGBDT with clinical monotonic constraints "
            "(gcs/spo2 z-scores decreasing, n_abnormal/aux increasing)."
        ),
    )
    ap.add_argument("--artifact-name", default=None,
                    help="Override the artifact directory name (default: derived from --model).")
    args = ap.parse_args()

    res = train(
        pathlib.Path(args.data), seed=args.seed,
        enable_pruning=args.prune, model_kind=args.model,
        artifact_name=args.artifact_name,
    )
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
