"""
run_bakeoff.py

Chains all Track C bake-off training runs sequentially and then runs the
leaderboard. Run this once both 100k datasets are ready.

Usage:
    python run_bakeoff.py

Runs:
    1. HistGBDT      100k seed 1337  (may already be done — skips if artifact exists)
    2. LightGBM      100k seed 1337
    3. XGBoost       100k seed 1337
    4. HistGBDT+mono 100k seed 1337
    5. HistGBDT      100k seed 42    (waits for data/train_set_100k_s42.jsonl)
    6. Leaderboard   all 6 artifacts vs shipped baseline
"""
from __future__ import annotations

import pathlib
import subprocess
import sys
import time

CWD = pathlib.Path(__file__).parent
ARTIFACT_ROOT = CWD / "model" / "artifacts"

RUNS = [
    # (data_path, seed, model_kind, artifact_name)
    ("data/train_set_100k.jsonl",     1337, "hist",     "medipilot-hist-100k-s1337"),
    ("data/train_set_100k.jsonl",     1337, "hist-mono","medipilot-hist-mono-100k-s1337"),
    ("data/train_set_100k_s42.jsonl", 42,   "hist",     "medipilot-hist-100k-s42"),
]

SHIPPED_ARTIFACT = str(ARTIFACT_ROOT / "medipilot-gbdt-v0.2.0")


def _wait_for_file(path: pathlib.Path, poll_sec: int = 15) -> None:
    if path.exists():
        return
    print(f"  Waiting for {path.name} ...", flush=True)
    while not path.exists():
        time.sleep(poll_sec)
        print(f"  ... still waiting ({path.name})", flush=True)


def _run_training(data: str, seed: int, kind: str, name: str) -> bool:
    out_dir = ARTIFACT_ROOT / name
    if out_dir.exists() and (out_dir / "manifest.json").exists():
        print(f"  [SKIP] {name} already trained.")
        return True

    data_path = CWD / data
    _wait_for_file(data_path)

    print(f"\n{'='*60}")
    print(f"Training: {name}  (model={kind}, seed={seed})")
    print(f"{'='*60}", flush=True)

    t0 = time.time()
    result = subprocess.run(
        [
            sys.executable, "-m", "model.train",
            "--data", str(data_path),
            "--seed", str(seed),
            "--model", kind,
            "--artifact-name", name,
        ],
        cwd=str(CWD),
    )
    elapsed = time.time() - t0
    if result.returncode != 0:
        print(f"  [ERROR] Training failed for {name} (exit {result.returncode})")
        return False
    print(f"  Done in {elapsed/60:.1f} min.")
    return True


def main() -> None:
    print("\nMediPilot GBDT Bake-Off — Sequential Training Chain")
    print("="*60)

    failed = []
    artifacts = [SHIPPED_ARTIFACT]

    for data, seed, kind, name in RUNS:
        ok = _run_training(data, seed, kind, name)
        if ok:
            art_path = str(ARTIFACT_ROOT / name)
            if art_path not in artifacts:
                artifacts.append(art_path)
        else:
            failed.append(name)

    print(f"\n{'='*60}")
    print("All training runs complete. Running leaderboard...")
    print(f"{'='*60}\n")

    lb_result = subprocess.run(
        [sys.executable, "-m", "model.leaderboard", "--artifacts"] + artifacts,
        cwd=str(CWD),
    )

    if failed:
        print(f"\n[WARN] These runs failed and are excluded from leaderboard: {failed}")

    # Save leaderboard JSON for later analysis
    lb_json = subprocess.run(
        [sys.executable, "-m", "model.leaderboard",
         "--artifacts"] + artifacts + ["--json"],
        cwd=str(CWD),
        capture_output=True, text=True,
    )
    if lb_json.returncode == 0:
        out_path = CWD / "leaderboard_results.json"
        out_path.write_text(lb_json.stdout, encoding="utf-8")
        print(f"\nLeaderboard JSON saved to: {out_path}")

    sys.exit(0 if not failed else 1)


if __name__ == "__main__":
    main()
