# MediPilot Risk Engine — Documentation

Status as of 2026-08-23: **trained, gated, and passing all 8 go-live checks
on synthetic data.** This document is the full record of how it got there —
architecture, every bug found and fixed, every research-driven change tried
(including the ones that failed), how to read the evaluation output, and the
changes still required before this could touch real patients.

Companion files: [`README.md`](README.md) (quick-start + API surface),
[`FIX_PLAN.md`](FIX_PLAN.md) (the earlier rules-layer bug-fix pass, F1–F6),
[`.claude/skills/medipilot-risk-model/SKILL.md`](.claude/skills/medipilot-risk-model/SKILL.md)
(condensed reference for future AI-assisted work on this codebase).

---

## 1. What this is

`backend` is the data/model/risk track of the MediPilot ED-triage
prototype. It takes patient vitals and produces a triage band (Red/Yellow/
Green) with a calibrated confidence and a conformal uncertainty set. Two
things sit side by side:

- **A rules layer** — deterministic, safety-critical, never learned.
- **A trained GBDT risk model** — supplies the probability the rules layer
  thresholds against.

Neither one is the whole system. The rules layer exists specifically because
the model is legitimately uncertain exactly where certainty matters most.

### 1.1 Origin state (before this work)

Before this pass, **no model was trained.** `scikit-learn` sat in
`requirements.txt` unused; the "risk engine" was a hand-coded weighted sum
(`_raw_risk_score`) with fixed constants; the synthetic generator emitted no
label of any kind; `compute_confidence()` was a heuristic with a dead
`_BASE_THRESHOLDS` stub; and `cost_ratio_R` had **zero** measured effect on
band assignment despite the whitepaper's whole pitch resting on a real,
trained, calibrated, conformal, cost-sensitive backbone. That gap is what
this work closes.

---

## 2. Architecture — the scoring pipeline

```
PatientRecord (from intake)
  1.  resolve_stratum        age -> one of 6 strata; inferred flag if unknown
  2.  RED-FLAG PASS          deterministic -> Red, EARLY RETURN, model never runs
  3.  OOD gate                -> AbstentionObject (band=yellow)
  4.  freshness                >3x cadence = missing, >2x = stale
  5.  all-vitals-missing       -> AbstentionObject
  6.  thresholds                per-stratum abnormality -> ThresholdResult[]
  7.  reliability weighting     asymmetric; only WIDENS uncertainty, never lowers risk
  8a. heuristic score           _raw_risk_score -> fallback score + FACTOR STRINGS
  8b. TRAINED MODEL              model/features.py -> GBDT -> Platt -> p_critical
  8c. abnormal_vital_floor      vulnerable strata -> at least Yellow
  8d. multi-vital floor         >=4 abnormal vitals -> at least Yellow
  8e. CRITICAL floor            GCS<=8 | SpO2<85 | SBP<70 | >=6 abnormal -> Red
  9.  conformal                  band from cost-sensitive thresholds; set width -> confidence
```

Steps 2, 3, 5, 8c, 8d, 8e are **rules, never model**. This is deliberate and
must stay that way: the model runs behind every hard safety guarantee, never
in front of one.

### 2.1 Key files

| File | Role |
|---|---|
| `model/risk_model.py` | Orchestrates the pipeline above; `PatientRecord`/`ScoreObject` contracts |
| `model/features.py` | THE single feature extractor — training and serving both go through it |
| `model/freshness.py` | Reading-age/staleness logic, shared by train and serve |
| `model/feature_registry.py` + `config/feature_registry.yaml` | Leakage enforcement — fails closed |
| `model/train.py` | Fits the GBDT, calibration, conformal quantiles, thresholds; writes the artifact |
| `model/evaluate.py` | The honesty layer — baseline/oracle comparison, all gates |
| `model/conformal.py` | Band assignment from cost-sensitive thresholds + conformal confidence |
| `model/calibration.py` | Legacy per-stratum hand-tuned multipliers (still used by the heuristic fallback) |
| `model/artifact.py` | Artifact loading + every fallback trigger |
| `model/predictor.py` | The serve-time seam; never raises into the triage path |
| `data/generator/trajectories.py` | Synthetic vitals time series, now with a per-patient latent |
| `data/generator/labels.py` | Outcome-derived label construction |
| `data/generator/bulk.py` | N-parameterised training-set generator |
| `config/label_spec.yaml` | Frozen label-generation parameters (hashed into the manifest) |

---

## 3. Data generation and labelling

### 3.1 The trap the design had to avoid

The obvious label source is the per-timestep `severity` latent in
`trajectories.py`, which drives every vital and used to be discarded. Using
it directly is a trap: late-window peak severity is essentially
`trajectory_shape != "improving"` (each `trajectory_shape` is a per-condition
constant), so a model trained on it scores **AUROC 0.988** by inverting the
generator, not by learning anything clinical. Full detail and the numbers
that proved it are in the skill file (§2, Trap 1).

### 3.2 The fix — three structural requirements

1. **Label lives strictly in the future** relative to the features. Features
   use steps `<= k`; the label is computed from severity strictly after `k`
   (`k` drawn uniformly from step 6–18, i.e. 30–90 min).
2. **A `frailty` latent enters the outcome and never touches any vital** —
   `PatientLatent.frailty`, drawn per-patient, stratum-conditioned mean
   (elevated for neonate/infant/geriatric). No feature set can recover it,
   which puts a hard floor under achievable AUC.
3. **The outcome is a Bernoulli draw**, not a threshold —
   `critical = Bernoulli(sigmoid(beta0 + beta1*s_max + beta2*s_mean + beta3*frailty))`.

Parameters live in `config/label_spec.yaml`, are hashed into the artifact
manifest, and were tuned against a **severity-oracle ceiling** (a model given
the true future peak severity) rather than against model performance:

| beta1 | beta3 | oracle AUROC |
|---|---|---|
| 8 | 0.50 | 0.808 |
| **10** | **0.40** | **0.869 — shipped** |
| 14 | 0.25 | 0.907 (frailty nearly vestigial) |

Two labels: primary `critical_composite_h180` (binary, drives the band) and
secondary `derangement_h60` (continuous, worst severity in a 60-min window —
the multi-task auxiliary).

### 3.3 The `stable_sudden` bug

`inflection = rng.uniform(0.55, 0.8)` was drawn **inside** `_severity_at()`,
called once per timestep — so every step re-sampled its own inflection point.
Severity paths oscillated (`0.47 → 0.24 → 0.51 → 0.72 → 0.52`) instead of
deteriorating monotonically. This silently removed the deterioration-while-
waiting signal — the entire product thesis — from a third of the synthetic
population.

**Fix:** `_severity_path()` draws inflection once per patient. The old
`_severity_at()` is kept as a deprecated single-step wrapper for backward
compatibility only — **do not use it to generate training data.**

### 3.4 Neonate coverage gap

Zero of the original 15 clinical conditions defined a neonate vitals
distribution; `vitals_for_stratum()` silently fell back to adult physiology.
The model had **zero neonate exposure** despite neonate carrying the most
aggressive `calibration_weight` (1.8) in the rules layer.

**Fix:** added neonate distributions to three conditions — sepsis (C01),
febrile-non-sepsis (C04), and a **well** neonate (C15). The well case matters:
without a negative example the stratum has no way to learn anything but a
constant "neonate ⇒ critical".

### 3.5 Bulk generation

`data/generator/bulk.py` is the N-parameterised driver (`build_corpus()` only
produces the fixed 20-record demo corpus). Sampling is **restricted to
explicitly-defined `(condition, stratum)` pairs** (32 currently) rather than
uniform over all combinations, specifically to avoid silently fabricating,
e.g., a "neonate with adult trauma physiology" via the fallback. Throughput:
~163 trajectories/sec, so 20k patients ≈ 2 minutes.

Regenerate with:
```bash
python -m data.generator.bulk --n 20000 --seed 1337 --out data/train_set.jsonl
```

---

## 4. Feature engineering

### 4.1 One extractor, two adapters

`model/features.py::build_feature_row()` is the **only** place a feature
matrix is built. `from_patient_record()` (serving) and
`from_trajectory_snapshot()` (training) are the two adapters into it, both
routed through the same freshness logic (`model/freshness.py`). This is a
correctness requirement: if training and serving computed freshness
differently, every downstream number would be wrong on a different input
distribution than the one being tested, and nothing would report it.
`tests/test_features.py::test_train_and_serve_adapters_agree` is the guard.

### 4.2 Missing-value discipline

Missing vitals are `np.nan`, never a sentinel (`-999`, `0`, etc.).
`HistGradientBoostingClassifier` learns a per-node missing direction only
from real NaN; a sentinel would silently convert "unknown" into "extremely
abnormal" — the dangerous direction for a triage model.
`tests/test_features.py::test_nan_branch_is_actually_used` proves the native
handling is live, not merely available.

### 4.3 Current feature set: **59 columns, `fx-v4`**

Per vital (7 vitals × 6 = 42): `value`, `z_stratum` (signed deviation from
the stratum's own normal range — GCS special-cased to avoid a divide-by-
~0 explosion), `age_minutes`, `slope_per_hour` (OLS over trailing 30 min),
`delta_30min`, `n_readings`. Plus 17 global features: age, stratum one-hot +
ordinal + inferred flag, vital present/missing/stale counts, reading-age
stats, sensor-failure fraction, and `aux_derangement_oof` (the stacked
auxiliary head's out-of-fold prediction).

**`FEATURE_VERSION` history: fx-v1 (59, shipped) → fx-v2 (68, reverted) →
fx-v3 (62, reverted) → fx-v4 (59, current — identical to fx-v1).** See §6.2
for why the intervening versions were rolled back; the version string still
advanced so the artifact/feature-contract guard in `model/artifact.py`
correctly treats fx-v2/v3 artifacts as incompatible.

### 4.4 Leakage control

`config/feature_registry.yaml` classifies every field SAFE / CONDITIONAL /
PROHIBITED; `model/feature_registry.py::assert_features_permitted()` enforces
it at `features.py` import time, so a prohibited column cannot enter a
feature matrix. **Fails closed** — an unregistered field defaults to
PROHIBITED, so a new generator field breaks the build until classified.

Never features: `condition_id`, `typical_band`, `trajectory_shape`,
`_latent`/`acuity`/`frailty`/`severity_path`, both labels, `s_max_future`,
`red_flag_observations` (the local Epic-Sepsis-Model analogue — extracted
clinician suspicion, and it pre-empts the model anyway), `current_band`
(self-confirming). Conditional-only: `spo2_bias_risk` (de-escalation guard
only — as a risk feature it would make risk a function of skin tone) and
`reliability_flags` (uncertainty inflation only — as score features they'd
let the model *lower* risk for a stoic geriatric, inverting the intended
asymmetry).

---

## 5. Model, calibration, and thresholds

### 5.1 Model choice

`sklearn.ensemble.HistGradientBoostingClassifier`. lightgbm and xgboost are
**not installed** in this environment; torch is installed but broken (DLL
init failure, verified). HistGBDT is a real GBDT of the family the whitepaper
names, already a dependency, native NaN handling, no install risk.

### 5.2 Two heads — honestly described as a stack, not multi-task

sklearn has no multi-task GBDT. This is a **two-stage stack**: a
`HistGradientBoostingRegressor` predicts the secondary derangement label;
its **out-of-fold** prediction (via `cross_val_predict` on train only)
becomes one input column (`aux_derangement_oof`) to the primary classifier,
which is refit on the full train split for serving. Achieves the
whitepaper's "secondary label constrains the primary", but is not literally
a shared trunk — the README says so explicitly.

### 5.3 Cost-sensitive training

Positives are upweighted 3× (`sample_weight`) at training time — the
whitepaper's asymmetric loss, previously absent entirely. Deliberately
modest, not the clinical 100–1000× cost ratio: extreme weights wreck
probability calibration, which the conformal layer and thresholds both
depend on. The clinical asymmetry lives in the **threshold** (§5.5), not the
loss.

### 5.4 Calibration — Platt, not isotonic

**Bug found:** isotonic regression is unconstrained and overfits below
roughly 2,000 calibration cases (Niculescu-Mizil & Caruana). The calibration
split here is ~2,000 rows **in total**, so every individual stratum is far
below that threshold. Symptom: ECE looked fine (0.025) while the
**reliability slope sat at 0.612** against an ideal of 1.0 — systematic
over-dispersion invisible to ECE alone.

**Fix:** Platt scaling (2-parameter logistic regression on the logit) is now
the default for every stratum; isotonic is reserved for a split that
genuinely clears `_MIN_N_ISOTONIC = 2000` rows. Result: **slope 0.612 →
0.954**, ECE 0.025 → 0.011.

### 5.5 Thresholds — three separate bugs, each independently reintroducing a 42% miss rate

The first trained model left **42.2% of critical patients in Green** while
passing every gate that existed at the time. Root-caused to three distinct
bugs, found in sequence — each one alone would have been enough:

1. **Band-mix thresholds instead of a recall budget.** `p*_yellow` was set
   to the 70th percentile of *predictions* — symmetric thinking on an
   asymmetric problem. **Fix:** `solve_thresholds()` now sets `p*_yellow`
   from the 10th percentile of predictions **among positives** — a direct
   recall guarantee. Over-triage becomes a reported consequence, never a
   target.
2. **`band = pred_set[0]`** took the *highest* band in the conformal
   prediction set. With a legitimately uncertain model this pushed 46% of
   the department into Red (raw threshold implied 26%). **Fix:** band is now
   the point decision from the thresholds; the conformal set drives
   confidence and abstention only.
3. **`_thresholds_from_R` was doubly broken** — it clamped `p_red` to
   `p_yellow − 0.01` (inverting the ordering), and its range-clamping
   discarded the solved thresholds, silently lifting the effective Yellow
   cut from 0.053 to 0.101. Compounding this, `DEFAULT_COST_RATIO_R = 2.0`
   overrode the trained operating point on every default call. **Fix:**
   `_thresholds_from_R` now anchors on the trained operating point and
   scales both cuts monotonically with R; the shipped default is the
   sentinel `USE_TRAINED_R = None`, meaning "use exactly what was solved at
   training time" rather than a hardcoded constant.

### 5.6 Per-stratum thresholds — required for fairness, not optional

Equalising FNR across groups **mathematically requires group-differential
thresholds**: a single global cut gives equal *scores* but unequal *miss
rates* whenever per-group score distributions differ, which they do here
(each stratum has its own calibrator). `solve_per_stratum_thresholds()`
solves a separate Yellow cut per stratum to the same recall target, with a
documented fallback to the global cut for strata with `<20` calibration
positives. Result: child FNR **0.212 → 0.077**, spread **0.52 → 0.195**.

The child problem was never purely a modelling artefact — the paediatric
literature backs the generator's physiology: children *compensate until
reserves are exhausted*, holding near-normal vitals while deteriorating, so
a snapshot-weighted score genuinely under-ranks them.

### 5.7 A real safety hole found and closed: the critical-derangement floor

Verified end-to-end: a peri-arrest patient (HR 190, RR 44, SBP 60, SpO₂ 72,
GCS 4) scored **Yellow** — the multi-vital floor (§2, step 8d) only lifts to
Yellow, and the model was genuinely unsure about this single-snapshot
extreme (sparse in training). **Fix:** added step 8e, a critical-derangement
floor that forces Red on any of GCS ≤ 8, SpO₂ < 85, SBP < 70, or ≥6
simultaneously abnormal vitals — individually life-threatening values in
any stratum, not a composite score. This is rules-layer, not model, on
purpose: single-snapshot extremes are exactly where the model should be
overridden.

### 5.8 Modality dropout — a train/serve distribution mismatch

**Measured bug:** trend features (`slope_per_hour`, `delta_30min`) were
populated in **94% of training rows and 0% at serve time**. The training
adapter always has `k_step >= 6` prior readings (i.e. history exists by
construction); a `PatientRecord` arriving from intake typically carries a
single snapshot. The model had learned to lean on trends it never receives
in production — the single extractor guaranteed the same *code* ran on both
sides, not the same *input distribution*.

**Fix:** `HISTORY_DROPOUT_RATE = 0.40` in `build_matrices()` — 40% of
training rows are built with `history=None`, forcing the model to produce a
usable estimate without trend features. This is the whitepaper's own
"train-time modality dropout," specified and previously unimplemented for
the trend block. Cost: AUPRC 0.176 → 0.174, AUROC 0.705 → 0.689 — a
deliberate, correct trade. The model is now honest about the conditions it
actually runs in; measured separately, it still beats the baseline in
**both** regimes (0.190 vs 0.178 with history; 0.166 vs 0.135 without).

---

## 6. Research-driven feature experiments — including the failures

### 6.1 What was tried

Literature review surfaced three well-evidenced clinical indices:

- **Shock Index** (HR/SBP): SI ≥1.2 → OR 11.1 for mortality.
- **Age Shock Index** (SI × age): OR 12.14 — strongest of the three in a
  district-ED cohort.
- **SIPA** (paediatric age-adjusted SI, thresholds 1.2 under-6y / 1.0 older):
  documented to detect **compensated shock earlier** than isolated vitals —
  seemingly a direct hit on the paediatric FNR problem.
- **ROX-like** (SpO₂/RR, room-air simplification of true ROX): beat NEWS2
  (AUC 0.848 vs 0.815), fired ~4h earlier for respiratory deterioration.
- **NEWS2-style aggregate score** and **max/mean absolute z-score** across
  vitals — aggregation the tree would otherwise have to rediscover through
  deep interactions.

All nine were added as `fx-v2` (68 features), and separately the aggregates
alone as `fx-v3` (62 features), with and without permutation-importance-based
pruning.

### 6.2 Measured result: every variant was a net negative

| Config | Features | AUPRC | slope | FNR spread | Verdict |
|---|---|---|---|---|---|
| **fx-v1 / fx-v4 (shipped)** | 59 | **0.174** | **0.954** | **0.195** | kept |
| fx-v2 full ratio block | 68 | 0.155 | 0.826 | 0.317 | reverted |
| fx-v3 aggregates + pruning | 62→27 | 0.165 | 0.765 | 0.195 | reverted |
| fx-v3 aggregates, no pruning | 62 | 0.155 | 0.824 | 0.341 | reverted |

### 6.3 Why the clinical indices failed — not the expected reason

First hypothesis was that the generator lacked the physiological coupling
the indices exploit. **This was checked and disproven:** `corr(HR, SBP) =
−0.741` in the generated data — real, strong shock coupling. The actual
mechanism is **collinearity**: shock index correlates +0.908 with HR and
−0.851 with SBP, so it re-expresses information the model already has. In
real cohorts SI earns its place because the risk surface is *non-linear* in
the component vitals and a tree needs depth to carve that; here the coupling
is strong and near-linear, so nine extra columns bought variance on ~1,170
training positives and nothing else.

**Standing instruction:** do not re-add the ratio block against this
synthetic generator. It is a candidate worth revisiting only against data
whose risk surface is genuinely non-linear in HR/SBP/RR/SpO₂ — i.e. real
patient data.

### 6.4 Why feature pruning failed — the more dangerous lesson

Permutation importance measured on the **held-out calibration split**
(never test) showed 34 of 68 features at ≤0 importance. Pruning to
positive-importance columns raised **calibration-split AP 0.183 → 0.211**
— and simultaneously *lowered* **test AUPRC 0.174 → 0.165** while wrecking
the reliability slope (0.954 → 0.765).

Selecting features by permutation importance on ~2,000 rows with ~195
positives selects noise, and the apparent gain is measured on the very split
the selection overfit to. **This is the general lesson:** an improvement
measured on the split used to make the selection decision is not a proven
improvement — test-set confirmation on a split untouched by the decision is
mandatory. Pruning is now `train.py --prune`, off by default, kept only as
an experimental hook with this failure documented inline.

---

## 7. How to read the evaluation output

Run `python -m model.train --data data/train_set.jsonl` then
`python -m model.evaluate`.

### 7.1 Read in this order

1. **The three-row comparison table.** Below the *prevalence floor* → model
   is worthless regardless of AUROC. Below the *hand-coded baseline* → ship
   the rule card instead. At or above the *severity oracle* → leakage (the
   oracle knows the true future severity; nothing legitimate beats it).
2. **Oracle gap** (`model AUPRC / oracle AUPRC`). Near 100% is a leakage
   warning, not a triumph. Near 0% means the features don't carry the
   signal. Current: **42%** — real signal, considerable headroom.
3. **Green-miss rate** — the clinically decisive number: share of critical
   patients left below Yellow, at the thresholds that actually ship
   (per-stratum where available). Gated at ≤0.15. Current: **0.115**.
4. **Baseline comparison, significance-aware.** Reported as significant
   wins/losses/ties using disjoint bootstrap CIs — a small numeric
   difference with heavily overlapping CIs is a tie, not a win. Current: 1
   significant win, 0 losses, 3 ties.
5. **Calibration slope and intercept, not ECE alone.** Ideal (1.0, 0.0).
   ECE can look fine while slope reveals systematic over-dispersion (§5.4).
6. **Conformal coverage AND mean set size together.** Coverage ≥0.90 without
   set-size context is gameable — a method that always returns all three
   bands has perfect coverage and zero value. Current: 0.910 coverage,
   1.08 mean set size.
7. **FNR spread with CIs and n_pos.** Never quote a bare max−min gap — at
   these positive counts (as low as ~40 for neonate) the CI is wide.

### 7.2 Numbers that should trigger suspicion, not celebration

| Symptom | Almost certainly |
|---|---|
| AUROC > 0.95 | leakage — the naive label gave 0.988 |
| Prevalence > 20% | label collapsed to a condition-identity lookup |
| Model ≈ oracle | leakage |
| ECE fine, slope << 1 | isotonic overfit on a small calibration split |
| Green-miss low AND over-triage low simultaneously | threshold applied on the wrong score scale (this exact bug happened once — see §5.5.3 history in git blame) |
| "Trend features unimportant" | train/serve modality mismatch, not a real finding |

### 7.3 The eight go-live gates

All must be `True`: `prevalence_in_range`, `auroc_in_range` (**fails above
0.95** — the leakage canary), `auprc_beats_prevalence`,
`conformal_coverage_ge_090`, `ece_lt_005_where_reportable`,
`green_miss_rate_within_budget`, `equalised_fnr_across_strata`,
`beats_handcoded_baseline`. **Current state: 8/8 pass.**

---

## 8. Current results and honest verdict

On 4,001 held-out synthetic patients at 9.76% prevalence:

| Metric | Value |
|---|---|
| AUPRC | 0.174 (baseline 0.156, oracle 0.410, floor 0.098) |
| AUROC | 0.689 (naive-leaked ceiling 0.988, oracle 0.869) |
| Oracle gap | 42% of achievable AUPRC captured |
| Green-miss rate | 0.115 (started at 0.422) |
| Reliability slope / intercept | 0.954 / −0.083 (started at 0.612 / −0.739) |
| Conformal coverage / mean set size | 0.910 / 1.08 |
| FNR spread across strata | 0.195 (started at 0.52) |
| Baseline comparison | 1 significant win, 0 losses, 3 ties |
| Go-live gates | **8 / 8 pass** |

**This is a validated pipeline, not a validated model.** It is not fake
(AUROC 0.689 against a 0.988 fake ceiling and a 0.869 oracle is the correct
signature of a model that learned something real and incomplete). It is
modestly better than the rule card it replaces, not overwhelmingly. It
captures under half the achievable signal. **Most of the clinical safety
improvement over the session came from thresholds and rules, not from the
model** — green-miss fell from 42% to 11.5% almost entirely through
threshold design and hard floors, while AUPRC moved only slightly.

**What it does not prove:** a model trained on synthetic data generated by
this project's own assumptions validates the *pipeline* — that training,
calibration, conformal abstention, and cost-sensitive thresholding are wired
correctly end to end. It says nothing about real clinical performance. That
requires the real-data phases the whitepaper already specifies (MIMIC-IV-ED
for architecture validation, then partner-hospital data).

---

## 9. Required changes — outstanding work

Ordered by expected impact.

### 9.1 High priority

- **Wire `PatientRecord.vitals_history` through the live API.** The model
  was trained on trend features and Loop A already re-scores every patient
  every 5 minutes per the product architecture — the history exists, it is
  simply not passed to the scorer today. This is the single highest-value
  lever available without new data: it is what would let trend features
  earn their keep, and paediatric deterioration specifically depends on
  trend over snapshot (§5.6, §6.3's clinical literature).
- **Fix `backend/api.py` `/queue` sorting.** It currently sorts on
  `1.0 - confidence` (inverse confidence), not on actual risk. With the
  confidence-inversion bug fixed on the model path, this needs re-auditing —
  confidence and risk are no longer the same axis and should not be
  conflated in the queue ordering.
- **Real-data validation phase.** Everything in §8 is a pipeline-correctness
  demonstration on self-generated data. No claim here transfers to real
  patients until validated on MIMIC-IV-ED (architecture only, no India
  claim) and then partner-hospital data, per the whitepaper's four-phase
  acquisition plan.

### 9.2 Medium priority

- **Close the oracle gap.** 42% captured leaves real headroom. Candidate
  directions, in order of expected payoff: (a) richer trend features once
  §9.1 is wired (current trend features are underused because they're
  usually absent at serve time); (b) a genuinely non-linear feature
  interaction the tree isn't finding on its own — needs measurement, not
  guessing (see §6.4's lesson: measure on held-out, confirm on test); (c)
  more training data — 20k patients gives ~195 positives per typical
  stratum split, which is thin for the fairness claims already being made.
- **Neonate and infant strata need more data.** FNR remains highest here
  (neonate 0.195+ with wide CIs on ~40 positives). The three neonate
  conditions added in §3.4 are a floor, not a solution — before any louder
  claim about neonates, either generate substantially more neonate volume
  or explicitly flag the stratum as underpowered in every report that
  touches it.
- **Re-evaluate physiological ratio features against real data.** §6.3's
  finding (collinearity, not absence of signal) means shock index / SIPA /
  ROX are not dead ideas — they are untested against data with the
  non-linear risk surface where they're documented to work. Revisit once
  real-data access exists; do not re-add against the synthetic generator.
- **`monotonic_cst` on the primary GBDT.** Not yet tried. Literature
  suggests "negligible predictive loss" and improved governance/
  interpretability for features with unambiguous clinical direction (e.g.
  `gcs_z_stratum` should only ever push risk up as it worsens). Worth a
  measured experiment following the same held-out-then-test protocol as
  §6.4, given the demonstrated cost of skipping that protocol.

### 9.3 Lower priority / hygiene

- **`compute_confidence()` naming.** `calibrated_score` parameter now
  sometimes carries a real model probability and sometimes the legacy
  heuristic score — the dual meaning is documented in the fallback comments
  but not in the signature. Consider splitting the parameter for clarity
  before this file gets another owner.
- **`test_p04_ambiguous_presentation_low_confidence`** — flagged during
  the original design pass as a test that will need rewriting once the real
  conformal path exercises it (a near-normal patient under real conformal
  is confidently Green, not uncertain — see the design notes referenced in
  `FIX_PLAN.md`). Confirm this test still asserts something true after the
  changes in this document; it was written against the heuristic path.
- **Retire or clearly separate `_severity_at()`.** Kept only for backward
  compatibility (§3.3); a stray call from new code would silently
  regenerate the oscillating-severity bug. Consider a runtime warning or
  moving it to a clearly-marked legacy module.

---

## 10. If you retrain

1. Regenerate data if the generator or `config/label_spec.yaml` changed
   (~2 min / 1k patients; `beta0` is re-solved for target prevalence).
2. Note the severity-oracle ceiling the run prints — the only way to know
   whether a resulting score reflects a weak model or a genuinely hard task.
3. `python -m model.train --data data/train_set.jsonl`
4. `python -m model.evaluate` — check all 8 gates. If `auroc_in_range` fails
   high, you have leakage; stop and investigate before doing anything else.
5. `python -m pytest -q` — 94 tests must pass, including the leakage canary
   and the four fx-v1-era string assertions in
   `test_p02_p03_same_temperature_...`.
6. Delete `model/artifacts/` and confirm `score_patient()` falls back
   cleanly to `score_source="fallback_heuristic"` with all tests still
   green.
7. Run the R-sweep demo and confirm bands actually re-sort across R.

**Do not tune a threshold or hyperparameter to make a gate pass.** Every
constant in this codebase has a stated, measured reason (§§5–6 above); if
one needs to change, the reason changes first, in writing, here.

**Not in version control, regenerable:** `data/train_set.jsonl` (~550 MB) —
seed 1337 plus `config/label_spec.yaml` fully determines it. Model artifacts
**are** committed so the fallback path is exercised against a real artifact,
not just a mocked absence.
