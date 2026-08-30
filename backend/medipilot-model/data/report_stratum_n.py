"""
data/report_stratum_n.py

Reports per-stratum patient counts and positive counts from a training set
JSONL file. Run this BEFORE retraining on any new dataset to verify that
thin strata (neonate, infant) have enough positives to support calibration.

Gate: any stratum with < 100 positives exits non-zero and prints a warning.
If < 200 positives, prints a caution — recommend scaling up before proceeding.

Usage:
    python -m data.report_stratum_n --data data/train_set_100k.jsonl
"""
from __future__ import annotations

import argparse
import json
import pathlib
import sys
from collections import defaultdict


GATE_HARD = 100      # < this → non-zero exit, do not train
GATE_SOFT = 200      # < this → print caution, training allowed but marginal


def report(data_path: pathlib.Path) -> int:
    counts: dict[str, int] = defaultdict(int)
    positives: dict[str, int] = defaultdict(int)
    total = 0

    with open(data_path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            rec = json.loads(line)
            s = rec.get("stratum", "unknown")
            label = int(rec.get("critical_composite_h180", 0))
            counts[s] += 1
            positives[s] += label
            total += 1

    overall_prev = sum(positives.values()) / max(total, 1)
    print(f"\n{'='*60}")
    print(f"Dataset: {data_path}")
    print(f"Total records: {total:,}   Prevalence: {overall_prev:.3f}")
    print(f"{'='*60}")
    print(f"{'Stratum':<20} {'N':>8} {'Pos':>6} {'Prev':>7}  Status")
    print(f"{'-'*60}")

    exit_code = 0
    strata_order = ["neonate", "infant", "child", "adolescent", "adult",
                    "geriatric"]
    all_strata = sorted(counts, key=lambda s: (strata_order.index(s)
                                               if s in strata_order else 99))

    for s in all_strata:
        n = counts[s]
        pos = positives[s]
        prev = pos / max(n, 1)
        if pos < GATE_HARD:
            status = f"[FAIL]   < {GATE_HARD} positives, do NOT train"
            exit_code = 1
        elif pos < GATE_SOFT:
            status = f"[CAUTION] < {GATE_SOFT} positives, FNR CI will be wide"
        else:
            status = "[OK]"
        print(f"  {s:<18} {n:>8,} {pos:>6} {prev:>7.3f}  {status}")

    print(f"{'='*60}\n")
    if exit_code != 0:
        print("GATE FAILED: one or more strata are underpowered.")
        print("Scale up N before retraining. Suggested: 200k+ records.")
    elif any(positives[s] < GATE_SOFT for s in counts):
        print("CAUTION: some strata are marginal. Consider scaling to 200k.")
    else:
        print("All strata are adequately powered. Safe to proceed with training.")
    return exit_code


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", required=True, help="Path to .jsonl training set")
    args = ap.parse_args()
    code = report(pathlib.Path(args.data))
    sys.exit(code)


if __name__ == "__main__":
    main()
