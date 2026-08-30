# MediPilot model — data scale-up, patient history, and multi-model comparison plan

Handoff document for an agentic coding run (Antigravity). Self-contained: you
do not need the conversation that produced it, but you must read
[`RISK_ENGINE.md`](RISK_ENGINE.md) and
[`.claude/skills/medipilot-risk-model/SKILL.md`](../.claude/skills/medipilot-risk-model/SKILL.md)
first — they record seven measured traps in this exact pipeline (leaky
labels, an oracle-ceiling miscalibration, a train/serve trend-feature
mismatch, three threshold bugs) and the house discipline that caught each
one. Everything below extends that pipeline; it does not replace it.

Work in `D:\medipilot-whitepaper\backend`.

---

## Standing rule — read this before running anything

**No model result is reported, discussed, or shipped in isolation.** Every
model you train — every GBDT variant, every sequence model, every ablation —
runs through the comparison harness in Phase 3 below and lands as one row in
a single leaderboard alongside the currently-shipped `HistGradientBoosting`
baseline, the hand-coded rule-card baseline, the prevalence floor, and the
severity-oracle ceiling that already exist in `model/evaluate.py`. A number
quoted without its row in that table (AUPRC, green-miss rate, calibration
slope, per-stratum FNR with CI, all 8 go-live gates) is not a result yet —
say so explicitly rather than presenting it as one.

This mirrors what the project already does (§7–8 of `RISK_ENGINE.md`); the
only change is making it mandatory for *every* new model, not just the
shipped one.

---

## 0. Current state — what "more data" and "patient history" mean here

- **Data**: 20,000 synthetic patients (`data/train_set.jsonl`, seed 1337,
  9.76% prevalence), regenerated in ~2 min/1k via
  `python -m data.generator.bulk`. The calibration split is **~2,000 rows
  total**, so per-stratum positive counts are thin — neonate sits around 40
  positives with a wide FNR confidence interval.
- **"Patient history" already half-exists and is split into two unrelated
  things — do not conflate them:**
  1. **Within-encounter trend** (`slope_per_hour`, `delta_30min`,
     `vitals_history` on `PatientRecord`) — built, trained on, but **not
     wired through the live API** (`RISK_ENGINE.md` §9.1, its own
     highest-priority open item). This is the cheapest, highest-leverage
     task in this whole plan: no new data, no new model, just plumbing.
  2. **Cross-visit / longitudinal history** (prior ED visits, known chronic
     conditions, repeat-attender flags) — does **not exist anywhere** in the
     generator or the schema. This is a real feature addition, not a wiring
     fix, and it changes what the `frailty` latent is standing in for. Scope
     it separately (Phase 2 below) — don't let it get bundled silently into
     "add patient history."
- **Model**: `sklearn.ensemble.HistGradientBoostingClassifier` only.
  `lightgbm` and `xgboost` are not in `requirements.txt` and have never been
  run against this data. `torch` is installed in the environment but broken
  (DLL init failure on Windows, verified) — no sequence model has ever been
  trained here.
- **Oracle gap**: the model captures 42% of the achievable AUPRC (0.174 of
  0.410, against an oracle that knows the true future severity). More data
  reduces variance in thin strata; it does not by itself move the oracle
  ceiling — that ceiling comes from `config/label_spec.yaml`'s frailty
  latent, which is deliberately unrecoverable from vitals.

---

## 1. Track A — more data

1. **Scale N.** `python -m data.generator.bulk --n 100000 --seed 1337 --out
   data/train_set_100k.jsonl` (or larger; throughput is ~163
   trajectories/sec, so 100k ≈ 10 min). Keep the existing seed for the
   current 20k set as a regression reference — do not overwrite it.
2. **Report per-stratum n before touching the model.** Neonate and infant
   are the ones that matter (RISK_ENGINE.md §9.2). If 100k patients still
   leaves neonate under ~200 positives, say so and scale further rather than
   proceeding on an underpowered split.
3. **Multiple seeds for the leaderboard, not one.** Generate at least 2
   independent seeds at the chosen N and report variance across seeds for
   every model in the comparison table (Phase 3) — a single-seed win is not
   distinguishable from noise at this positive count, and this project has
   already been burned once by trusting a single split (§6.4 of
   `RISK_ENGINE.md`).
4. **Real data is a separate, later track, not a substitute.** The
   whitepaper's own phased plan calls for MIMIC-IV-ED next (architecture
   validation only — no India-population claim), then partner-hospital
   data. Nothing in this plan produces a claim that transfers to real
   patients; keep that framing in every report this track produces.

---

## 2. Track B — patient history

### B1. Wire existing within-encounter history through the live API (do this first)

The model was trained expecting trend features; production sends none. Find
where `backend/api.py` builds a `PatientRecord` for `/score` and pass
accumulated readings as `vitals_history` instead of a single snapshot. This
requires no new data and no new model — it is closing a train/serve gap that
already has a name (`RISK_ENGINE.md` §5.8, §9.1). Confirm afterward that
`model/features.py::from_patient_record` is populating `slope_per_hour` /
`delta_30min` on repeat-visit patients the way
`from_trajectory_snapshot` does in training
(`tests/test_features.py::test_train_and_serve_adapters_agree` is the
existing guard — extend it with a live-API-shaped fixture, don't just trust
the unit-level adapter test).

### B2. Cross-visit / longitudinal history — scope, don't build blind

This needs a design decision before code:

- What does a "history" record contain — prior visit outcomes only, known
  chronic conditions, both?
- Does it enter the generator's latent model (alongside or replacing part of
  `frailty`), or as an observed feature the label doesn't already encode?
  If it overlaps with `frailty`, adding it as a feature without changing the
  label spec just leaks the latent through a side door — re-run the Trap-1
  leakage check (`auroc_in_range` gate, ceiling at 0.95) after this change,
  not just after model changes.
- Per-patient generation currently produces one encounter. Multi-encounter
  patients are a generator redesign, not a config tweak.

Deliverable for this sub-track is a short design note (data shape,
generator change, updated `config/feature_registry.yaml` classification for
every new field, updated `config/label_spec.yaml` if the latent changes) —
land that before writing generator code, and flag it back for a decision
rather than guessing the shape.

---

## 3. Track C — model comparison matrix

### Group 1 — GBDT variants (cheap, do this before any sequence-model work)

Add `lightgbm` and `xgboost` to a new `requirements-experimental.txt` (keep
them out of the core `requirements.txt` that the API deployment installs).
Train each against **the identical 59-feature `fx-v4` matrix**, identical
CV folds, identical calibration/threshold/conformal pipeline as the shipped
`HistGradientBoostingClassifier` — the only thing allowed to vary is the
boosting implementation, so the comparison isolates that one variable.
Include a monotonic-constraint variant of whichever GBDT wins
(`RISK_ENGINE.md` §9.2 flagged `monotonic_cst` as untried, clinically
motivated for features like `gcs_z_stratum`) as one more row, not a separate
track.

Recent comparisons on clinical tabular data found `HistGradientBoosting`
the most stable across datasets with LightGBM and XGBoost close behind, and
that LightGBM tends to win on larger N / tighter training-time budgets while
XGBoost tends to be more forgiving on defaults — treat both as plausible,
decide from your own leaderboard, not from this prior.

### Group 2 — sequence models (only after B1 ships — they need real history)

These operate on the raw multivariate vitals sequence, not the hand-built
feature row, so they are blocked on Track B1 actually delivering history at
serve time — training a sequence model against data the API can never
supply is the exact train/serve mismatch this project already found once
(§5.8) and fixed; don't reintroduce it in a new form.

Candidates, roughly in order of how much they suit sequences this short
(per-patient history here is 6–18 steps, 30–90 minutes — short and
irregularly sampled):

- **TCN** (Bai et al., dilated causal convolutions) — cheap to train, no
  recurrence, a reasonable first sequence baseline.
- **LSTM/GRU**, optionally with GRU-D-style missingness-aware gating —
  standard choice for irregular clinical vitals, but expect it to be harder
  to calibrate well against the existing Platt-scaling pipeline.
- **A small Transformer** (SAnD-style multi-head attention over the vitals
  sequence) — keep it deliberately small (few layers, small hidden dim);
  full-scale transformer capacity on ~2,000 calibration positives will
  overfit before it learns anything, the same lesson §6.4 already recorded
  for feature pruning on a small split.

**Mandatory control arm: last-observation-only.** A 2026 finding
(vitals-only ICU mortality, medRxiv) reports *no significant improvement*
from full time-series models over the last observed vitals for hospital
mortality prediction. Any sequence model here must beat a last-observation
snapshot baseline **on the same held-out test split, with a bootstrap CI**,
or it does not ship — this is the exact discipline the project already
applies to the oracle/baseline comparison in `evaluate.py`, extended to a
new axis.

**Fix the environment before starting this group.** `torch` currently fails
to import (DLL init failure). Diagnose and fix the Windows CPU wheel
mismatch (usually a Python-version/CPU-wheel or MSVC runtime mismatch) or
move this group to WSL/a container if the native install stays broken.
Report which one you used, since anything trained in a different runtime
must still evaluate against the identical test split as Group 1.

### Out of scope, on purpose

**No diffusion models for the prediction task.** Diffusion is a generative
family; it has no established role in this kind of tabular/short-sequence
risk classification. If synthetic-data augmentation via diffusion is worth
exploring later, that is a separate, clearly-labeled experiment against the
Track A data pipeline — not a candidate in this model leaderboard.

---

## 4. The comparison harness (build this once, reuse for every model)

Extend `model/evaluate.py` (or add `model/leaderboard.py` that imports it —
don't duplicate the baseline/oracle/bootstrap logic) so it accepts a list of
trained artifacts and emits **one table**, one row per (model type, data N,
seed, history-availability) combination, with:

| column | source |
|---|---|
| AUPRC / AUROC | existing |
| oracle gap % | existing |
| green-miss rate | existing, gate ≤0.15 |
| per-stratum FNR + CI, spread | existing, `solve_per_stratum_thresholds` |
| calibration slope / intercept | existing |
| conformal coverage / mean set size | existing |
| bootstrap-significant win/loss/tie vs. **currently shipped** model | existing, extend the pairwise comparison to every new row |
| all 8 go-live gates | existing, pass/fail per row |
| data N, seed, history available? (Y/N) | new — required for Track A/B provenance |

Rank by AUPRC **only among rows that pass all 8 gates**. If nothing clears
all 8, nothing replaces the shipped model — report that plainly rather than
promoting the best-of-a-bad-set.

Re-run the AUROC>0.95 leakage canary on every row, not just new feature
sets — a sequence model with direct access to the raw trajectory has a
different, easier path to reconstructing the discarded severity latent than
the hand-built features did.

---

## 5. Guardrails (inherited from `FIX_PLAN.md` / `RISK_ENGINE.md` — do not relax these for new models)

- Compute the severity-oracle ceiling for whatever data split you're using
  *before* judging any model against it.
- Do not tune a threshold, hyperparameter, or feature selection to make a
  gate pass. If a constant needs to change, the clinical or statistical
  reason changes first, in writing, in this file or its successor.
- Any selection made on the calibration split (feature pruning, model
  choice, early stopping) must be confirmed on the untouched test split
  before being called an improvement — §6.4 measured exactly this failure
  mode once already.
- Small-n strata (neonate, infant) get confidence intervals, never bare
  point estimates, in every report.
- `python -m pytest -q` after every change; report anything that changes
  status, including tests that start passing for reasons you didn't intend.
- Document losing experiments in this file (or fold into
  `RISK_ENGINE.md` §6-style) with the actual numbers — this project's
  culture is to keep failed variants on record (fx-v2, fx-v3, feature
  pruning), not delete them.

---

## 6. Suggested order

1. **B1** — wire existing history through the API. Cheapest, no new data,
   fixes a documented gap, unblocks Group 2 of Track C.
2. **A1–A3** — scale synthetic data, multiple seeds, report per-stratum n.
3. **C, Group 1** — LightGBM/XGBoost bake-off against current features.
   Cheap, no architecture risk, can run in parallel with step 2's later
   part.
4. **Harness (§4)** — build once C-Group-1 has ≥2 candidate rows to compare;
   don't build it against a single model, or it will silently assume things
   about shape that break on model 2.
5. **C, Group 2** — sequence models, only after B1 ships and the torch
   environment is fixed. Last-observation control arm is part of this step,
   not a follow-up.
6. **B2** — cross-visit history design note. Independent of 1–5; land the
   scoping decision whenever, but do not start generator changes without it
   signed off.

---

## Research notes (grounding for §3, not repo-specific — verify against your own leaderboard, don't cite these numbers as MediPilot's)

- HistGradientBoosting reported as the most stable of the three GBDT
  variants across several clinical tabular comparisons, with LightGBM
  favoring large-N/tight-time budgets and XGBoost favoring smaller data and
  forgiving defaults — [XGBoost vs LightGBM: 2026 Comparison with Benchmarks](https://www.bohrium.com/en/blog/tutorials/xgboost-vs-lightgbm/), [An interpretable LightGBM model for predicting coronary heart disease](https://pmc.ncbi.nlm.nih.gov/articles/PMC12431356/).
- No significant improvement from full time-series modeling over
  last-observed vitals for hospital mortality prediction, in a 2026 vitals-only
  ICU study — the direct source for the mandatory last-observation control
  arm in Group 2: [Less is More: last observations of vital signs can outperform time series for hospital mortality prediction](https://www.medrxiv.org/content/10.64898/2026.05.05.26352366v1.full).
- TCNs report weaker long-range dependency capture than attention-based
  approaches for forward vitals prediction, and LSTMs are noted as
  hard to train/interpret and weak on very long dependencies despite strong
  results on shorter clinical sequences — background for candidate ordering
  in Group 2: [A Multi-Headed Transformer Approach for Predicting the Patient's Clinical Time-Series Variables From Charted Vital Signs](https://www.researchgate.net/publication/364136134_A_Multi-headed_Transformer_Approach_for_Predicting_the_Patient's_Clinical_Time-series_Variables_from_Charted_Vital_Signs).
