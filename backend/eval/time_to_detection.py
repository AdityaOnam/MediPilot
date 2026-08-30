"""
backend/eval/time_to_detection.py

Measures the quantity the whole product claims: how much sooner a deteriorating
patient is noticed when the queue is re-scored every five minutes, versus when
it is only looked at on the scheduled physical re-measurement.

METHOD
------
Every corpus patient carries a full 37-step vital trajectory (T=0 to T=180 min
at 5-minute intervals). For each step k we rebuild the feature row through the
same extractor the model was trained on, score it with the shipped artifact, and
record the calibrated probability. That gives p(t) per patient.

Two detection times are then read off the same p(t) curve:

  continuous   the first 5-minute tick at which p(t) crosses the threshold.
               This is what MediPilot does: re-score every patient every 5 min.

  scheduled    the first *scheduled re-measurement* at or after that crossing,
               on the band's own cadence from config/band_cadence.yaml
               (Yellow every 30 min, Green every 60 min). This is the
               counterfactual: a queue that is only re-examined when someone
               physically comes back to it.

The difference is the head start, in minutes, and it is the number the
five-minute loop exists to buy.

WHAT THIS IS NOT
----------------
This is a measurement on synthetic trajectories, not a clinical outcome study.
It quantifies detection latency under a stated monitoring policy. It does not
claim lives saved, and no causal claim is made.

Usage (from backend/):
    python -m eval.time_to_detection
"""

from __future__ import annotations

import json
import pathlib
import statistics
import time

import numpy as np

from model.features import from_trajectory_snapshot, build_feature_row
from model.predictor import predict_p_critical, band_thresholds

STEP_MIN = 5          # trajectory resolution
CADENCE_MIN = {       # scheduled physical re-measurement, per band
    "yellow": 30,
    "green": 60,
}


def score_trajectory(rec: dict) -> list[float]:
    """Calibrated p(critical) at every 5-minute step of one patient."""
    traj = rec["trajectory"]
    n = len(traj["series"]["hr"])
    out = []
    for k in range(n):
        fi = from_trajectory_snapshot(
            traj=traj, k_step=k, stratum=rec["stratum"], stratum_inferred=False
        )
        p, _ = predict_p_critical(build_feature_row(fi), rec["stratum"])
        out.append(float("nan") if p is None else float(p))
    return out


def first_crossing(series: list[float], thr: float) -> int | None:
    """Index of the first step at or above thr, or None."""
    for i, p in enumerate(series):
        if p == p and p >= thr:
            return i
    return None


def next_scheduled(minute: int, cadence: int) -> int:
    """The first scheduled check at or after `minute` on a `cadence` grid."""
    if minute % cadence == 0:
        return minute
    return ((minute // cadence) + 1) * cadence


def main() -> None:
    corpus = json.load(open("data/corpus_20.json", encoding="utf-8"))
    p_yellow, p_red = band_thresholds()
    print(f"thresholds  p*_yellow={p_yellow:.4f}  p*_red={p_red:.4f}")
    print(f"trajectory  {STEP_MIN}-minute steps, T=0..180 min\n")

    results, curves = [], {}
    for rec in corpus:
        s = score_trajectory(rec)
        curves[rec["patient_id"]] = s

        row = {
            "patient_id": rec["patient_id"],
            "case_id": rec["case_id"],
            "stratum": rec["stratum"],
            "p_t0": s[0],
            "p_max": max(x for x in s if x == x),
        }
        for name, thr, cad in (("yellow", p_yellow, CADENCE_MIN["green"]),
                               ("red", p_red, CADENCE_MIN["yellow"])):
            k = first_crossing(s, thr)
            if k is None:
                row[f"{name}_cont"] = row[f"{name}_sched"] = row[f"{name}_gain"] = None
                continue
            cont = k * STEP_MIN
            sched = next_scheduled(cont, cad)
            row[f"{name}_cont"] = cont
            row[f"{name}_sched"] = sched
            row[f"{name}_gain"] = sched - cont
        results.append(row)

    # ---- report -----------------------------------------------------------
    print(f"{'ID':<5} {'case':<30} {'p(T0)':>7} {'p_max':>7} "
          f"{'Y@cont':>7} {'Y@sched':>8} {'gain':>5} "
          f"{'R@cont':>7} {'R@sched':>8} {'gain':>5}")
    for r in results:
        f = lambda v: "-" if v is None else str(v)
        print(f"{r['patient_id']:<5} {r['case_id'][:30]:<30} "
              f"{r['p_t0']:7.3f} {r['p_max']:7.3f} "
              f"{f(r['yellow_cont']):>7} {f(r['yellow_sched']):>8} {f(r['yellow_gain']):>5} "
              f"{f(r['red_cont']):>7} {f(r['red_sched']):>8} {f(r['red_gain']):>5}")

    for name, cad in (("yellow", CADENCE_MIN["green"]), ("red", CADENCE_MIN["yellow"])):
        gains = [r[f"{name}_gain"] for r in results if r[f"{name}_gain"] is not None]
        if not gains:
            continue
        print(f"\n{name.upper()} crossing — n={len(gains)} of {len(results)} patients")
        print(f"  scheduled cadence used : {cad} min")
        print(f"  head start  mean {statistics.mean(gains):.1f} min | "
              f"median {statistics.median(gains):.1f} | max {max(gains)}")
        print(f"  worst case (a full cadence lost): {sum(1 for g in gains if g >= cad-STEP_MIN)}"
              f" of {len(gains)} patients")

    # ---- serving latency --------------------------------------------------
    rec = corpus[0]
    fi = from_trajectory_snapshot(traj=rec["trajectory"], k_step=6,
                                  stratum=rec["stratum"], stratum_inferred=False)
    row = build_feature_row(fi)
    predict_p_critical(row, rec["stratum"])           # warm
    lat = []
    for _ in range(300):
        t0 = time.perf_counter()
        predict_p_critical(row, rec["stratum"])
        lat.append((time.perf_counter() - t0) * 1000.0)
    lat.sort()
    print(f"\nSERVING LATENCY over 300 calls (ms): "
          f"p50 {lat[150]:.2f} | p95 {lat[284]:.2f} | p99 {lat[297]:.2f} | max {lat[-1]:.2f}")

    out = {
        "thresholds": {"p_star_yellow": p_yellow, "p_star_red": p_red},
        "step_minutes": STEP_MIN,
        "scheduled_cadence_minutes": CADENCE_MIN,
        "per_patient": results,
        "curves": curves,
        "serving_latency_ms": {"p50": lat[150], "p95": lat[284],
                               "p99": lat[297], "max": lat[-1], "n": len(lat)},
        "note": "synthetic trajectories; detection latency under a stated "
                "monitoring policy, not a clinical outcome study",
    }
    dest = pathlib.Path("../docs/benchmarks/time_to_detection.json")
    dest.write_text(json.dumps(out, indent=2), encoding="utf-8")
    print(f"\nwrote {dest}")


if __name__ == "__main__":
    main()
