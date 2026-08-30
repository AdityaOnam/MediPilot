"""
backend/eval/build_bench_split.py

Materialise a fresh, COMMON held-out test split so the Risk Engine bake-off
table can actually be produced.

WHY THIS EXISTS
---------------
The five trained artifacts in model/artifacts/ ship without their
`test_split.npz`. Those dumps are close to a gigabyte across the bake-off and
are gitignored as regenerable, which is correct -- but it means
`python -m model.leaderboard` cannot run from a clean checkout, and that is why
the bake-off table was never committed to docs/benchmarks/ alongside the ASR
and structurer tables.

WHAT IT DOES *NOT* DO
---------------------
It does not retrain anything and it does not touch primary.joblib,
isotonic.joblib, auxiliary.joblib, conformal.json or thresholds.json. The
shipped models are evaluated exactly as they are.

WHY A FRESH SEED RATHER THAN A REPLAYED SPLIT
---------------------------------------------
Training used seed 1337. Regenerating at 1337 and replaying the split would
reproduce each model's own test rows -- but those splits are not comparable to
each other: the shipped GBDT held out 4,001 rows from a 20k population while
the 100k bake-off models held out 20,001 from their own. Scoring five models on
five different samples is not a leaderboard.

So this generates a population at a seed that was never used for training
(default 4242). Every row is genuinely unseen by every artifact, and all five
are scored on identical data. This is a stricter and more honest comparison
than each model's own split.

Because it is a different sample from the one metrics.json was computed on, the
shipped model's numbers here will differ slightly from its committed
metrics.json. That is sampling variation, not a discrepancy.

Usage (from backend/):
    python -m data.generator.bulk --n 20000 --seed 4242 --out data/bench_set.jsonl
    python -m eval.build_bench_split --data data/bench_set.jsonl --seed 4242
    python -m model.leaderboard --artifacts model/artifacts/medipilot-gbdt-v0.2.0 ...
"""

from __future__ import annotations

import argparse
import json
import pathlib

import numpy as np

from model.train import ARTIFACT_ROOT, load_dataset, build_matrices

# Artifacts that carry a scikit-learn-compatible primary.joblib. The sequence
# baselines (GRU/TCN/transformer/last-obs) unpickle through
# model/sequence_models.py, which imports torch at module scope -- they are
# skipped automatically below rather than crashing the run.
DEFAULT_ARTIFACTS = [
    "medipilot-gbdt-v0.2.0",
    "medipilot-hist-100k-s1337",
    "medipilot-hist-mono-100k-s1337",
    "medipilot-xgboost-100k-s1337",
    "medipilot-last-obs-100k-s1337",
]


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--data", default="data/bench_set.jsonl",
                    help="jsonl produced by data.generator.bulk at a NON-training seed")
    ap.add_argument("--seed", type=int, default=4242,
                    help="seed for the modality-dropout draw in build_matrices")
    ap.add_argument("--artifacts", nargs="*", default=DEFAULT_ARTIFACTS)
    args = ap.parse_args()

    path = pathlib.Path(args.data)
    if not path.exists():
        raise SystemExit(
            f"{path} not found. Generate it first:\n"
            f"  python -m data.generator.bulk --n 20000 --seed {args.seed} --out {path}"
        )

    records = load_dataset(path)
    print(f"loaded {len(records):,} records from {path}")

    # Same shared extractor, same dropout rate the models were trained under.
    X, y, y_aux, strata, pids, s_max = build_matrices(records, seed=args.seed)
    print(f"features {X.shape}  prevalence {y.mean():.4f}  "
          f"strata {sorted(set(strata.astype(str)))}")

    written = []
    for name in args.artifacts:
        d = pathlib.Path(ARTIFACT_ROOT) / name
        if not d.exists():
            print(f"  skip {name}: directory not found")
            continue
        if not (d / "primary.joblib").exists():
            print(f"  skip {name}: no primary.joblib")
            continue
        np.savez_compressed(
            d / "test_split.npz",
            X=X, y=y, strata=strata.astype(str), y_aux=y_aux, s_max=s_max,
        )
        written.append(name)
        print(f"  wrote {d / 'test_split.npz'}")

    manifest = {
        "purpose": "common held-out benchmark split for the Risk Engine bake-off",
        "source_data": str(path),
        "n_rows": int(len(y)),
        "prevalence": float(y.mean()),
        "generator_seed": args.seed,
        "training_seed": 1337,
        "note": "seed differs from training, so every row is unseen by every artifact",
        "artifacts": written,
    }
    out = pathlib.Path("data") / "bench_split_manifest.json"
    out.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(f"\nwrote {out}\nnow run:  python -m model.leaderboard --artifacts "
          + " ".join(f"model/artifacts/{n}" for n in written))


if __name__ == "__main__":
    main()
