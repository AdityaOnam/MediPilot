# MediPilot model — fix plan

Handoff document. Self-contained: you do not need the review conversation that
produced it. Work in `D:\medipilot-whitepaper\backend`.

Baseline state: 62/62 tests pass, ~5,400 LOC, all modules present. The code is
broadly sound — Invariant 1 (asymmetric autonomy), reliability asymmetry, and
the audit-log schema were all verified correct and **must not be regressed**.

Six defects below, in priority order. F1 and F2 are blocking: they break the
project's headline demo. Run `python -m pytest -q` after each fix.

---

## F1 — Febrile child scores Green (BLOCKING)

### Symptom

A 3-year-old at 38.5 °C with age-appropriate vitals scores **green**, while a
75-year-old with the same temperature scores **yellow**:

```
CHILD 3y      -> green   conf=0.05   for:['temp_c_high (σ=2.0)']
GERIATRIC 75y -> yellow  conf=0.39   for:['temp_c_high (σ=1.3)']
```

The child's temperature is *more* deviant for its stratum (σ=2.0 vs σ=1.3) yet
scores lower. The brief requires the paediatric fever case to escalate; Green is
the forbidden direction.

Reproduce with:

```bash
python -c "import sys; sys.path.insert(0,'.'); from tests.test_corpus_cases import NOW, NOW_ISO; from model.risk_model import score_patient, PatientRecord; mk=lambda p,a,h,r,t: PatientRecord(patient_id=p,age_days=a,hr=(h,NOW_ISO,'recheck_station','valid'),rr=(r,NOW_ISO,'recheck_station','valid'),bp_sys=(100,NOW_ISO,'recheck_station','valid'),spo2=(96,NOW_ISO,'recheck_station','valid'),temp_c=(t,NOW_ISO,'recheck_station','valid'),gcs=(15,NOW_ISO,'recheck_station','valid'),pain_score=(3,NOW_ISO,'recheck_station','valid')); [print(n,score_patient(m,now=NOW).as_dict()['band']) for n,m in (('child',mk('C',365*3+90,120,26,38.5)),('geri',mk('G',365*75,82,18,38.5)))]"
```

### Root cause

`model/calibration.py`, in `StratumCalibrator.calibrate()`:

```python
if cal_weight > 1.4 and n_abnormal_vitals > 0:
    calibrated = max(calibrated, 0.36)
```

That magic number gates the vulnerable-stratum floor. Current weights in
`config/age_strata.yaml`:

| stratum | calibration_weight | floor applies? |
|---|---|---|
| neonate | 1.80 | yes |
| infant | 1.50 | yes |
| geriatric | 1.60 | yes |
| **child** | **1.30** | **no — falls through** |
| adolescent | 1.00 | no |
| adult | 1.00 | no |

`child` sits just under the threshold, so a febrile toddler gets no floor and
the reassurance reduction pulls it to Green.

### Fix

Do **not** just bump the child weight to 1.5 — that silently changes every
child score and re-tunes the model to dodge one test. Replace the implicit
magic number with an explicit per-stratum config field.

1. In `config/age_strata.yaml`, add to **every** stratum block:

   ```yaml
   abnormal_vital_floor: 0.36   # min calibrated score when any vital is abnormal
   ```

   Set `0.36` (Yellow floor) for `neonate`, `infant`, `child`, `geriatric`.
   Set `null` for `adolescent` and `adult` (no floor — reference strata).

   Add a comment stating this encodes "a child compensates well then
   decompensates abruptly, so an abnormal vital is never dismissible", which is
   the clinical reason child needs the floor even at a lower weight.

2. In `calibration.py`, replace the magic-number gate with:

   ```python
   floor = s.get("abnormal_vital_floor")
   if floor is not None and n_abnormal_vitals > 0:
       calibrated = max(calibrated, float(floor))
   ```

3. Surface it on `CalibrationResult` (add an `abnormal_vital_floor_applied: bool`
   field) so the explanation layer can name it.

### Acceptance

- Child at 38.5 °C with age-appropriate vitals → **yellow or red**, never green.
- Adult at 38.5 °C, otherwise normal → **unchanged from today** (no floor).
- Verify you have not shifted the adult baseline: `P-20` (adult benign illness,
  Green baseline) must still score Green.

---

## F2 — "Different reasoning" is false, and the test is rigged (BLOCKING)

### Symptom

`factors_against` is character-for-character identical across strata:

```
CHILD 3y      against:['hr_normal','rr_normal']
GERIATRIC 75y against:['hr_normal','rr_normal']
```

The entire geriatric claim is that a normal HR alongside fever is *weak
reassurance* in that stratum. Here it is presented as a factor against
escalation with equal footing in both. The nurse card would show the same
explanation for two patients the system is treating differently — the
explanation channel is misreporting the actual reasoning.

### Root cause (two parts)

**Part A — factors are stratum-blind.** In `model/risk_model.py`,
`_raw_risk_score()` (~line 227) builds the strings from a bare threshold
comparison:

```python
factors_against.append(f"{tr.vital}_normal")
```

`reassurance_decay` (geriatric 0.25 vs child 0.65 vs adult 0.85) is applied
later, to the *score*, in `calibration.py` — and never reaches the factor
strings. So the score is stratum-aware; the explanation is not.

**Part B — the test does not test the claim.**
`tests/test_corpus_cases.py::test_p03_geriatric_fever_also_escalates_different_reasoning`
compares a geriatric patient at **38.5 °C, HR 82** against a child at
**39.5 °C, HR 180, RR 45**. That is a critically ill toddler versus a mildly
febrile pensioner — a different temperature and different vitals, so it proves
nothing about stratification. It then computes:

```python
geriatric_factors_against = " ".join(d_geriatric.get("factors_against", []))
child_factors_against = " ".join(d_child.get("factors_against", []))
```

…and **never asserts on either variable**. The only real assertion is
`d_geriatric["age_stratum"] != d_child["age_stratum"]`, which is trivially true.
Dead variables sitting where the missing check should be.

### Fix

1. **Make factor strings carry reassurance strength.** In `_raw_risk_score()`,
   pass the stratum (or its `reassurance_decay`) in, and label accordingly —
   e.g. below ~0.4 decay emit `hr_normal (weak reassurance — geriatric)`,
   otherwise `hr_normal`. Keep the machine-readable vital name as a stable
   prefix so the frontend can still parse it; the qualifier is a suffix.

2. Consider returning factors as small dicts
   (`{"vital": "hr", "state": "normal", "reassurance": "weak"}`) and rendering
   the display string at the edge. If you do this, **update the §7 output
   contract in `README.md` and every consumer**, because Track B (frontend)
   reads `factors_for` / `factors_against` as strings today. If that ripple is
   too wide, keep strings and just append the qualifier.

3. **Rewrite the test to actually test the claim.** Same temperature (38.5 °C)
   for both, each with vitals that are unremarkable *for their own stratum*
   (child HR ~120 / RR ~26; geriatric HR ~82 / RR ~18). Assert:
   - both escalate (neither is Green);
   - `factors_against` differs between the two — specifically, the geriatric
     patient's normal-HR entry is marked weak-reassurance and the child's is not
     marked the same way;
   - delete the two dead variables, or assert on them.

4. Write the test **first** and watch it fail before applying fix 1, so you know
   it is really exercising the behaviour.

### Acceptance

Same temperature, both escalate, and the two `factors_against` lists are
provably different in a way a human reading the card would notice.

---

## F3 — Invariant 5 bypassable by construction

`AbstentionObject(patient_id='X', band='green')` constructs successfully. The
Yellow floor is a dataclass **default**, not a guard, so any caller can produce
an abstained-Green patient — the exact state Invariant 5 forbids.

**Fix.** Add `__post_init__` to `AbstentionObject` in `model/risk_model.py`:
raise `ValueError` if `band == "green"` or `abstained is not True`. Add a test
asserting the constructor raises. Apply the same treatment to `ScoreObject` if
any path there can emit `abstained=True` with a green band.

---

## F4 — Surge safety guards are config-toggleable

In `backend/surge_controller.py` all three guards are gated on config
membership:

```python
if "raise_cost_ratio_R" in self._forbidden and proposed_R > current_R:
    raise SurgeViolation(...)
```

`self._forbidden` is read from `config/surge_policy.yaml`. Deleting a line from
that YAML silently disables a safety check and **no test fails**.

**Fix.** The guards must always run. Config may tune thresholds; it must not
decide whether a safety invariant is enforced. Remove the
`if "..." in self._forbidden` condition from all three guards. Keep the YAML
list if you want it as documentation, but assert at load time that it contains
all three expected entries and raise on startup if not. Add a test that removes
an entry from a temp config and asserts the guard **still** fires.

---

## F5 — Corpus IDs disagree with the other two tracks

The generated corpus renumbered the acceptance cases relative to the briefs the
speech/LLM and frontend tracks are building against:

| Case | Brief said | Corpus has |
|---|---|---|
| Age pair (same temp, opposite reasoning) | P-03 / P-04 | **P-02 / P-03** |
| Deteriorates while waiting (hero demo) | P-05 | **P-01** |
| Ambiguous epigastric pain | P-07 | **P-04** |
| Dark skin / SpO₂ 96% | P-08 | **P-05** |
| Stale vitals 3 h | P-09 | **P-06** |
| Zero history | P-11 | **P-07** |
| OOD abstention | P-15 | **P-08** |
| Nurse override → full record | P-14 | **P-09** |
| Missed rechecks under surge | P-20 | **P-10** |

Left alone, the frontend wires its demo to the wrong patients.

**Fix.** Do not renumber unilaterally — this is a cross-track contract. Add a
`case_id` field alongside `patient_id` in `data/corpus_20.json` carrying a
stable semantic name (`age_pair_paediatric`, `age_pair_geriatric`,
`deteriorates_while_waiting`, `ood_abstention`, …), and have the other two
tracks key off `case_id` rather than the numeric ID. Publish the mapping table
above in `README.md` so all three tracks can reconcile. Flag to the team before
changing any existing ID.

---

## F6 — Assertion hygiene sweep

F2 revealed a pattern worth checking for elsewhere: a test whose docstring
claims more than its assertions check. Sweep `tests/` for

- computed-then-unused locals (as in F2),
- assertions that are tautologies (`x != y` where the two can never be equal),
- `assert x in ("red", "yellow")` where the case name implies exactly one.

Tighten each to assert the specific claimed behaviour. Report anything where
the tightened assertion **fails** — that is a real defect this suite was hiding,
and it should be fixed rather than loosened back.

---

## Guardrails

- Do **not** regress: `band_engine.AsymmetricAutonomyViolation` (Invariant 1),
  the reliability asymmetry in `model/reliability.py` (alarming answers must
  keep full weight and never be discounted), or the 15-field hash-chained audit
  record in `backend/audit_log.py`. All three were verified correct.
- Do not tune magic numbers to make a specific test pass. If a threshold needs
  to change, move it into `config/` with a comment stating the clinical reason.
- Re-run the full suite after each fix; report any test that changes status,
  including ones that start passing for reasons you did not intend.
- After F1 and F2, re-run the reproduce command in F1 and paste the actual
  output as evidence, rather than asserting it now works.
