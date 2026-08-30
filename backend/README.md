# The Triage Engine (`backend/`)

> **All data in this repository is synthetic.** We make no clinical claim, no performance claim against Indian patients, and no causal claim about outcomes. 

This directory contains the Python/FastAPI orchestrator that maintains state, evaluates risk, and manages surge conditions. It represents the **Evaluation Track** of the MediPilot architecture.

## Architectural Boundaries
While the frontend (`web/`) is permitted only to render, and the speech tier (`intake/`) is permitted only to extract, **this engine alone possesses the authority to decide a clinical band.** 

## Execution Constraints
The orchestrator maintains `world = World()` at the module level and starts a tick loop in its lifespan hook. 
- **Strictly Single-Worker:** Do not raise `--workers` beyond `1`. Scaling this prototype horizontally would create independent tick loops and splinter the queue state.

## Sub-Modules
- `triage/`: The core orchestrator, containing the `band_engine` and cryptographic `audit_log`.
- `intake/`: The state machine, question tree, and structural extractors.
- `rules/`: Deterministic safety floors (red flags, SpO2 bias guards).
- `model/`: The calibrated risk estimators and conformal thresholds.
- `data/`: Generation logic for the synthetic datasets.
- `eval/`: Benchmarking harnesses for structural evaluation.
