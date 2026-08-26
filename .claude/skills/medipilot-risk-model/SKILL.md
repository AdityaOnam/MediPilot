---
name: medipilot-risk-model
description: The trained risk backbone in medipilot-model — how the supervised model was built on synthetic data, the seven traps that made earlier versions look good while being wrong, how to read model/evaluate.py output, and how good the model actually is. Invoke before retraining, before changing the generator/labels/thresholds/calibration, before quoting any AUROC or fairness number from this project, and whenever an evaluation result looks too good.
last_verified: 2026-08-23
---

# MediPilot risk model — what it is, why it is built this way, and how good it is

Covers `D:\medipilot-whitepaper\medipilot-model`. This is the data/model/risk
track: synthetic data generation, the trained GBDT, calibration, conformal
abstention, cost-sensitive thresholds, and the safety rules wrapped around them.

**The single most important thing in this file:** on synthetic data it is easy
to produce a model that looks excellent and means nothing. Section 2 lists the
seven specific ways that happened here, each with the measurement that exposed
it. Read that before trusting any number this project prints.

---

## 1. Architecture, in the order a patient flows through it

```
PatientRecord (from intake)
  ├─ 1. resolve_stratum          age -> one of 6 strata (inferred flag if unknown)
  ├─ 2. RED-FLAG PASS            deterministic -> Red, EARLY RETURN, model never runs
  ├─ 3. OOD gate                 -> AbstentionObject (band=yellow)
  ├─ 4. freshness                >3x cadence = missing, >2x = stale
  ├─ 5. all-vitals-missing       -> AbstentionObject
  ├─ 6. thresholds               per-stratum abnormality -> ThresholdResult[]
  ├─ 7. reliability weighting    asymmetric; only widens uncertainty
  ├─ 8a. heuristic score         _raw_risk_score -> fallback score + FACTOR STRINGS
  ├─ 8b. TRAINED MODEL           features.py -> GBDT -> Platt -> p_critical
  ├─ 8c. abnormal_vital_floor    vulnerable strata -> >= Yellow
  ├─ 8d. multi-vital floor       >=4 abnormal -> >= Yellow
  ├─ 8e. CRITICAL floor          GCS<=8 | SpO2<85 | SBP<70 | >=6 abnormal -> Red
  └─ 9. conformal                band from thresholds; set width -> confidence
```

**Layers 2, 3, 5, 8c, 8d, 8e are rules, not model.** They exist because the
model is uncertain exactly where certainty matters most. Never move a guarantee
into the model to "simplify".

Key files: `model/features.py` (the ONE extractor), `model/train.py`,
`model/evaluate.py`, `model/conformal.py`, `data/generator/labels.py`,
`data/generator/bulk.py`, `config/feature_registry.yaml`, `config/label_spec.yaml`.

---

## 2. The seven traps — each one made a bad model look good

### Trap 1 — The obvious label gives AUROC 0.988 and means nothing

`trajectories._severity_at()` computes a per-timestep severity latent that
drives every vital, then discards it. It is the obvious label source. Using it
directly produces a fake result.

Measured: late-window peak severity is essentially a lookup on
`trajectory_shape`, which is a per-condition constant.

| shape | mean late peak | p10 | p90 |
|---|---|---|---|
| `improving` | 0.54 | 0.50 | 0.58 |
| `compensating_then_decompensating` | 0.99 | 0.96 | 1.00 |
| `stable_sudden` | 0.98 | 0.94 | 1.00 |

So "peak severity > 0.7" collapses to `trajectory_shape != improving`,
prevalence 81%. Each condition has distinctive vital means, so the condition is
nearly perfectly recoverable from the vitals. Trained on t=0 vitals alone:
**prevalence 79.6%, AUROC 0.988, AUPRC 0.997.**

That number measures "can you invert a known generative model", not "can you
predict deterioration". Shipping it would reproduce the Epic Sepsis Model
failure the whitepaper is built around criticising.

**Fix — three structural changes, all required:**
1. Label lives strictly in the FUTURE relative to features (features from steps
   `<= k`, label from severity after `k`, `k` drawn from 6–18).
2. A `frailty` latent enters the outcome and **never touches any vital**, so no
   feature set can recover it — a hard floor under Bayes error.
3. The outcome is a **Bernoulli draw**, not a threshold.

### Trap 2 — Balance the label noise or the ceiling collapses

First attempt at Trap 1's fix over-corrected: `beta3=0.8, frailty_sd=1.0` made
the frailty term's variance exceed the severity term's, so the label was mostly
unpredictable noise. **Even a perfect severity oracle scored AUROC 0.676.**

Tuned against the oracle ceiling, not against model performance:

| beta1 | beta3 | oracle AUROC |
|---|---|---|
| 8 | 0.50 | 0.808 |
| **10** | **0.40** | **0.869** (chosen) |
| 14 | 0.25 | 0.907 (frailty nearly vestigial) |

**Always compute the oracle ceiling before training anything.** It is the only
way to know whether a mediocre score means a weak model or an impossible task.

### Trap 3 — `stable_sudden` had no sudden event

`inflection = rng.uniform(0.55, 0.8)` was drawn **inside** `_severity_at`, which
is called once per timestep — so every step re-sampled its own inflection. The
path oscillated (`0.47 → 0.24 → 0.51 → 0.72 → 0.52`) instead of deteriorating.

The deterioration-while-waiting signal — the entire product thesis — was
largely absent from the data. Inflection is now drawn once per patient in
`_severity_path()`. `_severity_at()` is kept as a deprecated wrapper; **do not
use it to generate training data.**

### Trap 4 — Confidence was inverted

The heuristic measured "distance to the lower boundary" for a Green patient
against `0.0`, which is not a boundary. Result:

| score | band | confidence |
|---|---|---|
| 0.05 | green | 0.050 |
| **0.34** | green | **0.779** (highest) |
| 0.95 | red | 0.050 |

Maximally confident **at** the decision boundary, minimally confident about
obviously-healthy and obviously-critical patients. Two tests "passed" on this
vacuously. Fixed on the model path; the legacy formula survives only in the
artifact-absent fallback.

### Trap 5 — Three separate threshold bugs, each restoring a 42% miss rate

The first trained model left **42.2% of critical patients in Green** while
passing every gate that existed. Three causes, found in sequence:

1. **Thresholds set by band mix.** `p*_yellow` was the 70th percentile of
   *predictions* — symmetric thinking on an asymmetric problem. Now solved from
   an **under-triage budget**: the 10th percentile of predictions **among
   positives**, a recall guarantee. Over-triage becomes a reported consequence,
   not a target.
2. **`band = pred_set[0]`** took the highest band in the conformal set. With a
   legitimately uncertain model that pushed **46% of the department into Red**
   while the raw threshold implied 26%. Band is now the point decision; set
   width drives confidence only.
3. **`_thresholds_from_R` was doubly broken** — it forced `p_red < p_yellow`
   (inverted), and its clamping discarded the solved thresholds, lifting the
   effective Yellow cut from 0.053 to 0.101. Also `DEFAULT_COST_RATIO_R = 2.0`
   overrode the trained operating point entirely. The default is now the
   sentinel `USE_TRAINED_R = None`.

### Trap 6 — Trend features present in training, absent in production

Measured: slope/delta populated in **94% of training rows, 0% at serve time.**
The training adapter always has `k_step >= 6` prior readings; a `PatientRecord`
from intake carries one snapshot. The model learned to lean on trends it never
receives.

The shared extractor did not prevent this — it guaranteed the same *code*, not
the same *input distribution*. Fixed with 40% `HISTORY_DROPOUT_RATE`, which is
the whitepaper's own "train-time modality dropout", specified and never
implemented for the trend block.

**This cost discrimination and that is correct:** AUPRC 0.176 → 0.174,
AUROC 0.705 → 0.689. The model is now honest about the conditions it runs in.

### Trap 7 — Isotonic overfits, and only the slope shows it

ECE looked fine at 0.025 while the **reliability slope sat at 0.612** against an
ideal of 1.0 — systematic over-dispersion, invisible to ECE alone.

Isotonic is unconstrained and overfits below ~2,000 calibration cases
(Niculescu-Mizil & Caruana). The calibration split is ~2,000 rows *in total*, so
every stratum was far below it. Platt has two parameters, fits on the logit
scale, and targets slope directly. **Slope 0.612 → 0.954, ECE 0.025 → 0.011.**

**Always report slope and intercept alongside ECE.** ECE alone hides this.

---

## 2b. What was tried and did NOT work — do not repeat these

An aggressive literature-driven feature push was run and **every block was a net
negative.** The 59-column fx-v1 set remains the best configuration found. These
are recorded so nobody spends the day rediscovering them.

| Attempt | Features | AUPRC | slope | FNR spread | Verdict |
|---|---|---|---|---|---|
| **fx-v1** | 59 | **0.174** | **0.954** | **0.195** | **shipped** |
| fx-v2 ratio block | 68 | 0.155 | 0.826 | 0.317 | reverted |
| fx-v3 aggregates + prune | 62→27 | 0.165 | 0.765 | 0.195 | reverted |
| fx-v3 aggregates, no prune | 62 | 0.155 | 0.824 | 0.341 | reverted |

### Why the clinical indices failed — and it is NOT the reason you would guess

Added Shock Index (HR/SBP), SIPA age-adjusted SI, Age Shock Index, ROX-like
(SpO2/RR), a NEWS2-style aggregate, and shock-index trend. All are well
evidenced in ED literature (SI ≥1.2 → OR 11.1 mortality; ASI → OR 12.14; SIPA
detects compensated shock earlier; ROX beat NEWS2 AUC 0.848 vs 0.815 and fired
4h earlier). The reasoning was sound: trees cannot construct ratios from
axis-aligned splits.

First hypothesis — "the generator lacks the physiological coupling" — was
**wrong, and measurement disproved it**: `corr(HR, SBP) = −0.741`, which is real
shock coupling.

The actual mechanism is **collinearity**. Shock index correlates **+0.908 with
HR and −0.851 with SBP**, so it re-expresses what the model already has. In real
cohorts SI earns its place because the risk surface is *non-linear* in the
component vitals and a tree needs depth to carve it. Here the coupling is strong
and near-linear, so nine extra columns bought variance on ~1,170 positives and
nothing else.

**Re-add the ratio block only against data whose risk surface is non-linear in
the component vitals — i.e. real data.** This is a concrete instance of
"synthetic data validates the pipeline, not the medicine".

### Why feature pruning failed — the more dangerous trap

Permutation importance on the held-out calib split showed 34 of 68 features at
≤0 importance. Pruning to those with positive importance raised **calib AP
0.183 → 0.211** — and *lowered* **test AUPRC 0.174 → 0.165** while wrecking the
slope (0.954 → 0.765).

Selecting features by permutation importance on 2,000 rows with ~195 positives
selects noise, and the apparent gain is measured on the very split the selection
overfit. Pruning is disabled by default; `--prune` re-enables it for experiments.

**The transferable lesson: an improvement measured on the split used to make the
decision is not an improvement.** Test-set confirmation is mandatory, and the
held-out ranking differed materially from the test ranking, which is exactly why
selection must never touch test.

---

## 3. Fairness — why per-stratum thresholds, not a global one

A single global cut gives equal *scores* but unequal *miss rates* whenever group
score distributions differ, which they do here since each stratum has its own
calibrator. Equalising FNR mathematically **requires** group-differential
thresholds.

Child FNR went 0.212 → 0.077, spread 0.52 → 0.195, via per-stratum Yellow cuts
solved to the same recall.

The child problem was never purely an artefact. The paediatric literature
describes what the generator encodes: children *compensate until reserves are
exhausted*, holding near-normal vitals while deteriorating, so a
snapshot-weighted score genuinely under-ranks them, and dynamic trends beat
static thresholds. That is a real reason to wire history through, not just to
move a threshold.

**Grade with the cuts that actually ship.** `evaluate.py` mirrors the serving
path via `effective_yellow_cuts()`. Grading with the global cut while shipping
per-stratum cuts reports a number for a configuration that never runs.

---

## 4. Leakage control

`config/feature_registry.yaml` classifies every field SAFE / CONDITIONAL /
PROHIBITED. `model/feature_registry.py` enforces it at `features.py` import, so
a prohibited column cannot enter a feature matrix.

**Fails closed** — an unregistered field is PROHIBITED, so a new generator field
breaks the build until classified. That is the point.

Never features: `condition_id`, `typical_band`, `trajectory_shape`, `_latent`
(acuity/frailty/severity_path), `p_event`, both labels, `s_max_future`,
`red_flag_observations` (the local Epic analogue — clinician suspicion, and it
pre-empts the model anyway), `current_band` (self-confirming).

Conditional: `spo2_bias_risk` — de-escalation guard only; as a risk feature it
would make risk a function of skin tone. `reliability_flags` — uncertainty
inflation only; as score features they would let the model *lower* risk for a
stoic geriatric, the exact inverse of the intended asymmetry.

---

## 5. How to read `python -m model.evaluate`

Run `python -m model.train` first, then `python -m model.evaluate`.

### Read in this order

**1. The three-row comparison table — always read all three.**
```
                          AUPRC    AUROC
trained model            0.1740   0.6894
hand-coded baseline      0.1561   0.6302
severity oracle          0.4104   0.8658
prevalence floor         0.0977
```
- Below the **prevalence floor** the model is worthless regardless of AUROC.
- Below the **baseline**, ship the rule card instead.
- At or above the **oracle**, you have leakage — the oracle knows the true
  future severity, so nothing legitimate beats it.

**2. Oracle gap.** `model captures 42% of achievable AUPRC`. Near 100% means
leakage, not triumph. Near 0% means the features do not carry the signal.
40–70% is the honest working range here.

**3. Green-miss — the number that matters clinically.** Share of critical
patients left below Yellow, at the cuts that actually ship. Gated at ≤0.15.
A single number; do not average it away.

**4. Baseline comparison, significance-aware.** Reported as significant
wins/losses/ties using disjoint bootstrap CIs. A 0.003 difference with 90%
overlapping CIs is a tie, not a win — an earlier version of this gate counted
exactly that as a win and an exact 0.486/0.486 tie as a loss.

**5. Calibration — slope and intercept, not just ECE.** Ideal (1.0, 0.0).
Slope < 1 means over-dispersed probabilities. ECE alone will not show it.

**6. Conformal coverage AND mean set size.** Coverage ≥0.90 is meaningless
without efficiency: a method that always returns `{green, yellow, red}` has
perfect coverage and zero value. Current: 0.910 coverage, 1.08 set size.

**7. FNR spread with CIs and n_pos.** Never quote a bare max−min gap. Neonate
at 0.195 on 41 positives has a CI of [0.075, 0.325] — that is a wide interval,
not a precise finding.

### The gates

All eight must be `True`. `auroc_in_range` **fails above 0.95** — that is the
leakage canary, and a high AUROC here is bad news, not good.

### Numbers that should make you suspicious

| Symptom | Almost certainly |
|---|---|
| AUROC > 0.95 | leakage (Trap 1) |
| Prevalence > 20% | label collapsed to a condition lookup |
| Model ≈ oracle | leakage |
| ECE fine, slope << 1 | isotonic overfit (Trap 7) |
| Green-miss low AND over-triage low | threshold applied on the wrong score scale |
| Trend features unimportant | Trap 3 or Trap 6, not a finding |

---

## 6. How good is the model, honestly

**Current, on 4,001 held-out patients at 9.77% prevalence:**

| metric | value | read as |
|---|---|---|
| AUPRC | 0.174 | 1.8× prevalence floor, +11.5% over baseline |
| AUROC | 0.689 | modest; correct to be far from 0.99 |
| Oracle gap | 42% | real signal, large headroom |
| Green-miss | 0.115 | 11.5% of criticals below Yellow |
| Reliability slope | 0.954 | well calibrated |
| Conformal coverage | 0.910 @ 1.08 set size | honest and efficient |
| FNR spread | 0.195 | acceptable, neonate worst |

**The honest verdict: this is a validated pipeline, not a validated model.**

- It is **not fake.** AUROC 0.689 against a 0.988 fake ceiling and a 0.869
  oracle is exactly the signature of a model learning something real and
  incomplete.
- It is **better than the rule card**, but not overwhelmingly: +11.5% AUPRC,
  one significant win over four budgets, three statistical ties.
- It is **weak in absolute terms.** It captures 42% of achievable signal and
  still misses 11.5% of critical patients at the shipped cut. Safety currently
  rests as much on the rules layer (red flags, critical-derangement floor,
  abstention) as on the model.
- **Most of the safety came from thresholds and rules, not the model.** The
  42.2% → 11.5% improvement was threshold design and floors, while AUPRC barely
  moved. Worth remembering before crediting the model for it.

**What it does and does not prove.** A model trained on synthetic data generated
by our own assumptions validates the **pipeline**, not the medicine. The AUROC
measures how well it recovers a latent we defined. It is evidence that training,
calibration, conformal abstention and cost-sensitive thresholding are wired
correctly end to end — nothing more. Any clinical claim needs the real-data
phases (MIMIC-IV-ED for architecture validation, then partner-hospital data).

**Never say:** "the model detects deterioration with 0.69 AUROC" as if that were
a clinical result. **Say:** "on synthetic data whose generative process we
control, the pipeline trains, calibrates and abstains correctly, and beats the
rule-card baseline by 11.5% AUPRC."

---

## 7. If you retrain

1. Regenerate data if the generator or `config/label_spec.yaml` changed —
   ~6 min for 20k, and `beta0` is re-solved for target prevalence.
2. **Print the oracle ceiling before training.**
3. `python -m model.train` then `python -m model.evaluate`.
4. Check all eight gates. If `auroc_in_range` fails high, you have leakage.
5. `python -m pytest -q` — 94 tests.
6. Delete `model/artifacts/` and confirm clean fallback to
   `score_source="fallback_heuristic"`.

**Do not tune a threshold or a hyperparameter to make a gate pass.** Every
constant here has a stated reason; if one needs to change, the reason changes
first. When the model loses to the baseline, that is the finding — report it.

**Regenerable, not in git:** `data/train_set.jsonl` (528 MB) — seed 1337 plus
config fully determines it. Artifacts ARE committed so the fallback path is
exercised against a real artifact.
