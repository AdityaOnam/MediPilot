# MediPilot — Solution Architecture & Implementation

> **All documentation reflects the exact state of the `restructure` branch.** This document serves as the definitive guide to how MediPilot is structurally implemented, architected, and executed.

---

## Implementation Approach

MediPilot is built on a strict separation of concerns, ensuring that the **clinical risk engine** and the **patient/nurse interfaces** are decoupled by a rigid API contract.

1. **Unified Type Contract:** The entire boundary between the frontend and the backend is defined by `web/lib/api/types.ts` and mirrored precisely by `backend/triage/orchestrator/dto.py`. If a field is missing in the DTO, it cannot be rendered on the nurse board.
2. **Deterministic Fallbacks (Tiered Architecture):** The system relies on models for parsing, but never for clinical evaluation. The Language Model extracts structure from speech (Tier 1/2), but a deterministic **Band Engine** applies thresholds and rules (Tier 0). The model is structurally prohibited from generating an acuity score.
3. **The Two-Clock Resource Model:** Rather than assuming continuous data, the system explicitly models the decay of medical facts. The `SimClock` tracks both **re-measurement intervals** (physical nurse checks) and **wait ceilings** (queue time limits). Freshness is mathematically bound to the value itself (`{value, takenAt, validity}`).
4. **Offline-First Resilience:** The intake speech layer degrades gracefully. If cloud transcription (Groq) drops, it falls back to local `faster-whisper`. If inference fails entirely, the system falls back to a rule-based deterministic structurer.

---

## Solution Architecture

The repository is divided into two primary execution environments:

### 1. The Web Layer (`web/`)
A Next.js 16 (React 19, Tailwind 4) web application containing the seven core surfaces.
- **`web/intake/`:** The interactive patient kiosk module. Handles branching conversations, speech-to-text integration, and local offline phrase matching.
- **`web/components/clinical/`:** The shared UI library for rendering `AcuityCard`, `VitalChip`, and `OverrideDialog`. Enforces invariants at runtime (e.g., throwing an error if a score is rendered without a conformal confidence interval).
- **`web/lib/api/adapters/`:** Implements `mock.ts` and `live.ts`. The mock adapter runs the entire 20-patient synthetic corpus (`lib/seed/corpus.ts`) locally for demonstrations without backend dependencies.

### 2. The Triage Engine (`backend/`)
A Python/FastAPI orchestrator that maintains state, evaluates risk, and manages surge conditions.
- **`backend/triage/`:** The core orchestrator. Contains the `band_engine`, `surge_controller`, `audit_log`, and the Uvicorn `app`.
- **`backend/model/`:** The clinical risk models, calibration logic, and feature registries.
- **`backend/rules/`:** The safety floors, including the `red_flag_engine` and `spo2_bias_guard`.
- **`backend/eval/`:** Benchmarking and bake-off harnesses for verifying LLM extraction and ASR accuracy (results stored in `docs/benchmarks/`).

---

## Dependencies

The system is deliberately constrained to run on commodity hardware, avoiding paid cloud GPU locks to comply with local data privacy requirements (DPDP Act 2023).

### Frontend Dependencies (`web/package.json`)
- **Core:** Next.js 16, React 19, Node.js (v20+ recommended)
- **Styling:** Tailwind CSS 4
- **Media & 3D:** Three.js / React Three Fiber (for the 3D mascot rendering)
- **Speech:** `webkitSpeechRecognition` (Chrome native), Web Audio API

### Backend Dependencies (`backend/requirements.txt`)
- **Core:** Python 3.10+, FastAPI, Uvicorn, Pydantic
- **Data & ML:** Scikit-learn, NumPy, Pandas, Joblib
- **Speech & NLP (Optional Local Tiers):** `faster-whisper`, `llama.cpp`
- **Testing:** Pytest

---

## Execution Instructions

The system can be run in two modes: **Mock Mode** (frontend only, purely for UI/UX demonstration) and **Live Mode** (full end-to-end inference and orchestration).

### 1. Running the Web Frontend (Mock Mode)
By default, the frontend runs entirely on local mock data.

```bash
cd web
npm install
cp .env.example .env.local  # Ensure NEXT_PUBLIC_MP_SOURCE=mock is set
npm run dev
```
Navigate to `http://localhost:3000`. You can test all 7 surfaces, including the kiosk (`/intake`), the nurse board (`/board`), and the override panels.

### 2. Running the Triage Engine (Live Mode)
To run the full clinical pipeline, start the Python backend.

```bash
cd backend
python -m venv .venv

# On Windows:
.\.venv\Scripts\activate
# On macOS/Linux:
source .venv/bin/activate

pip install -r requirements.txt
python -m uvicorn triage.orchestrator.app:app --port 8000 --reload
```

### 3. Connecting Frontend to the Live Engine
Once the backend is running on port 8000, instruct the frontend to use the live network adapter:

1. Edit `web/.env.local`
2. Change `NEXT_PUBLIC_MP_SOURCE=mock` to `NEXT_PUBLIC_MP_SOURCE=live`
3. Restart the Next.js development server (`npm run dev`)

### 4. Running the Invariant Test Suite
The clinical constraints are mathematically enforced via Pytest.

```bash
cd backend
# Ensure the virtual environment is activated
python -m pytest
```

*Note: on a clean checkout you should expect **278 passed, 4 failed**, validating age stratification, audit logging, and the band engine contract. None of the four is a failing safety invariant:*

- *`test_auroc_leakage_canary`, `test_auprc_beats_prevalence_baseline` and `test_conformal_coverage_at_least_090` need `model/artifacts/medipilot-gbdt-v0.2.0/test_split.npz`, which is gitignored as regenerable — restore it by retraining (below).*
- *`test_census_has_20` asserts a census of 20; the census is now 34 (20 seeded encounters in `corpus_20.json` + 14 dynamic arrivals). The assertion is stale, not the code.*

### 5. Regenerating the model artefacts
The training set and the held-out split are generated from a seed rather than committed. To restore what the three model tests consume:

```bash
cd backend
python -m data.generator.bulk --n 20000 --out data/train_set.jsonl
python -m model.train --data data/train_set.jsonl
```

---

## Production Deployment Guidelines

To deploy MediPilot in a production or shadow-mode clinical environment (V2+ on the capability ladder), follow these hardening practices:

### Web Frontend (Next.js)
Do not use `npm run dev` in production. Build the optimized React payload:

```bash
cd web
npm run build
npm start
```
*For containerized environments, Next.js can be configured for `output: 'standalone'` in `next.config.ts` to minimize Docker image size.*

### Triage Engine (FastAPI)
Use Gunicorn as a process manager for auto-restarts — but **with a single worker**:

```bash
cd backend
gunicorn triage.orchestrator.app:app --workers 1 --worker-class uvicorn.workers.UvicornWorker --bind 0.0.0.0:8000
```

> ⚠️ **Do not raise `--workers` on either Python app as it stands.** The orchestrator holds `world = World()` at module level and starts a tick loop in its lifespan hook, and `triage/api.py` likewise holds `_audit_log`, `_scheduler`, `_surge_ctrl` and `_surge_state` at module level. `--workers 4` would create four independent worlds with four independent tick loops, and the census a nurse sees would depend on which worker answered the request. Horizontal scaling requires externalising that state first (Postgres for encounters, Redis for the live queue) — see §9 of `docs/paper/implementation_readme.pdf`.

---

## Environment Variable Reference

The system behavior is governed by the following environment variables. In production, these should be securely injected via your deployment platform (e.g., Kubernetes Secrets, Docker env files).

| Variable | Location | Purpose |
|---|---|---|
| `NEXT_PUBLIC_MP_SOURCE` | `web/.env.local` | `mock` (demo) or `live` (production orchestrator) |
| `NEXT_PUBLIC_API_BASE` | `web/.env.local` | URL of the Python backend (e.g., `http://localhost:8000`) |
| `MEDIPILOT_INTAKE_OFFLINE`| `web/.env.local` | Set to `1` to force the offline dictionary-matching path |
| `GROQ_API_KEY` | `web/.env.local` | Optional: Key for cloud Groq LLM inference (Tier 2) |
| `MEDIPILOT_STRUCTURER` | `backend/.env` | Order of structurer fallback (e.g., `local,groq,rules`) |
| `MEDIPILOT_ASR_BACKEND` | `backend/.env` | Order of ASR fallback (e.g., `local,groq`) |

---

## Security, Privacy, and Audit Logs

**Data Privacy (DPDP Act 2023):** 
MediPilot is designed to function **entirely on-premise** when Tier 1 (local) inference is active. If `GROQ_API_KEY` is omitted, the system will gracefully fall back to local `faster-whisper` and dictionary matching. No Patient Health Information (PHI) leaves the hospital network.

**Cryptographic Audit Ledger:**
Every autonomous decision made by the risk engine, and every clinical override performed by a nurse on the `/card/[id]` route, is recorded by the system's Audit Log (`backend/triage/audit_log.py`). 
- The ledger is **append-only**.
- Each entry is **SHA-256 hash-chained** to the previous entry, mathematically proving that historical triage decisions were not retroactively altered.
- The raw ledger can be inspected at any time via the `/audit` UI route.
