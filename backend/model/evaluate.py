"""
backend/model/evaluate.py

Honest evaluation of the trained risk backbone.

Every headline metric is reported three ways:
  - trained model
  - hand-coded baseline (_raw_risk_score -> calibrate), the incumbent
  - severity oracle, which knows the true future peak severity

The oracle row is the anti-self-congratulation control. A trained model that
approaches or exceeds it has leakage; that is a mechanical detection rather than
a judgement call.

Metric choices follow the whitepaper rather than convenience:
  - AUPRC is primary. AUROC flatters every model at low prevalence.
  - The safety metric is UNDER-TRIAGE AT A FIXED OVER-TRIAGE RATE, not accuracy.
  - ECE uses QUANTILE bins. At ~10% prevalence equal-width bins put almost all
    mass in bin 0 and ECE collapses to ~0 regardless of calibration quality.
  - Fairness is equalised false-negative rate across strata, with bootstrap CIs.
    Never a bare max-min gap: at these positive counts that number is mostly noise.

Usage:
    python -m model.evaluate
"""

from __future__ import annotations

import argparse
import json
import pathlib
from typing import Optional

import joblib
import numpy as np
from sklearn.metrics import roc_auc_score, average_precision_score

from model.train import ARTIFACT_ROOT, apply_calibration

# Honesty gates. These fail the build rather than being celebrated.
GATE_PREVALENCE = (0.05, 0.20)
GATE_AUROC = (0.60, 0.95)      # >0.95 == leakage canary

# The whitepaper's primary safety metric, made into a build gate: at most this
# share of critical patients may be left below Yellow.
GATE_MAX_GREEN_MISS = 0.15

# Equalised FNR is THE fairness criterion in the whitepaper, so it gets a gate
# rather than being merely reported. Compared on strata with enough positives to
# support a claim; a wider spread than this is a fairness failure, not noise.
GATE_MAX_FNR_SPREAD = 0.25
FNR_MIN_POS_FOR_GATE = 25


def baseline_scores_from_features(X, strata) -> np.ndarray:
    """
    Reproduce the hand-coded scorer on the same rows the model is graded on.

    The plan required a baseline comparison and it was skipped: without it there
    is no evidence the trained model beats the rule card it replaced. Vitals are
    reconstructed from the '<vital>_value' feature columns, then pushed through
    the SAME thresholds -> _raw_risk_score -> calibrate path score_patient uses
    on the fallback branch.
    """
    from model.features import FEATURE_NAMES, VITALS
    from model.thresholds import get_thresholds
    from model.risk_model import _raw_risk_score
    from model.calibration import calibrate, get_reassurance_decay

    th = get_thresholds()
    idx = {v: FEATURE_NAMES.index(f"{v}_value") for v in VITALS}
    out = np.zeros(len(X), dtype=float)

    for i, (row, s) in enumerate(zip(X, strata)):
        vitals = {}
        missing = set()
        for v in VITALS:
            val = row[idx[v]]
            if np.isnan(val):
                missing.add(v)
            else:
                vitals[v] = float(val)

        n_abnormal, tr = th.count_abnormal_vitals(vitals, str(s))
        raw, _f, _a = _raw_risk_score(tr, missing, str(s), get_reassurance_decay(str(s)))
        cal = calibrate(raw, str(s), n_abnormal, max(len(vitals), 1))
        out[i] = cal.calibrated_score
    return out


def effective_yellow_cuts(thresholds: dict, strata) -> np.ndarray:
    """
    The Yellow cut actually applied to each row.

    Must mirror the serving path: `_thresholds_from_R` prefers the per-stratum
    cut and falls back to the global one. Grading with the global cut while
    shipping per-stratum cuts would report a fairness number for a configuration
    that never runs.
    """
    per = (thresholds.get("per_stratum") or {}).get("per_stratum_yellow") or {}
    g = float(thresholds["p_star_yellow"])
    return np.array([float(per.get(str(s), g)) for s in strata], dtype=float)


def green_miss_rate(y, p, cut) -> float:
    """
    Share of critical patients left below the Yellow cut.

    `cut` may be a scalar or a per-row array (per-stratum thresholds).
    """
    y = np.asarray(y); p = np.asarray(p)
    cut = np.asarray(cut, dtype=float)
    pos = y == 1
    if pos.sum() == 0:
        return float("nan")
    c = cut[pos] if cut.ndim else cut
    return float((p[pos] < c).sum() / pos.sum())


def _load_artifact(root: pathlib.Path = ARTIFACT_ROOT):
    name = (root / "current.txt").read_text(encoding="utf-8").strip()
    d = root / name
    return d, {
        "clf": joblib.load(d / "primary.joblib"),
        "aux": joblib.load(d / "auxiliary.joblib"),
        "iso": joblib.load(d / "isotonic.joblib"),
        "conformal": json.loads((d / "conformal.json").read_text(encoding="utf-8")),
        "thresholds": json.loads((d / "thresholds.json").read_text(encoding="utf-8")),
        "manifest": json.loads((d / "manifest.json").read_text(encoding="utf-8")),
    }


# ---------------------------------------------------------------------------
# Metrics
# ---------------------------------------------------------------------------

def under_triage_at_fixed_over_triage(y, p, target_otr: float, n_boot: int = 400, seed: int = 0):
    """
    over_triage_rate(t)  = FP / (FP + TN)   -> 1 - specificity
    under_triage_rate(t) = FN / (FN + TP)   -> 1 - sensitivity (the FNR)

    Pick the lowest threshold whose over-triage rate still respects the budget,
    then report the under-triage rate there with a bootstrap CI. A point
    estimate without the CI invites over-claiming at these positive counts.
    """
    y = np.asarray(y); p = np.asarray(p)
    if y.sum() == 0 or (1 - y).sum() == 0:
        return {"under_triage": float("nan"), "achieved_otr": float("nan"),
                "threshold": float("nan"), "ci_lo": float("nan"), "ci_hi": float("nan")}

    def _eval(yy, pp, t):
        pred = pp >= t
        tp = float(((pred == 1) & (yy == 1)).sum()); fn = float(((pred == 0) & (yy == 1)).sum())
        fp = float(((pred == 1) & (yy == 0)).sum()); tn = float(((pred == 0) & (yy == 0)).sum())
        otr = fp / max(fp + tn, 1.0)
        utr = fn / max(fn + tp, 1.0)
        return otr, utr

    cands = np.unique(p)
    best_t, best = None, None
    for t in cands:
        otr, utr = _eval(y, p, t)
        if otr <= target_otr and (best is None or utr < best[1]):
            best_t, best = t, (otr, utr)
    if best_t is None:
        best_t = cands.max()
        best = _eval(y, p, best_t)

    rng = np.random.default_rng(seed)
    boots = []
    n = len(y)
    for _ in range(n_boot):
        idx = rng.integers(0, n, n)
        _o, u = _eval(y[idx], p[idx], best_t)
        boots.append(u)
    return {
        "under_triage": float(best[1]),
        "achieved_otr": float(best[0]),
        "threshold": float(best_t),
        "ci_lo": float(np.percentile(boots, 2.5)),
        "ci_hi": float(np.percentile(boots, 97.5)),
    }


def ece_quantile(y, p, n_bins: int = 10) -> float:
    """
    Expected calibration error with quantile bins.

    Bin count adapts to the number of POSITIVES, not the number of rows. With 10
    fixed bins a stratum holding 35 positives gets ~3.5 positives per bin, and
    the resulting "ECE" is dominated by sampling noise — it measures how few
    positives you have, not how miscalibrated you are. Requiring ~10 positives
    per bin keeps the statistic meaningful on small strata.
    """
    y = np.asarray(y); p = np.asarray(p)
    if len(y) == 0:
        return float("nan")

    n_pos = int(y.sum())
    if n_pos > 0:
        n_bins = int(min(n_bins, max(3, n_pos // 10)))

    edges = np.unique(np.quantile(p, np.linspace(0, 1, n_bins + 1)))
    if len(edges) < 2:
        return float("nan")
    ece, n = 0.0, len(y)
    for lo, hi in zip(edges[:-1], edges[1:]):
        m = (p >= lo) & (p <= hi)
        if not m.any():
            continue
        ece += (m.sum() / n) * abs(y[m].mean() - p[m].mean())
    return float(ece)


def reliability_slope_intercept(y, p) -> tuple[float, float]:
    """Logistic regression of y on logit(p). Perfect calibration = (1, 0)."""
    from sklearn.linear_model import LogisticRegression
    y = np.asarray(y); p = np.clip(np.asarray(p), 1e-6, 1 - 1e-6)
    if len(np.unique(y)) < 2:
        return float("nan"), float("nan")
    z = np.log(p / (1 - p)).reshape(-1, 1)
    lr = LogisticRegression().fit(z, y)
    return float(lr.coef_[0][0]), float(lr.intercept_[0])


def conformal_coverage(y, p, strata, conformal) -> dict:
    """Empirical coverage of the conformal label set, overall and per stratum."""
    q = conformal["q_hat"]; pooled = conformal["pooled_q_hat"]
    covered, sizes = [], []
    per: dict[str, list] = {}
    for yi, pi, s in zip(y, p, strata):
        qs = q.get(str(s), pooled)
        st = []
        if (1.0 - pi) <= qs:
            st.append(1)
        if pi <= qs:
            st.append(0)
        covered.append(int(yi in st)); sizes.append(len(st))
        per.setdefault(str(s), []).append(int(yi in st))
    return {
        "overall_coverage": float(np.mean(covered)) if covered else float("nan"),
        "mean_set_size": float(np.mean(sizes)) if sizes else float("nan"),
        "per_stratum": {k: float(np.mean(v)) for k, v in per.items()},
        "per_stratum_n": {k: len(v) for k, v in per.items()},
    }


def fnr_by_stratum(y, p, strata, threshold, n_boot: int = 400, seed: int = 0) -> dict:
    """Equalised-FNR fairness metric, with per-stratum bootstrap CIs."""
    rng = np.random.default_rng(seed)
    out: dict[str, dict] = {}
    threshold = np.asarray(threshold, dtype=float)
    for s in sorted(set(map(str, strata))):
        m = np.array([str(x) == s for x in strata])
        ys, ps = np.asarray(y)[m], np.asarray(p)[m]
        # threshold may be scalar or per-row (per-stratum cuts)
        ts = threshold[m] if threshold.ndim else threshold
        pos = int(ys.sum())
        if pos == 0:
            out[s] = {"fnr": float("nan"), "n_pos": 0, "ci_lo": float("nan"),
                      "ci_hi": float("nan"), "underpowered": True}
            continue
        fnr = float(((ps < ts) & (ys == 1)).sum() / pos)
        boots = []
        for _ in range(n_boot):
            idx = rng.integers(0, len(ys), len(ys))
            yb, pb = ys[idx], ps[idx]
            if yb.sum() == 0:
                continue
            tb = ts[idx] if np.asarray(ts).ndim else ts
            boots.append(((pb < tb) & (yb == 1)).sum() / yb.sum())
        out[s] = {
            "fnr": fnr, "n_pos": pos,
            "ci_lo": float(np.percentile(boots, 2.5)) if boots else float("nan"),
            "ci_hi": float(np.percentile(boots, 97.5)) if boots else float("nan"),
            "underpowered": pos < 25,
        }
    return out


# ---------------------------------------------------------------------------
# Report
# ---------------------------------------------------------------------------

def evaluate(root: pathlib.Path = ARTIFACT_ROOT) -> dict:
    d, art = _load_artifact(root)
    test = np.load(d / "test_split.npz", allow_pickle=True)
    X, y, strata = test["X"], test["y"], test["strata"]

    spec = json.loads((d / "feature_spec.json").read_text(encoding="utf-8"))
    
    if spec.get("is_sequence_model", False):
        X_seq = test["X_seq"]
        p_raw = art["clf"].predict_proba(X_seq)[:, 1]
    else:
        sel = spec.get("selected_feature_indices") or list(range(X.shape[1]))
        p_raw = art["clf"].predict_proba(X[:, sel])[:, 1]
        
    p = apply_calibration(art["iso"]["calibrators"], art["iso"]["methods"], p_raw, strata)

    prevalence = float(y.mean())
    two_classes = len(np.unique(y)) > 1

    def _disc(scores):
        if not two_classes:
            return {"auroc": float("nan"), "auprc": float("nan")}
        return {
            "auroc": float(roc_auc_score(y, scores)),
            "auprc": float(average_precision_score(y, scores)),
        }

    # The three comparators the plan required.
    p_baseline = baseline_scores_from_features(X, strata)
    s_max = test["s_max"] if "s_max" in test.files else None

    report: dict = {
        "n_test": int(len(y)),
        "prevalence": prevalence,
        "model": _disc(p),
        "baseline_handcoded": _disc(p_baseline),
        "oracle_severity": _disc(s_max) if s_max is not None else None,
    }

    # Oracle gap: how much of the achievable signal the model actually captured.
    # Near 1.0 is a leakage warning, not a triumph; near 0 means the features do
    # not carry the signal.
    if s_max is not None and two_classes:
        o = report["oracle_severity"]
        report["oracle_gap"] = {
            "auprc_ratio": (report["model"]["auprc"] / o["auprc"]) if o["auprc"] > 0 else float("nan"),
            "auroc_ratio": (report["model"]["auroc"] / o["auroc"]) if o["auroc"] > 0 else float("nan"),
        }

    for otr in (0.10, 0.20, 0.30, 0.50):
        report.setdefault("under_triage_at_over_triage", {})[f"{otr:.2f}"] = \
            under_triage_at_fixed_over_triage(y, p, otr)
        report.setdefault("under_triage_at_over_triage_baseline", {})[f"{otr:.2f}"] = \
            under_triage_at_fixed_over_triage(y, p_baseline, otr)

    report["calibration"] = {
        "ece_overall": ece_quantile(y, p),
        "per_stratum": {},
    }
    slope, intercept = reliability_slope_intercept(y, p)
    report["calibration"]["reliability_slope"] = slope
    report["calibration"]["reliability_intercept"] = intercept

    for s in sorted(set(map(str, strata))):
        m = np.array([str(x) == s for x in strata])
        n_pos = int(y[m].sum())
        report["calibration"]["per_stratum"][s] = {
            "ece": ece_quantile(y[m], p[m]),
            "n": int(m.sum()),
            "n_pos": n_pos,
            # An ECE on <25 positives is not a measurement; refuse to grade it.
            "reportable": n_pos >= 25,
        }

    report["conformal"] = conformal_coverage(y, p, strata, art["conformal"])
    # Grade with the cuts that actually ship (per-stratum where available).
    thr = art["thresholds"]["p_star_yellow"]
    cuts = effective_yellow_cuts(art["thresholds"], strata)
    report["fairness_fnr_by_stratum"] = fnr_by_stratum(y, p, strata, cuts)
    report["thresholds"] = art["thresholds"]

    gates = {
        "prevalence_in_range": GATE_PREVALENCE[0] <= prevalence <= GATE_PREVALENCE[1],
        "auroc_in_range": (
            not np.isnan(report["model"]["auroc"])
            and GATE_AUROC[0] <= report["model"]["auroc"] <= GATE_AUROC[1]
        ),
        "auprc_beats_prevalence": report["model"]["auprc"] > prevalence * 1.5,
        "conformal_coverage_ge_090": report["conformal"]["overall_coverage"] >= 0.90,
    }
    reportable = [v for v in report["calibration"]["per_stratum"].values() if v["reportable"]]
    gates["ece_lt_005_where_reportable"] = all(v["ece"] < 0.05 for v in reportable) if reportable else None

    # --- the gate that was missing: under-triage at the shipped cut point ---
    gm = green_miss_rate(y, p, cuts)
    report["green_miss_rate"] = gm
    report["green_miss_rate_baseline"] = green_miss_rate(y, p_baseline, thr)
    gates["green_miss_rate_within_budget"] = bool(gm <= GATE_MAX_GREEN_MISS)

    # --- the other gate that was missing: equalised FNR across strata ---
    gated = {k: v for k, v in report["fairness_fnr_by_stratum"].items()
             if v["n_pos"] >= FNR_MIN_POS_FOR_GATE and not np.isnan(v["fnr"])}
    if len(gated) >= 2:
        vals = [v["fnr"] for v in gated.values()]
        spread = float(max(vals) - min(vals))
        report["fnr_spread"] = {
            "spread": spread,
            "strata_compared": sorted(gated),
            "worst": max(gated, key=lambda k: gated[k]["fnr"]),
            "best": min(gated, key=lambda k: gated[k]["fnr"]),
        }
        gates["equalised_fnr_across_strata"] = bool(spread <= GATE_MAX_FNR_SPREAD)
    else:
        report["fnr_spread"] = None
        gates["equalised_fnr_across_strata"] = None   # underpowered, not a pass

    # --- does the trained model actually beat the rule card it replaced? ---
    #
    # Compare at MATCHED OVER-TRIAGE RATES, not at a shared threshold. The two
    # scores live on different scales: p*_yellow is solved on the model's
    # calibrated-probability scale, and applying it to the heuristic score flags
    # 88% of all patients as Yellow-or-above. That makes the baseline's raw
    # green-miss look excellent while it is really just escalating almost
    # everyone — a comparison artefact, not a finding.
    if two_classes:
        # Significance-aware. Counting a 0.003 difference as a "win" and an
        # exact tie as a "loss" is noise-chasing when the bootstrap CIs overlap
        # by 90% - and those CIs are already computed here. A budget counts only
        # when the intervals are disjoint; everything else is a tie.
        sig_wins, sig_losses, ties = [], [], []
        for k, a in report["under_triage_at_over_triage"].items():
            b = report["under_triage_at_over_triage_baseline"][k]
            if np.isnan(a["under_triage"]) or np.isnan(b["under_triage"]):
                continue
            if a["ci_hi"] < b["ci_lo"]:
                sig_wins.append(k)
            elif b["ci_hi"] < a["ci_lo"]:
                sig_losses.append(k)
            else:
                ties.append(k)

        report["baseline_comparison"] = {
            "method": "under-triage at matched over-triage, bootstrap-CI significance",
            "significant_wins": sorted(sig_wins),
            "significant_losses": sorted(sig_losses),
            "ties_ci_overlap": sorted(ties),
            "auprc_model": report["model"]["auprc"],
            "auprc_baseline": report["baseline_handcoded"]["auprc"],
            "note": (
                "green_miss_rate_baseline is NOT comparable to green_miss_rate: "
                "they are evaluated at the same numeric cut on different score "
                "scales. Use this matched-over-triage comparison instead."
            ),
        }
        # Beat the incumbent = significantly better on at least one budget,
        # significantly worse on none, and a better AUPRC overall.
        gates["beats_handcoded_baseline"] = bool(
            len(sig_wins) >= 1
            and len(sig_losses) == 0
            and report["model"]["auprc"] > report["baseline_handcoded"]["auprc"]
        )

    report["go_live_criteria"] = gates

    (d / "metrics.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    return report


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--artifacts", default=str(ARTIFACT_ROOT))
    args = ap.parse_args()
    r = evaluate(pathlib.Path(args.artifacts))

    print(f"n_test={r['n_test']}  prevalence={r['prevalence']:.4f}")
    print()
    print("  %-22s %8s %8s" % ("", "AUPRC", "AUROC"))
    print("  %-22s %8.4f %8.4f" % ("trained model", r["model"]["auprc"], r["model"]["auroc"]))
    print("  %-22s %8.4f %8.4f" % ("hand-coded baseline",
                                   r["baseline_handcoded"]["auprc"],
                                   r["baseline_handcoded"]["auroc"]))
    if r.get("oracle_severity"):
        print("  %-22s %8.4f %8.4f" % ("severity oracle (ceiling)",
                                       r["oracle_severity"]["auprc"],
                                       r["oracle_severity"]["auroc"]))
    print("  %-22s %8.4f" % ("prevalence floor", r["prevalence"]))
    if r.get("oracle_gap"):
        print(f"  oracle gap: model captures {r['oracle_gap']['auprc_ratio']*100:.0f}% "
              f"of achievable AUPRC")
    print()
    print(f"  GREEN-MISS (criticals left below Yellow, at shipped cut): "
          f"{r['green_miss_rate']:.3f}")
    if r.get("baseline_comparison"):
        bc = r["baseline_comparison"]
        print(f"  vs baseline @ matched over-triage: "
              f"{len(bc['significant_wins'])} significant win(s), "
              f"{len(bc['significant_losses'])} loss(es), "
              f"{len(bc['ties_ci_overlap'])} tie(s)")
    if r.get("fnr_spread"):
        fs = r["fnr_spread"]
        print(f"  FNR spread across strata: {fs['spread']:.3f} "
              f"(worst={fs['worst']}, best={fs['best']})")
    print("  under-triage at fixed over-triage:")
    for k, v in r["under_triage_at_over_triage"].items():
        print(f"    otr<={k}: under_triage={v['under_triage']:.3f} "
              f"[{v['ci_lo']:.3f},{v['ci_hi']:.3f}] (achieved {v['achieved_otr']:.3f})")
    print(f"  ECE overall = {r['calibration']['ece_overall']:.4f}  "
          f"slope={r['calibration']['reliability_slope']:.3f} "
          f"intercept={r['calibration']['reliability_intercept']:.3f}")
    print(f"  conformal coverage = {r['conformal']['overall_coverage']:.3f} "
          f"(mean set size {r['conformal']['mean_set_size']:.2f})")
    print("  go-live gates:")
    for k, v in r["go_live_criteria"].items():
        print(f"    {k}: {v}")


if __name__ == "__main__":
    main()
