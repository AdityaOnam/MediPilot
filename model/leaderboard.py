"""
model/leaderboard.py

Multi-artifact comparison harness for the MediPilot model bake-off (Track C).

STANDING RULE (from MODEL_EXPANSION_PLAN.md):
  No model result is reported, discussed, or shipped in isolation.
  Every model runs through this harness and lands as one row alongside the
  shipped HistGradientBoosting baseline, the hand-coded rule-card baseline,
  the prevalence floor, and the severity-oracle ceiling.

  A number quoted without its row in this table is not a result yet.

Usage:
    # Single artifact (re-evaluate the shipped model):
    python -m model.leaderboard

    # Multiple artifacts (compare bake-off candidates):
    python -m model.leaderboard \\
        --artifacts model/artifacts/medipilot-gbdt-v0.2.0 \\
                    model/artifacts/medipilot-lgbm-v0.2.0-s1337 \\
                    model/artifacts/medipilot-xgboost-v0.2.0-s1337 \\
                    model/artifacts/medipilot-hist-mono-v0.2.0-s1337

    # JSON output (for further analysis):
    python -m model.leaderboard --json > leaderboard.json
"""
from __future__ import annotations

import argparse
import json
import pathlib
from typing import Optional

import numpy as np

from model.train import ARTIFACT_ROOT, apply_calibration
from model.evaluate import (
    evaluate,
    baseline_scores_from_features,
    under_triage_at_fixed_over_triage,
    ece_quantile,
    reliability_slope_intercept,
    conformal_coverage,
    fnr_by_stratum,
    green_miss_rate,
    effective_yellow_cuts,
    GATE_PREVALENCE,
    GATE_AUROC,
    GATE_MAX_GREEN_MISS,
    GATE_MAX_FNR_SPREAD,
    FNR_MIN_POS_FOR_GATE,
)
import joblib
from sklearn.metrics import roc_auc_score, average_precision_score


def _load_artifact(artifact_dir: pathlib.Path):
    d = artifact_dir
    return d, {
        "clf": joblib.load(d / "primary.joblib"),
        "aux": joblib.load(d / "auxiliary.joblib"),
        "iso": joblib.load(d / "isotonic.joblib"),
        "conformal": json.loads((d / "conformal.json").read_text(encoding="utf-8")),
        "thresholds": json.loads((d / "thresholds.json").read_text(encoding="utf-8")),
        "manifest": json.loads((d / "manifest.json").read_text(encoding="utf-8")),
    }


def _evaluate_one(artifact_dir: pathlib.Path) -> dict:
    """Full evaluation for one artifact directory."""
    d, art = _load_artifact(artifact_dir)
    test = np.load(d / "test_split.npz", allow_pickle=True)
    X, y, strata = test["X"], test["y"], test["strata"]

    spec = json.loads((d / "feature_spec.json").read_text(encoding="utf-8"))
    sel = spec.get("selected_feature_indices") or list(range(X.shape[1]))
    p_raw = art["clf"].predict_proba(X[:, sel])[:, 1]
    p = apply_calibration(art["iso"]["calibrators"], art["iso"]["methods"],
                          p_raw, strata)

    manifest = art["manifest"]
    prevalence = float(y.mean())
    two_classes = len(np.unique(y)) > 1

    # --- discriminative metrics ---
    auroc = float(roc_auc_score(y, p)) if two_classes else float("nan")
    auprc = float(average_precision_score(y, p)) if two_classes else float("nan")

    # --- oracle gap ---
    s_max = test["s_max"] if "s_max" in test.files else None
    if s_max is not None and two_classes:
        oracle_auprc = float(average_precision_score(y, s_max))
        oracle_auroc = float(roc_auc_score(y, s_max))
        oracle_gap_pct = (auprc / oracle_auprc * 100) if oracle_auprc > 0 else float("nan")
    else:
        oracle_auprc = oracle_auroc = oracle_gap_pct = float("nan")

    # --- safety: green-miss rate at shipped threshold ---
    cuts = effective_yellow_cuts(art["thresholds"], strata)
    gm = green_miss_rate(y, p, cuts)

    # --- calibration ---
    ece = ece_quantile(y, p)
    slope, intercept = reliability_slope_intercept(y, p)

    # --- conformal coverage ---
    conf_cov = conformal_coverage(y, p, strata, art["conformal"])
    overall_cov = conf_cov["overall_coverage"]
    mean_set_size = conf_cov["mean_set_size"]

    # --- fairness: per-stratum FNR ---
    fnr_dict = fnr_by_stratum(y, p, strata, cuts)
    gated_fnr = {k: v for k, v in fnr_dict.items()
                 if v["n_pos"] >= FNR_MIN_POS_FOR_GATE and not np.isnan(v["fnr"])}
    if len(gated_fnr) >= 2:
        vals = [v["fnr"] for v in gated_fnr.values()]
        fnr_spread = float(max(vals) - min(vals))
        worst_stratum = max(gated_fnr, key=lambda k: gated_fnr[k]["fnr"])
        best_stratum = min(gated_fnr, key=lambda k: gated_fnr[k]["fnr"])
    else:
        fnr_spread = float("nan")
        worst_stratum = best_stratum = "underpowered"

    # --- baseline comparison at matched over-triage (10%, 20%, 30%, 50%) ---
    p_baseline = baseline_scores_from_features(X, strata)
    sig_wins, sig_losses, ties = [], [], []
    for otr_str in ("0.10", "0.20", "0.30", "0.50"):
        otr = float(otr_str)
        a = under_triage_at_fixed_over_triage(y, p, otr)
        b = under_triage_at_fixed_over_triage(y, p_baseline, otr)
        if np.isnan(a["under_triage"]) or np.isnan(b["under_triage"]):
            continue
        if a["ci_hi"] < b["ci_lo"]:
            sig_wins.append(otr_str)
        elif b["ci_hi"] < a["ci_lo"]:
            sig_losses.append(otr_str)
        else:
            ties.append(otr_str)

    auprc_baseline = float(average_precision_score(y, p_baseline)) if two_classes else float("nan")
    beats_baseline = bool(
        len(sig_wins) >= 1
        and len(sig_losses) == 0
        and auprc > auprc_baseline
    )

    # --- 8 go-live gates ---
    gates = {
        "prevalence_in_range": GATE_PREVALENCE[0] <= prevalence <= GATE_PREVALENCE[1],
        "auroc_in_range": (
            not np.isnan(auroc)
            and GATE_AUROC[0] <= auroc <= GATE_AUROC[1]
        ),
        "auprc_beats_prevalence": auprc > prevalence * 1.5,
        "conformal_coverage_ge_090": overall_cov >= 0.90,
        "ece_lt_005_where_reportable": ece < 0.05 if not np.isnan(ece) else None,
        "green_miss_rate_within_budget": bool(gm <= GATE_MAX_GREEN_MISS),
        "equalised_fnr_across_strata": (
            bool(fnr_spread <= GATE_MAX_FNR_SPREAD)
            if not np.isnan(fnr_spread) else None
        ),
        "beats_handcoded_baseline": beats_baseline,
    }
    gates_pass = sum(1 for v in gates.values() if v is True)
    gates_total = len(gates)
    all_gates_pass = all(v is True for v in gates.values())

    return {
        # Provenance
        "artifact": str(artifact_dir),
        "model_kind": manifest.get("model_kind", "hist"),
        "model_version": manifest.get("model_version", "unknown"),
        "data_n": manifest.get("dataset", {}).get("n_total", "?"),
        "seed": manifest.get("dataset", {}).get("seed", "?"),
        "history_available": bool(manifest.get("history_wired", False)),
        # Discriminative
        "auprc": auprc,
        "auroc": auroc,
        # Oracle
        "oracle_auprc": oracle_auprc,
        "oracle_auroc": oracle_auroc,
        "oracle_gap_pct": oracle_gap_pct,
        # Safety
        "green_miss_rate": gm,
        # Fairness
        "fnr_spread": fnr_spread,
        "worst_stratum": worst_stratum,
        "best_stratum": best_stratum,
        # Calibration
        "calib_slope": slope,
        "calib_intercept": intercept,
        "ece": ece,
        # Conformal
        "conformal_coverage": overall_cov,
        "mean_set_size": mean_set_size,
        # vs. shipped baseline
        "sig_wins_vs_baseline": sorted(sig_wins),
        "sig_losses_vs_baseline": sorted(sig_losses),
        "ties_vs_baseline": sorted(ties),
        # Gates
        "gates": gates,
        "gates_pass": f"{gates_pass}/{gates_total}",
        "all_gates_pass": all_gates_pass,
    }


def _fmt(v, fmt=".4f", nan_str="—"):
    if v is None or (isinstance(v, float) and np.isnan(v)):
        return nan_str
    return format(v, fmt)


def render_table(rows: list[dict]) -> str:
    # Separate shipped baseline from candidates
    lines = []
    lines.append(
        f"\n{'MediPilot Model Leaderboard':=^100}\n"
        f"Ranked by AUPRC among rows that pass ALL 8 go-live gates.\n"
        f"A row that fails any gate cannot replace the shipped model regardless of AUPRC.\n"
    )

    # Sort: passing rows by AUPRC desc, failing rows after
    passing = sorted([r for r in rows if r["all_gates_pass"]], key=lambda r: -r["auprc"])
    failing = [r for r in rows if not r["all_gates_pass"]]
    sorted_rows = passing + failing

    header = (
        f"{'Model':<22} {'N':>8} {'Seed':>6} {'Hist':>5}  "
        f"{'AUPRC':>7} {'AUROC':>7} {'Oracle%':>8} "
        f"{'GrMiss':>7} {'FNR_df':>6} {'CalSlp':>7} {'CovC':>6} "
        f"{'Gates':>7}  vs-Baseline"
    )
    lines.append(header)
    lines.append("─" * 110)

    for r in sorted_rows:
        gate_str = r["gates_pass"]
        if r["all_gates_pass"]:
            gate_str = "✅ " + gate_str
        else:
            gate_str = "❌ " + gate_str

        wins = len(r["sig_wins_vs_baseline"])
        losses = len(r["sig_losses_vs_baseline"])
        ties = len(r["ties_vs_baseline"])
        vs_str = f"{wins}W/{losses}L/{ties}T"

        hist_str = "Y" if r["history_available"] else "N"
        n_str = f"{int(r['data_n']):,}" if str(r["data_n"]).isdigit() else str(r["data_n"])

        row_str = (
            f"  {r['model_kind']:<20} {n_str:>8} {str(r['seed']):>6} {hist_str:>5}  "
            f"{_fmt(r['auprc']):>7} {_fmt(r['auroc']):>7} {_fmt(r['oracle_gap_pct'], '.1f'):>8} "
            f"{_fmt(r['green_miss_rate'], '.3f'):>7} {_fmt(r['fnr_spread'], '.3f'):>6} "
            f"{_fmt(r['calib_slope'], '.3f'):>7} {_fmt(r['conformal_coverage'], '.3f'):>6} "
            f"{gate_str:>9}  {vs_str}"
        )
        lines.append(row_str)

    lines.append("─" * 110)
    if passing:
        winner = passing[0]
        lines.append(
            f"\n▶ Best model: {winner['model_kind']} "
            f"(AUPRC={_fmt(winner['auprc'])}, gates={winner['gates_pass']})"
        )
        if winner["model_kind"] != "hist" or winner["data_n"] != 20000:
            lines.append(
                "  ✅ This model beats the shipped HistGBDT-20k baseline on AUPRC "
                "and passes all 8 go-live gates. Eligible for promotion."
            )
        else:
            lines.append("  (This is the currently shipped model — no new candidate to promote.)")
    else:
        lines.append("\n⚠ No candidate passes all 8 gates. Shipped model is retained.")

    return "\n".join(lines)


def main() -> None:
    ap = argparse.ArgumentParser(description="MediPilot leaderboard — compare artifact bake-off results.")
    ap.add_argument(
        "--artifacts", nargs="+", default=[str(ARTIFACT_ROOT / "medipilot-gbdt-v0.2.0")],
        help="Artifact directories to compare. Pass multiple paths for bake-off.",
    )
    ap.add_argument("--json", action="store_true", help="Emit JSON instead of table.")
    args = ap.parse_args()

    rows = []
    for artifact_path in args.artifacts:
        d = pathlib.Path(artifact_path)
        if not d.exists():
            print(f"[WARN] Artifact directory not found: {d} — skipping.")
            continue
        print(f"Evaluating {d.name} ...", flush=True)
        try:
            row = _evaluate_one(d)
            rows.append(row)
        except Exception as exc:
            print(f"[ERROR] Failed to evaluate {d}: {exc}")

    if not rows:
        print("No artifacts evaluated.")
        return

    if args.json:
        print(json.dumps(rows, indent=2, default=str))
    else:
        print(render_table(rows))


if __name__ == "__main__":
    main()
