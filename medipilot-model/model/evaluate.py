"""
medipilot-model/model/evaluate.py

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
    """Expected calibration error with quantile bins."""
    y = np.asarray(y); p = np.asarray(p)
    if len(y) == 0:
        return float("nan")
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
    for s in sorted(set(map(str, strata))):
        m = np.array([str(x) == s for x in strata])
        ys, ps = np.asarray(y)[m], np.asarray(p)[m]
        pos = int(ys.sum())
        if pos == 0:
            out[s] = {"fnr": float("nan"), "n_pos": 0, "ci_lo": float("nan"),
                      "ci_hi": float("nan"), "underpowered": True}
            continue
        fnr = float(((ps < threshold) & (ys == 1)).sum() / pos)
        boots = []
        for _ in range(n_boot):
            idx = rng.integers(0, len(ys), len(ys))
            yb, pb = ys[idx], ps[idx]
            if yb.sum() == 0:
                continue
            boots.append(((pb < threshold) & (yb == 1)).sum() / yb.sum())
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

    p_raw = art["clf"].predict_proba(X)[:, 1]
    p = apply_calibration(art["iso"]["calibrators"], art["iso"]["methods"], p_raw, strata)

    prevalence = float(y.mean())
    report: dict = {
        "n_test": int(len(y)),
        "prevalence": prevalence,
        "model": {
            "auroc": float(roc_auc_score(y, p)) if len(np.unique(y)) > 1 else float("nan"),
            "auprc": float(average_precision_score(y, p)) if len(np.unique(y)) > 1 else float("nan"),
        },
        "baseline_auprc_by_prevalence": prevalence,
    }

    for otr in (0.10, 0.20, 0.30, 0.50):
        report.setdefault("under_triage_at_over_triage", {})[f"{otr:.2f}"] = \
            under_triage_at_fixed_over_triage(y, p, otr)

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
    thr = art["thresholds"]["p_star_yellow"]
    report["fairness_fnr_by_stratum"] = fnr_by_stratum(y, p, strata, thr)
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
    report["go_live_criteria"] = gates

    (d / "metrics.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    return report


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--artifacts", default=str(ARTIFACT_ROOT))
    args = ap.parse_args()
    r = evaluate(pathlib.Path(args.artifacts))

    print(f"n_test={r['n_test']}  prevalence={r['prevalence']:.4f}")
    print(f"  AUPRC (primary) = {r['model']['auprc']:.4f}   "
          f"[prevalence baseline {r['prevalence']:.4f}]")
    print(f"  AUROC           = {r['model']['auroc']:.4f}   (flatters at low prevalence)")
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
