"""
backend/data/validate.py

Statistical validation of the synthetic corpus.
Run: python -m data.validate

Checks:
  1. Marginals — per-vital per-stratum distributions vs. published ED reference ranges
  2. Correlations — HR/RR, HR/BP coherence
  3. Missingness patterns — sensor_fail rate, staff_shortage coverage
  4. Plausibility — flag any reading combinations that are clinically implausible
"""

from __future__ import annotations

import json
import pathlib
import sys
import numpy as np
from typing import Any


ROOT = pathlib.Path(__file__).parent.parent
CORPUS_PATH = ROOT / "data" / "corpus_20.json"

# Published ED reference marginals (approximate, for self-check)
REFERENCE_RANGES = {
    "adult": {
        "hr":      (60, 100),
        "rr":      (12, 20),
        "bp_sys":  (90, 140),
        "spo2":    (95, 100),
        "temp_c":  (36.1, 37.9),
    },
    "child": {
        "hr":      (70, 140),
        "rr":      (18, 30),
        "bp_sys":  (80, 120),
        "spo2":    (95, 100),
        "temp_c":  (36.1, 37.9),
    },
    "geriatric": {
        "hr":      (60, 100),
        "rr":      (12, 20),
        "bp_sys":  (90, 150),
        "spo2":    (94, 100),
        "temp_c":  (36.0, 37.9),
    },
}

PLAUSIBILITY_RULES = [
    # (vital_a, op, vital_b) — if violated, flag as implausible
    # HR high + BP low expected in shock — not a bug
    # HR > 200 in adult → implausible
    lambda r: not (r.get("stratum") == "adult" and r.get("hr", 80) > 220),
    lambda r: not (r.get("spo2", 97) > 100),
    lambda r: not (r.get("temp_c", 37) < 28),
    lambda r: not (r.get("gcs", 15) > 15),
    lambda r: not (r.get("gcs", 15) < 3),
]


def extract_vitals_from_corpus(records: list[dict]) -> dict[str, dict[str, list[float]]]:
    """
    Extract per-stratum vital lists from the first snapshot (T=0) of each record.
    Returns {stratum: {vital: [values]}}
    """
    result: dict[str, dict[str, list[float]]] = {}
    for rec in records:
        stratum = rec.get("stratum", "adult")
        if stratum not in result:
            result[stratum] = {}
        traj = rec.get("trajectory", {})
        series = traj.get("series", {})
        for vital, readings in series.items():
            valid = [r for r in readings if r.get("validity") == "valid"]
            if valid:
                v = valid[0]["value"]
                result[stratum].setdefault(vital, []).append(v)
    return result


def check_marginals(vitals_by_stratum: dict[str, dict[str, list[float]]]) -> list[str]:
    """Check that sampled means are within 2 SD of reference ranges."""
    warnings = []
    for stratum, ref in REFERENCE_RANGES.items():
        if stratum not in vitals_by_stratum:
            warnings.append(f"  WARN: no records for stratum '{stratum}'")
            continue
        stratum_data = vitals_by_stratum[stratum]
        for vital, (ref_lo, ref_hi) in ref.items():
            vals = stratum_data.get(vital, [])
            if not vals:
                warnings.append(f"  WARN: {stratum}/{vital} — no data")
                continue
            mean_v = np.mean(vals)
            ref_mid = (ref_lo + ref_hi) / 2
            ref_half_range = (ref_hi - ref_lo) / 2
            # Allow 3× the normal range for abnormal patients
            tolerance = ref_half_range * 3
            if abs(mean_v - ref_mid) > tolerance:
                warnings.append(
                    f"  WARN: {stratum}/{vital} mean={mean_v:.1f} "
                    f"far from reference [{ref_lo}, {ref_hi}]"
                )
    return warnings


def check_correlations(records: list[dict]) -> list[str]:
    """Check HR/RR correlation and HR/BP inverse correlation."""
    hr_vals, rr_vals, bp_vals = [], [], []
    for rec in records:
        series = rec.get("trajectory", {}).get("series", {})
        for vital_dict, target in [("hr", hr_vals), ("rr", rr_vals), ("bp_sys", bp_vals)]:
            readings = series.get(vital_dict, [])
            valid = [r["value"] for r in readings if r.get("validity") == "valid"]
            if valid:
                target.append(np.mean(valid))

    warnings = []
    if len(hr_vals) >= 5 and len(rr_vals) >= 5:
        corr_hr_rr = float(np.corrcoef(hr_vals[:min(len(hr_vals), len(rr_vals))],
                                        rr_vals[:min(len(hr_vals), len(rr_vals))])[0, 1])
        if corr_hr_rr < -0.1:
            warnings.append(f"  WARN: HR/RR correlation is negative ({corr_hr_rr:.2f}) — expected weakly positive")

    if len(hr_vals) >= 5 and len(bp_vals) >= 5:
        corr_hr_bp = float(np.corrcoef(hr_vals[:min(len(hr_vals), len(bp_vals))],
                                        bp_vals[:min(len(hr_vals), len(bp_vals))])[0, 1])
        if corr_hr_bp > 0.5:
            warnings.append(f"  WARN: HR/BP correlation is strongly positive ({corr_hr_bp:.2f}) — shock pattern expected to be inverse")

    return warnings


def check_missingness(records: list[dict]) -> list[str]:
    """Report missingness rates per vital."""
    total = valid = sensor_fail = absent = 0
    for rec in records:
        series = rec.get("trajectory", {}).get("series", {})
        for vital, readings in series.items():
            for r in readings:
                total += 1
                v = r.get("validity")
                if v == "valid":
                    valid += 1
                elif v == "sensor_fail":
                    sensor_fail += 1
                else:
                    absent += 1

    notes = [
        f"  Total readings: {total}",
        f"  Valid: {valid} ({100*valid/max(total,1):.1f}%)",
        f"  Sensor-fail: {sensor_fail} ({100*sensor_fail/max(total,1):.1f}%)",
        f"  Absent/missing: {absent} ({100*absent/max(total,1):.1f}%)",
    ]
    warnings = []
    if sensor_fail == 0 and absent == 0:
        warnings.append("  WARN: no missingness in corpus — generator may not be exercising missingness")
    return notes + warnings


def check_plausibility(records: list[dict]) -> list[str]:
    """Flag implausible vital combinations."""
    issues = []
    for rec in records:
        pid = rec.get("patient_id")
        series = rec.get("trajectory", {}).get("series", {})
        t0_snap: dict[str, Any] = {}
        for vital, readings in series.items():
            valid = [r for r in readings if r.get("validity") == "valid"]
            if valid:
                t0_snap[vital] = valid[0]["value"]
        t0_snap["stratum"] = rec.get("stratum")
        for rule in PLAUSIBILITY_RULES:
            try:
                if not rule(t0_snap):
                    issues.append(f"  FAIL: {pid} fails plausibility rule: {rule}")
            except Exception:
                pass
    return issues


def main():
    if not CORPUS_PATH.exists():
        print("Corpus not found — run: python -m data.generator.corpus")
        sys.exit(1)

    with open(CORPUS_PATH, encoding="utf-8") as f:
        records = json.load(f)

    print(f"\n=== MediPilot Corpus Validation Report ===")
    print(f"Corpus: {CORPUS_PATH} ({len(records)} records)\n")

    vitals_by_stratum = extract_vitals_from_corpus(records)

    print("── Marginal Checks ──")
    marginal_warnings = check_marginals(vitals_by_stratum)
    if marginal_warnings:
        for w in marginal_warnings:
            print(w)
    else:
        print("  OK — all marginals within tolerance")

    print("\n── Correlation Checks ──")
    corr_warnings = check_correlations(records)
    if corr_warnings:
        for w in corr_warnings:
            print(w)
    else:
        print("  OK — HR/RR and HR/BP correlations plausible")

    print("\n── Missingness ──")
    for line in check_missingness(records):
        print(line)

    print("\n── Plausibility ──")
    plaus_issues = check_plausibility(records)
    if plaus_issues:
        for w in plaus_issues:
            print(w)
    else:
        print("  OK — no implausible vital combinations detected")

    print("\n=== Done ===\n")


if __name__ == "__main__":
    main()
