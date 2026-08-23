# MediPilot — Data / Model / Risk / Classifier Track

**Accenture Innovation Challenge 2026, Round 2 — Team 01 BIT (IIT Patna)**

This track implements everything between Track A (speech/LLM/intake) and
Track B (frontend UI): synthetic data, risk model, calibration, age
stratification, uncertainty/abstention, and the safety-orchestration backend.

---

## Quick Start

```bash
# Install dependencies
pip install -r requirements.txt

# Generate the 20-record corpus
python -m data.generator.corpus

# Validate the corpus statistically
python -m data.validate

# Run all tests (6 invariant + 10 acceptance + unit tests)
pytest tests/ -v

# Start the API server
uvicorn backend.api:app --reload --port 8000
# → Swagger UI at http://localhost:8000/docs

# Live cost-ratio sweep demo
python -c "from backend.api import demo_cost_ratio_sweep; demo_cost_ratio_sweep()"
```

---

## Architecture

```
Track A (intake/LLM)
      │  structured record (vitals + red_flags + reliability_flags)
      ▼
┌─────────────────────────────────────────────────────────────┐
│                     Risk Model Pipeline                      │
│                                                             │
│  1. Age stratum resolution (Invariant 3)                   │
│  2. Deterministic red-flag engine (independent of model)   │
│  3. Vital freshness check (Invariant 4)                    │
│  4. SpO₂ bias guard                                        │
│  5. Threshold assessment (per-stratum, configurable)       │
│  6. Reliability weighting (asymmetric — Invariant 1 axis)  │
│  7. Raw risk scoring (feature-weighted)                    │
│  8. Calibration (per-stratum, separate from thresholds)    │
│  9. Conformal uncertainty (cost ratio R)                   │
│  10. ScoreObject or AbstentionObject (Invariant 2, 5)      │
└─────────────────────────────────────────────────────────────┘
      │  ScoreObject / AbstentionObject (§7 contract)
      ▼
┌─────────────────────────────────────────────────────────────┐
│                      Safety Backend                          │
│                                                             │
│  Band engine (Invariant 1: asymmetric autonomy)            │
│  Two-clock scheduler (rescore 5min, remeasure by band)     │
│  Surge controller (forbidden paths enforced in code)       │
│  Audit log (append-only, hash-chained, §9 schema)         │
└─────────────────────────────────────────────────────────────┘
      │  band + audit record
      ▼
Track B (frontend UI)
```

---

## Non-Negotiable Invariants (§1)

All 6 are tested in `tests/test_invariants.py`:

| # | Invariant | Enforcement |
|---|---|---|
| I-1 | Asymmetric autonomy | `AsymmetricAutonomyViolation` in `band_engine.py` |
| I-2 | No naked scores | `AbstentionObject` emitted, never partial `ScoreObject` |
| I-3 | Age never assumed | `inferred=True` in stratum result, never silent |
| I-4 | Freshness as value | `>3×` cadence → treated as missing |
| I-5 | Abstention is Yellow | `AbstentionObject.band` hardcoded to `"yellow"` |
| I-6 | Human closes every loop | `ValidationError` on empty `reason_text` |

---

## Age Stratification (§2)

Two mechanisms kept **separate**:
- **`model/thresholds.py`** — what counts as abnormal (per-stratum normal ranges)
- **`model/calibration.py`** — how abnormality maps to risk (per-stratum calibration weight)

Config: [`config/age_strata.yaml`](config/age_strata.yaml) — all values configurable, never hard-coded.

Key geriatric insight: `reassurance_decay=0.25` means normal vitals in a 75yo
offer very little reassurance — same temperature as a 3yo → same escalation,
different reasoning.

---

## Output Contract (§7)

Every scored patient emits exactly one of:
- **`ScoreObject`** — fully populated with `confidence` always set
- **`AbstentionObject`** — `abstained=True`, `band="yellow"`, `confidence=0.0`

Never a partially-populated object. Both are guarded by `__post_init__` (F3)
so the Invariant-5 floor can't be bypassed by construction.

`factors_for` / `factors_against` remain `list[str]` per the original
contract — no shape change for the frontend. In strata where a normal
reading is weak evidence of safety (currently geriatric,
`reassurance_decay < 0.4`), entries in `factors_against` carry a suffix:
`"hr_normal (weak reassurance — geriatric)"` instead of plain `"hr_normal"`.
The vital-name prefix (`hr_normal`) is stable either way if you need to
parse it; the qualifier is decoration, not a new field (F2).

---

## Audit Record Schema (§9)

All 15 fields, append-only, SHA-256 hash chain. Consent withdrawal is
recorded as a new event (never deletes prior records, per DPDP Act 2023).

---

## API Endpoints

| Method | Path | Description |
|---|---|---|
| `POST` | `/score` | Score a patient |
| `POST` | `/override` | Clinician override + audit record |
| `GET` | `/queue` | Queue sorted by risk × time-waiting |
| `POST` | `/recheck/{pid}` | Mark recheck complete |
| `GET` | `/surge-status` | Surge mode + active cadences |
| `GET` | `/audit/{pid}` | Full audit chain for a patient |
| `POST` | `/demo/arrival` | Simulate arrival (surge demo) |

---

## Demo Corpus

20-record corpus at `data/corpus_20.json` (committed after `python -m data.generator.corpus`).

P-01…P-10 map directly to the §10 acceptance cases:
- **P-01** Adult ACS deteriorating while waiting
- **P-02** 3yo paediatric fever → child stratum escalation
- **P-03** 75yo geriatric fever → geriatric stratum, different reasoning
- **P-04** Epigastric pain — ambiguous, low confidence
- **P-05** SpO₂ bias (dark skin) — SpO₂ alone cannot lower band
- **P-06** Stale vitals (3h) — confidence decayed
- **P-07** Zero history first visit
- **P-08** OOD presentation → explicit abstention
- **P-09** Nurse override → complete §9 record
- **P-10** Green, 2 missed rechecks → Yellow escalation

### Cross-track ID reconciliation (F5)

The original task brief numbered these cases differently (P-03/P-04 for the
age pair, P-14 for the override, P-20 for missed rechecks). The generator's
numbers above are the ones that ship. **Every corpus record now also carries
a stable `case_id`** — key off that, not the numeric `patient_id`, if your
track needs to reference a specific case, since generation order can still
renumber `P-xx` without `case_id` changing:

| `case_id` | `patient_id` | Old brief said |
|---|---|---|
| `deteriorates_while_waiting` | P-01 | P-05 |
| `age_pair_paediatric` | P-02 | P-03 |
| `age_pair_geriatric` | P-03 | P-04 |
| `ambiguous_epigastric_pain` | P-04 | P-07 |
| `spo2_bias_dark_skin` | P-05 | P-08 |
| `stale_vitals_3h` | P-06 | P-09 |
| `zero_history` | P-07 | P-11 |
| `ood_abstention` | P-08 | P-15 |
| `nurse_override_full_record` | P-09 | P-14 |
| `missed_rechecks_under_surge` | P-10 | P-20 |

P-11…P-20 (`case_id`s: `neonate_fever_floppy`, `infant_sepsis`,
`adolescent_poisoning_redflag`, `adult_stroke_redflag`,
`adult_anaphylaxis_redflag`, `geriatric_silent_mi`, `adult_trauma_redflag`,
`geriatric_communication_barrier`, `adolescent_obstetric_redflag`,
`green_baseline`) are generalisation cases not in the original §10 list —
no reconciliation needed for those.

---

## Out of Scope (§11)

Federated learning, FHIR/HIS integration, production edge deployment,
large-scale self-supervised pretraining, live ABHA retrieval, mass-casualty mode.
