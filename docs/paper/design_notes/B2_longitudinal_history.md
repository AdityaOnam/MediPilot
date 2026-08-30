# B2 Design Note — Cross-Visit / Longitudinal Patient History

**Status**: Scoping decision required before any generator code is written.
**Author**: Generated per MODEL_EXPANSION_PLAN.md §B2
**Date**: 2026-08-24

---

## What this is and is not

"Patient history" in this project currently means two separate things:

1. **Within-encounter trend** (`slope_per_hour`, `delta_30min`, `vitals_history`
   on `PatientRecord`) — already built, trained on, and **now wired through
   the API as of Track B1**. This is done.

2. **Cross-visit / longitudinal history** — prior ED visits, known chronic
   conditions, repeat-attender flags. This does **not exist anywhere** in the
   generator or the schema. This note scopes that addition.

Do not conflate (1) and (2). They touch different parts of the pipeline.

---

## Open design decisions (require sign-off before writing code)

### Decision 1: What fields does a cross-visit record contain?

Three options, in increasing complexity:

| Option | Fields | Generator change | Leakage risk |
| :--- | :--- | :--- | :--- |
| A | `n_prior_visits`, `last_visit_outcome` (binary) | Small | Low — observable |
| B | A + `known_chronic_conditions` (list of coded conditions) | Medium | Medium — partially overlaps `condition_id` |
| C | A + B + `repeat_attender_flag`, `days_since_last_visit` | Large | High — conditions may directly encode frailty |

**Recommended**: Start with Option A. It is observable, non-circular, and
requires the smallest generator change.

### Decision 2: Does cross-visit history enter the latent model or arrive as an observed feature?

This is the critical decision. The current label spec uses a `frailty` latent
to model chronic disease burden — it is the primary source of outcome risk that
vitals alone cannot predict.

**If cross-visit history is added as an observed feature:**
- If it partially recovers `frailty`, the model gains signal that the label
  spec says is unrecoverable from vitals. This will push AUROC upward.
- The AUROC > 0.95 leakage canary **must be re-run** after this change.
- If the canary triggers, the feature must either be removed or the label spec
  updated to make the frailty genuinely unrecoverable from the new feature.

**If cross-visit history is used to modify the label latent:**
- This changes `config/label_spec.yaml` — the frailty drawn for a patient
  with 3 prior visits for chest pain is higher than for a first-time patient.
- This is a more honest model of reality, but it requires a generator redesign
  and a complete retrain from scratch.

**Recommended**: Add as an **observed feature only**, explicitly document that
it partially proxies `frailty`, re-run the leakage canary, and report the
AUROC change in the leaderboard.

### Decision 3: Multi-encounter patient generation

Currently, `data.generator.bulk` generates **one encounter per patient**.
Multi-encounter patients require:

1. A patient-level identity that persists across encounters.
2. The generator must produce N encounters per patient, with visit outcomes
   from encounter k feeding into the cross-visit features of encounter k+1.
3. The train/test split must be by **patient_id** (already the case for
   within-encounter splits), but for multi-encounter data, all encounters
   of one patient must stay in the same split to prevent outcome leakage.

This is a **generator redesign**, not a config tweak. It is estimated to
require 2–3 days of careful work to implement correctly with the existing
Bernoulli outcome / frailty latent structure.

---

## Proposed new feature fields (Option A)

```yaml
# config/feature_registry.yaml additions
- name: n_prior_visits
  classification: permitted
  reason: "Observable count, not a label proxy. Zero for first-time patients."

- name: last_visit_outcome_critical
  classification: permitted
  reason: "Binary outcome of last visit. Observable retrospectively."
  leakage_note: "Correlates with frailty — must re-run AUROC canary after adding."

- name: days_since_last_visit
  classification: permitted
  reason: "Time-since feature, observable."
```

---

## Proposed generator change (Option A)

In `data/generator/conditions.py`, add a `prior_visits` dict to the generated
patient record:

```python
# Sampled from a Poisson(lambda=1.5) distribution — most patients have 0-3 prior visits.
# Lambda is not conditioned on frailty by design to avoid directly encoding the latent.
n_prior = rng.poisson(1.5)
prior_outcome_prob = 0.10   # unconditional — NOT frailty-weighted
last_critical = rng.binomial(1, prior_outcome_prob) if n_prior > 0 else 0
days_since = rng.integers(1, 365) if n_prior > 0 else None
```

**Note**: `prior_outcome_prob` is deliberately unconditional (not frailty-weighted)
to limit the overlap with the current label latent. If this is too conservative
and we want cross-visit history to genuinely improve performance, it should be
made frailty-weighted — but that makes the leakage concern real, not theoretical.

---

## Verification protocol

After any B2 code is written and a model is trained with the new features:

1. **Re-run the AUROC canary**: `gates["auroc_in_range"]` must remain True.
2. **Report oracle gap change**: If the oracle gap increases significantly,
   the new feature partially recovers the latent.
3. **Run the full leaderboard**: B2-enabled model must appear as its own row,
   with `history_available=Y` and the data provenance documented.

---

## Decision requested

Please answer the following before any generator code is written:

1. **Option A, B, or C** for cross-visit record fields?
2. **Observed feature** or **label latent modification** for the frailty interaction?
3. **Multi-encounter redesign**: proceed now (longer scope) or defer to post-Group-2?
