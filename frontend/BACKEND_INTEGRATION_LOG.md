# MediPilot — Backend ↔ Frontend Integration Log

**For:** Aditya Onam, Varada Patel (backend / model)
**From:** Aditya Gupta (frontend)
**Status:** contract **v0.2** — corrected against the R2 system plan. Frozen unless a change is logged in §1.

This is the only document you need in order to plug into the frontend. §2 tells you which backend module feeds which screen. §4 is the wire format. You are done when §8 is green.

---

## 1. Change log

Newest at the top. Every contract change gets a row, or the frontend breaks silently.

| Date | Ver | Change | By |
|---|---|---|---|
| 2026-08-22 | v0.2 | Corrected against R2 system plan. **Two clocks** replace the single 5-min cadence; six age strata; measurement tuple with validity; 16-field override record; abstention holds a Yellow floor; R exposed as a live control; scheduler and simulated clock confirmed backend-owned. | Gupta |
| 2026-08-22 | v0.1 | Initial contract. Nine endpoints, one SSE stream, five invariants. | Gupta |

---

## 2. Module → screen map

This is the section you asked for: which backend part lands on which frontend part. Module numbers are from §05 of the system plan.

| Backend module | Feeds | Frontend consumer | Via |
|---|---|---|---|
| **M01** Data ingestion | vitals, roster, bed feeds | `<VitalChip>`, routing hints on `/board` | `GET /v1/encounter/{id}` |
| **M02** Validation & freshness | staleness class per field | `<VitalChip>` staleness state; confidence decay | `validity` on each measurement |
| **M03** Intake branch | assisted / consent / human-offer state | `/intake` steps 1–3; `assistedState` badge on the card | `POST /v1/intake/branch` |
| **M04** Question tree | next question, age-aware branching | `/intake` typed tree | `POST /v1/intake/next` |
| **M05** Speech & multilingual | transcript, language | `/intake` voice layer (**P7, droppable**) | `POST /v1/structure` |
| **M06** LLM structurer | structured fields, **never a band** | `/intake` review step | `POST /v1/structure` |
| **M07** Red-flag pass | fired flags + mapped observation | **top of** `<AcuityCard>` as leading factor | `redFlags[]` on score |
| **M08** Age stratification | resolved stratum, `inferred` flag | `<VitalChip>` bands; `<StratumBadge>` | `ageStratum` on encounter |
| **M09** Reliability weighting | named discounts | `<AcuityCard>` **Channel 2**, by name | `reliabilityDiscounts[]` |
| **M10** Risk model | probability, factors | `<AcuityCard>` Channel 1 | `POST /v1/score` |
| **M11** Hospital calibration | site + stratum calibration version | `/audit` model card; override record | `calibrationVersion` |
| **M12** Uncertainty / OOD | conformal set, abstention | `<ConfidenceBand>`, `<AbstentionCard>` | `conformalSet`, `abstained` |
| **M13** Emergency rule engine | vital-threshold + sensor-loss rules | `<AcuityCard>` rule factors; P-10 sensor-loss state | `ruleFires[]` |
| **M14** Band engine | band **+ the recheck contract** | `<BandChip>`, `<CadenceStrip>` | `band`, `cadence` |
| **M15** Recheck router | task, **owner**, deadline, breach | `<CadenceStrip>`, `<RecheckTask>`, breach list | `GET /v1/rechecks` |
| **M16** Surge controller | surge state, stretched cadences, refusals | `/board` density switch, surge banner | `GET /v1/surge` |
| **M17** Explainability | three channels | `<AcuityCard>` channels 1–3 | `explanation` on score |
| **M20** Audit log | override records | `/audit`, verbatim | `GET /v1/audit` |
| **M21** Synthetic generator | the P-01…P-20 corpus | seed data for `mock`; census for `live` | `GET /v1/census` |
| **M22** Controlled update | model version | `/audit` model card | `modelVersion` |

**M18** (nurse interface) and **M19** (patient interface) are the frontend. They are built here, not consumed.

**Not integrated, because not built:** mass-casualty mode, ambient sensing, live ABHA retrieval, real HIS/FHIR, federated learning, multi-site calibration. Do not send fields for these; the frontend has nowhere to put them.

---

## 3. Six invariants the API must uphold

The frontend enforces these — it throws loudly in development when a response violates one. Better you see the error than a judge does.

**I-1 · Never recommend below the human-assigned band.**
`POST /v1/score` may never return a band lower than `humanAssignedBand`. If the model believes lower, return the **same** band with `suggestsReview: true` and a reason. There is no frontend code path that lowers a band autonomously; a lower value is discarded and flagged.

**I-2 · No naked scores.**
Every non-abstained score carries `confidence`, `conformalSet`, and `inputsUsed`. Missing any → not renderable.

**I-3 · Age is never assumed.**
Every encounter carries `ageStratum`. Where age is unknown, send the widest-safety stratum with `ageStratumInferred: true` — never omit the field and never silently pick adult.

**I-4 · Freshness is part of the value.**
Every measurement is `{value, takenAt, source, validity}`. Never send a bare number. `validity` is computed against that band's cadence: `fresh` / `discounted` (> 2× cadence) / `expired` (> 3× cadence). The frontend renders `expired` as **missing**, not as a stale number.

**I-5 · Abstention is loud, and never Green.**
An abstained encounter has `abstained: true`, a reason, and `effectiveBand: "YELLOW"` — the floor. Never send `GREEN` alongside `abstained: true`. Past 15 minutes unreviewed, set `unmetReviewBreach: true`.

**I-6 · The structurer never emits a band.**
`POST /v1/structure` returns a schema with **no band or acuity key at all** — not null, absent. If the key is present the frontend rejects the whole response. The LLM reports what was said; the fixed table decides what it means.

Plus: every mutating call returns an `auditId`; every response carries `serverTime` **and** `simTime` (see §5).

---

## 4. Core types

```ts
export type Band = 'RED' | 'YELLOW' | 'GREEN';
export type AgeStratum = 'neonate' | 'infant' | 'child' | 'adolescent' | 'adult' | 'geriatric';
export type Validity = 'fresh' | 'discounted' | 'expired';
export type MeasurementSource = 'station' | 'nurse' | 'attendant' | 'family' | 'patient' | 'device';

export interface Measurement {            // I-4 — never a bare number
  code: 'HR'|'SBP'|'DBP'|'RR'|'SPO2'|'TEMP'|'GCS'|'RBS'|'PAIN';
  value: number | null;
  unit: string;
  takenAt: string;                        // ISO-8601 UTC
  source: MeasurementSource;
  validity: Validity;
  bandForStratum?: 'below'|'low'|'normal'|'high'|'above';
  deEscalationAuthority?: boolean;        // false for SpO2 under the pulse-ox bias rule
}

export interface Cadence {                // §8 — the two clocks plus the ceiling
  rescoreSec: number;                     // RED 60, others 300
  remeasureSec: number;                   // RED 300, YELLOW 1800, GREEN 3600
  ceilingSec: number;                     // RED 0, YELLOW 3600, GREEN 7200, abstained 900
  nextRescoreAt: string;
  nextRemeasureAt: string;
  ceilingBreachesAt: string;
  breached: boolean;
  breachKind?: 'REMEASURE_MISSED' | 'CEILING_EXCEEDED' | 'UNMET_REVIEW';
}

export interface RecheckTask {            // D3 — a recheck has an owner
  encounterId: string;
  owner: 'station' | 'nurse' | 'attendant' | 'family' | 'patient';
  trust: 'full' | 'partial' | 'signal-only';   // family=partial, patient=signal-only
  dueAt: string;
  canCloseBands: Band[];                  // family/patient may not close YELLOW or RED
}

export interface ReliabilityDiscount {    // §7 — asymmetric, and named on the card
  factor: 'geriatric-stratum' | 'communication-barrier' | 'health-literacy'
        | 'stoic-flag' | 'non-assisted' | 'analgesia-given';
  appliesTo: 'reassuring-only';           // never 'alarming'. This field is a constant.
  label: string;                          // shown verbatim in Channel 2
}

export interface ScoreResponse {
  encounterId: string;
  serverTime: string;
  simTime: string;

  abstained: boolean;
  abstentionReason?: 'CONFORMAL_SET_TOO_WIDE'|'OUT_OF_DISTRIBUTION'|'MISSING_CRITICAL_FIELDS';
  effectiveBand: Band;                    // I-5 — YELLOW floor when abstained, never GREEN

  band?: Band;
  probability?: number;
  conformalSet?: Band[];
  confidence?: 'high' | 'moderate' | 'low';
  confidenceReducedBy?: ('missing-field'|'stale-reading'|'inferred-stratum'
                        |'sensor-disagreement'|'out-of-distribution')[];

  redFlags?: { observation: string; mapsTo: 'RED'; lockedDownward: true }[];  // §10
  explanation?: {
    channel1: { label: string; direction: 'supports'|'opposes'; magnitude: number }[];
    channel2: { considered: string[]; discounts: ReliabilityDiscount[] };
    channel3: { narrative: { phrase: string; triggered: string }[]; timeline: TimelineEvent[] };
  };

  suggestsReview?: boolean;               // I-1
  thresholdUsed: number;                  // p* = 1/(1+R)
  costRatioR: number;
  modelVersion: string;
  calibrationVersion: string;
  auditId: string;
}
```

### The override record — all 16 fields (§13)

Rendered verbatim on `/audit` for P-14. Send every field; the frontend does not compute any of them.

`patientId` · `timestampUtc` · `clinicianId` · `clinicianRole` · `systemBand` · `clinicianBand` · `direction` · `reasonCode` · `reasonText` · `score` · `confidence` · `factorsShown` · `inputsHash` · `modelVersion` · `calibrationVersion` · `consentState` · `outcomeRef` *(back-filled)*

`factorsShown` must be **the card as displayed**, not a recomputation — it establishes what the clinician was actually told.

---

## 5. Endpoints

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/v1/config` | Cadence table, age-stratum definitions, R and its bounds, surge policy |
| `GET` | `/v1/census` | All waiting encounters with band, cadence, confidence |
| `GET` | `/v1/encounter/{id}` | Full detail, measurements, explanation |
| `POST` | `/v1/intake/branch` | M03 — assisted, human-offer, consent |
| `POST` | `/v1/intake/next` | M04 — next question, stratum-aware |
| `POST` | `/v1/structure` | M06 — transcript → fields. **No band key** (I-6) |
| `POST` | `/v1/score` | M10/M12/M14 — the score |
| `GET` | `/v1/rechecks` | M15 — open tasks, owners, breaches |
| `POST` | `/v1/decision` | Accept or override; returns the full 16-field record |
| `GET` | `/v1/surge` | M16 — state, stretched cadences, refusals |
| `GET` | `/v1/audit` | M20 — records, hash-chained |
| **`POST`** | **`/v1/control/r`** | **Set R. Returns new `p*` and the re-sorted census.** Drives the graded R control |
| `POST` | `/v1/control/clock` | Simulation speed. Backend owns the clock (§15) |
| `GET` | `/v1/stream` | SSE — see below |

### The clock

§15 puts the **simulated clock in the backend**: "a 3-hour ED shift demos in three minutes." So:

- Every response carries **both** `serverTime` (real) and `simTime` (simulated).
- All cadence deadlines are expressed in `simTime`.
- The frontend renders against `simTime` and never advances it locally when running `live`.
- `POST /v1/control/clock {speed}` is the only thing that changes it.

### SSE

```
event: rescore      {"encounterId":"P-05","band":"YELLOW","simTime":"..."}
event: escalation   {"encounterId":"P-05","from":"YELLOW","to":"RED","cause":"MODEL","auditId":"..."}
event: breach       {"encounterId":"P-20","kind":"CEILING_EXCEEDED","bandChanged":true}
event: recheckDue   {"encounterId":"P-09","owner":"station"}
event: surge        {"active":true,"multiplier":3}
```

**There is no de-escalation event.** Downward movement reaches the frontend only as a `decision` with `actor:"human"` and a reason. Wanting to emit an autonomous downgrade is the bug, not the feature.

Emit `rescore` even when nothing changed — a silent stream makes the board look dead.

---

## 6. The R control

`POST /v1/control/r { "R": 100 }` → returns `p*`, the re-sorted census, and a movement summary:

```json
{ "R": 100, "pStar": 0.0099,
  "moved": { "up": 3, "down": 0 },
  "note": "de-escalation is not available to the optimiser" }
```

`moved.down` must be **structurally zero**. Lowering R raises the threshold, so fewer patients cross it — but nobody moves below their human-assigned band, because I-1 binds the threshold rather than the reverse. If your implementation can ever produce a non-zero `down`, that is the invariant leaking and it must be fixed in the engine, not clamped in the response.

---

## 7. Scope we are NOT asking you to build

Real ASR (send us a transcript; voice is P7 and droppable), federated learning, FHIR/CDS Hooks, auth beyond a stub, persistence beyond process lifetime, mass-casualty mode, ambient sensing.

**A deterministic rule-based scorer that satisfies this contract is entirely acceptable** (§15 permits synthetic throughout, and §16 wants the demo to survive the model slipping). Get the contract right first; swap the brain in later. Tell us which it is, so the pitch describes it accurately — we do not claim a trained model while demoing rules.

---

## 8. Definition of done

```bash
npm run test:contract -- --target=http
```

Already green against `mock`, so it is a fair target with no surprises:

- [x] `/v1/structure` has no band/acuity key (I-6)
- [x] `/v1/score` never returns below `humanAssignedBand` (I-1)
- [x] Every non-abstained score has `confidence`, `conformalSet`, `inputsUsed` (I-2)
- [x] Every encounter has `ageStratum`; unknown age sets `ageStratumInferred` (I-3)
- [x] Every measurement is a full tuple with `validity` (I-4)
- [x] `abstained: true` always pairs with `effectiveBand: "YELLOW"` (I-5)
- [x] Cadence carries all three clocks and a breach kind
- [x] `/v1/decision` returns all 16 override fields
- [x] `/v1/control/r` returns `moved.down === 0` at every R in range
- [x] Both `serverTime` and `simTime` on every response
- [x] SSE emits `rescore` with zero changes, and never an autonomous de-escalation
- [x] Audit rows chain: `row[n].prevHash === row[n-1].hash`

---

## 9. Open questions — RESOLVED

Answered inline, 2026-08-27.

1. **`snake_case` on the wire?** ✅ **Resolved: camelCase, orchestrator-side.** The Python orchestrator (`backend/orchestrator/dto.py`) emits camelCase natively using Pydantic `model_config = {"alias_generator": to_camel, "populate_by_name": True}`. No mapping layer in TypeScript. The `live.ts` adapter is a thin `fetch` + `EventSource` wrapper with zero field translation. Verified: contract tests pass with raw JSON from the orchestrator matching `lib/api/types.ts` one-for-one.

2. **Who owns the P-01…P-20 corpus?** ✅ **Resolved: joined on `case_id`.** `backend/orchestrator/seed.py` contains a `CASE_MAP` that joins 13 backend cases (keyed by descriptive `case_id` like `deteriorates_while_waiting`, `ood_abstention`) to frontend encounter IDs (P-01…P-20). Backend supplies trajectory data, vitals, strata, red flags, reliability flags. Frontend `lib/seed/corpus.ts` supplies presentation metadata (token, displayName, sex, chiefComplaint, arrivalMode, consent flags). The 7 unjoined frontend records (P-01, P-10, P-12, P-16, P-17, P-19, surplus) get synthesised flat trajectories from their static measurements. Neither corpus was renumbered.

3. **Do you compute `validity` and cadence deadlines, or shall I?** ✅ **Resolved: backend computes, frontend renders.** The orchestrator's `world.py` computes measurement validity (`fresh`/`discounted`/`expired`) against each band's cadence table from `config/band_cadence.yaml`, and computes all three cadence deadlines (`nextRescoreAt`, `nextRemeasureAt`, `ceilingBreachesAt`) in sim time. The frontend renders `expired` measurements as MISSING and displays the deadlines as countdown timers. Verified: contract test `test_measurements_have_validity` and `test_cadence_has_three_clocks` both pass.

4. **Real scorer or deterministic rules for the demo?** ✅ **Resolved: trained GBDT with rule floors — and the pitch says exactly that.** The orchestrator calls `score_patient_verbose()` which runs the real trained `medipilot-gbdt-v0.2.0` model with per-stratum isotonic calibration and Mondrian conformal prediction. Three safety floors operate on top: (1) red-flag short-circuit to RED, (2) Invariant 1 escalate-only via `max(model_band, floor)`, (3) abstention YELLOW floor (I-5). This is a genuine hybrid — trained model + deterministic safety rules — and the submission describes it accurately.

5. **Simulated clock** — ✅ **Resolved: backend owns it, frontend drives it only through `/v1/control/clock`.** The orchestrator's `clock.py` implements `sim_now() = sim_base + (real_now - sim_epoch) * speed`, exactly matching the mock adapter's semantics. `set_speed()` freezes and re-anchors. Every `now=` passed to `score_patient_verbose`, `assign_band`, `scheduler.tick`, and `audit_log.record_override` is sim time. Every response carries both `serverTime` (real) and `simTime` (simulated). The frontend never advances the clock locally when running in `live` mode. Verified: contract test `test_score_has_both_times` passes.

