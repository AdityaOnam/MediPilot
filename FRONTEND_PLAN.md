# MediPilot — Frontend Implementation Plan (R2, corrected)

**Owner:** Aditya Gupta · **Code root:** `./frontend/`
**Corrected against:** *MediPilot — Round 2 Implementation Plan* (R2 draft 1), the authoritative system plan. Where this document and that one disagree, that one wins.
**Companion docs:** `DESIGN_SYSTEM.md`, `SCREENS_SPEC.md`, `frontend/BACKEND_INTEGRATION_LOG.md`, `frontend/IMPLEMENTATION_LOG.md`, `CONTENT_PROMPTS.md`

---

## 1. What the system plan corrected in this plan

The previous revision was written before the R2 system plan existed. Seventeen things were wrong or missing. Listed rather than silently patched, because several change what gets built and in what order.

| # | Was (earlier frontend plan) | Now | Source |
|---|---|---|---|
| **F1** | One Loop A clock, 5 min, everyone. One `SafeWaitRing` per card. | **Two clocks plus a ceiling.** Re-score is band-specific (Red 60 s, others 5 min); re-measure is band-specific (Red 5 / Yellow 30 / Green 60); wait ceiling is a third, independent number (Red 0 / Yellow 60 / Green 120 / Abstained 15). Every queue card carries **three time facts**, not one. | D1, §8 |
| **F2** | Pediatric/geriatric as a *badge*. | **Six strata**, resolved before any threshold is applied. Vitals render against the resolved stratum. Unknown age → widest-safety stratum, marked `inferred`, permanently reducing confidence. | D2, §6, Inv 3 |
| **F3** | Recheck was a task with a deadline. | Recheck has an **owner and a trust level**. Station/nurse = full trust; family = partial, cannot close Yellow/Red; patient self-report = signal only, never satisfies a recheck. | D3, §8 |
| **F4** | Consent screen, then voice intake. | **Four-step intake branch in fixed order**: is anyone with you → *would you prefer a person* → consent to use medical information → proceed. The human offer comes **before** the machine proceeds alone, not after it fails. | D4, §9 |
| **F5** | Red-flag was a kiosk interrupt. | Red-flag pass also **owns the top of the nurse card** as the leading factor, and a red-flag Red is **not system-overridable downward** by any later model output. | D5, §10 |
| **F6** | `reliability` chip on vitals, four values. | Reliability is **asymmetric and named**. It lowers the weight of *reassuring* self-report only, never alarming. Every applied discount appears **by name** on the card. New control: nurse's one-tap **stoic-presentation flag**. | D6, §7 |
| **F7** | `/charge` with mass-casualty behind auth. | **Mass casualty is not built** (§15). Surge is a separate, ordinary mode the system enters on its own, and the UI shows the **forbidden relaxations** explicitly. | D7, §11, §15 |
| **F8** | Confidence required on every score. | Unchanged — already correct. Enforced at the output contract, not by UI convention. | D8, Inv 2 |
| **F9** | Override dialog with a structured reason. | Override record has a **16-field legal schema** tied to the Indian jurisdiction, rendered **verbatim** for P-14. | D9, §13 |
| **F10** | Voice was the P3 centrepiece; typing "always available". | **Typed question tree is built first and must be complete on its own.** Voice is sequenced last so the demo survives ASR not landing. Talk-first is the product goal, not the build order. | D12, §15, §16 |
| **F11** | Motion budget of four named animations. | **Cut.** The system plan names frontend polish as a schedule risk and rules: *motion earns its place only where it shows a queue re-ordering*. One animation survives. | §16 |
| **F12** | — (absent) | **The live R control.** A judge-facing panel where moving the cost ratio R visibly moves the threshold and re-sorts the board with the same patients on screen. A self-imposed submission-gate item, and a frontend feature. | §02 |
| **F13** | My own census (P-001…P-020, invented names). | **Replaced entirely** by the authoritative corpus P-01…P-20 from §14. Each record exists to make one behaviour visible; do not invent new ones. | §14 |
| **F14** | Vitals had a value and a reliability. | Vitals are a **tuple of value, timestamp, source, validity**. Older than 2× band cadence → discounted; older than 3× → **rendered as missing**. Freshness is visible, not implicit. | Inv 4 |
| **F15** | Abstention was a separate lane. | Also: an abstained patient **holds at a Yellow floor, never Green**, and an unreviewed abstention past 15 min is an **unmet-review breach**, not a queue item. | Inv 5, §8 |
| **F16** | `LoopAEngine` ran client-side as source of truth. | The **scheduler and simulated clock are backend-owned** (§15). The client engine survives only inside the mock adapter, mirroring a backend contract. | §15 |
| **F17** | Kiosk consent had an ambient-sensing toggle. | **Removed.** Ambient sensing is described-not-built. Consenting to something that does not exist is the kind of detail a judge catches. | §15 |

**F1, F10, F11 and F13 change the build.** The rest are additive or subtractive detail.

---

## 2. Frontend scope, fixed by §15

The system plan draws a hard line between *built and demonstrated* and *described, not built*. The frontend half of that line:

**Built here**
- Nurse card (three explainability channels) and nurse board
- Override capture path and audit-record rendering
- Patient intake flow — typed question tree first, voice last
- Judge-facing control panel: **R**, surge rate, simulation speed
- Two-clock display: re-score age, re-measure deadline, wait ceiling, breach state
- Age stratification rendering across all six strata
- Uncertainty, conformal sets, abstention gate display
- Red-flag pass display
- Surge at 3×, including the refusals

**Not built, and we say so**
Mass-casualty mode · ambient sensing UI · live ABHA retrieval · real HIS/FHIR screens · federated-learning views · multi-site calibration views.

Saying this out loud is a strength (§15). Do not build a screen for anything in the right column, and do not let one appear by accident in the deck.

---

## 3. The six invariants, as frontend enforcement

Each invariant maps to a test that fails the build, not to a review checklist.

| Invariant | Frontend enforcement |
|---|---|
| **1 · Asymmetric autonomy** | No autonomous downward code path exists. `grep -ri "deescalat\|downgrade" lib/` returns hits only inside the human override handler. Downward motion in the UI happens only as the consequence of a human action. |
| **2 · No naked scores** | `<AcuityCard>` throws in dev if `confidence` or the input set is absent. A score object failing schema validation is not renderable. |
| **3 · Age is never assumed** | `VitalChip` refuses to render a band comparison without a resolved stratum. Unknown age renders `stratum: inferred (widest-safety)` on the card face and pins confidence down. |
| **4 · Freshness is part of the value** | `Measurement` is `{value, takenAt, source, validity}`. Staleness class computed against that band's cadence. Past 3× → the chip renders **missing**, not a stale number. |
| **5 · Abstention is loud, never Green** | `AbstentionCard` has no Green code path. Abstained patients sort at the Yellow floor. Past 15 min unreviewed they leave the queue and enter a **breach** list. |
| **6 · The human closes every loop** | Override is one touch from every surface where a band is shown. No screen exists where a recommendation cannot be overridden. |

---

## 4. Two clocks — the largest single correction

This is the thing to get right, because it is the difference between "we re-score every five minutes" — which the Round 1 paper said, and which is cheap and slightly glib — and a defensible resource model.

- **Re-scoring** is the model running again over existing data. Milliseconds. Never rationed.
- **Re-measurement** is a human physically taking fresh vitals. The scarcest thing in the department. Rationed by band.
- **Wait ceiling** is a third, independent trigger: time in queue alone forces action regardless of whether any number moved.

| Band | Re-score | Re-measure | Ceiling | On breach |
|---|---|---|---|---|
| Red | 60 s | 5 min | 0 min | Any Red still queued at 5 min pages the senior clinician and flags the board |
| Yellow | 5 min | 30 min | 60 min | Forced re-measurement task; not completed in 15 min → escalates to Red on time alone |
| Green | 5 min | 60 min | 120 min | Forced re-measurement + wellbeing contact; two consecutive misses → Yellow |
| Abstained | 5 min | on review | 15 min | Unmet-review breach; holds at Yellow floor |

**UI consequence:** `SafeWaitRing` is replaced by `<CadenceStrip>` — re-score age (thin, quiet), re-measure deadline (primary), wait ceiling (the one that turns). Staleness visibly decays the confidence indicator as a reading ages, which is the mechanism by which a patient surfaces for re-measurement on evidence rather than on a bare timer.

---

## 5. The R control — a graded item

§02 commits to demonstrating escalation bias *live*: move R, watch the threshold and the board change, same patients re-sorting in front of the judges. A claim in the deck does not satisfy the brief's requirement to demonstrate this explicitly in the prototype.

So this is a real feature, not a debug toggle:

- A slider for **R** (miss-to-false-alarm cost ratio), reading out `p* = 1/(1+R)` live.
- Two anchor presets: **R = 500** (tertiary, `p* ≈ 0.002`) and **R = 100** (district, `p* ≈ 0.010`).
- The board re-sorts as R moves — same patients, visible transition. The one place animation unambiguously earns its place.
- A counter showing what moved: *"3 patients crossed the threshold. 0 moved down — de-escalation is not available to the optimiser."*

That last line is the point. Raising R escalates more people; lowering R does **not** de-escalate anyone below a human-assigned band, because Invariant 1 binds the threshold rather than the reverse. Judges watch the asymmetry happen instead of being told about it.

---

## 6. Motion — cut back

The system plan lists *"frontend polish absorbs the schedule"* as a live risk and rules: **the interface must be legible, fast and honest; motion earns its place only where it shows a queue re-ordering.**

The earlier four-animation budget is withdrawn. What survives:

1. **Queue re-ordering** — a card changing position, whether from an autonomous escalation or from the R control re-sorting the board. ~500 ms, spring, layout-driven. The movement *is* the information.
2. Everything else — state changes, route changes, panel opens — is a ≤120 ms cross-fade, or nothing.

Cut entirely: the tick shimmer sweep, the field-extraction fly-in, the bespoke slow de-escalation choreography. Human de-escalation is now distinguished by **a required confirm-and-hold and a human badge on the record**, not by an animation.

Mascot media is already produced and stays — on patient surfaces, and still. The boot/attract videos play on the intake idle screen, not during clinical interaction.

---

## 7. Surfaces

| Route | Surface | Theme | Mascot |
|---|---|---|---|
| `/board` | Nurse board — the queue, three time facts per card, breaches | Dark | No |
| `/card/[id]` | The nurse card — three explainability channels, accept/override | Dark | No |
| `/intake` | Patient intake — four-step branch, typed tree, voice last | Light | Yes |
| `/control` | Judge-facing panel — **R**, surge rate, simulation speed, scenario jump | Dark | No |
| `/audit` | Override records rendered verbatim, ledger, model/calibration versions | Dark | No |
| `/hall` | Public waiting display — token numbers only | Light | Yes, ambient |

Dropped from the earlier plan: `/charge` (its only distinct content was mass casualty, not built) and `/corridor` as a route separate from `/board` (they were the same screen).

`/control` is no longer a hidden debug panel — it is a demonstrated deliverable, because R is a graded item.

---

## 8. Separation from the backend

Unchanged in principle, corrected in ownership. Everything crosses one boundary:

```
lib/api/
  types.ts              <- the contract, shared verbatim with the backend
  client.ts             <- export const api: MediPilotApi
  adapters/mock.ts      <- seeded, runs the whole demo offline
  adapters/http.ts      <- the backend service
  contract.test.ts      <- runs against BOTH adapters
```

`NEXT_PUBLIC_MP_SOURCE=mock | live`, default `mock`.

**Corrected (F16):** the scheduler and simulated clock are **backend-owned** (§15: "a single service holding the pipeline, scheduler and audit log. Simulated clock so a 3-hour ED shift demos in three minutes."). The mock adapter reimplements them client-side only so the demo runs without the service. The frontend never treats its own clock as authoritative when `live`.

Endpoint-by-endpoint and module-by-module map: `frontend/BACKEND_INTEGRATION_LOG.md`.

---

## 9. Build order — corrected

Reordered by F10 (typed before voice) and F12 (R control is graded, not optional).

**P0 · Foundations.** Scaffold, tokens, `types.ts`, mock adapter, the P-01…P-20 corpus from §14. *Exit: corpus loads, six routes resolve.*

**P1 · Board + two clocks.** `QueueCard`, `CadenceStrip`, band chips, breach states, freshness decay. *Exit: a Yellow breaches its ceiling and escalates on time alone, with no vital having changed.*

**P2 · The card.** Three explainability channels, conformal set, abstention with Yellow floor, red-flag as leading factor. *Exit: P-07 renders ambiguous, P-15 abstains out loud.*

**P3 · Override + audit.** Capture path, 16-field record rendered verbatim. *Exit: P-14 override produces the full record on screen.*

**P4 · The R control.** Slider, live `p*`, board re-sort, the "0 moved down" counter. *Exit: judges can move R and watch it.*

**P5 · Intake, typed.** Four-step branch, age-aware question tree, consent gate, red-flag pass over structured output. **Complete on its own.** *Exit: P-17 declines consent and is triaged without penalty; P-18 red-flags on narrative with unremarkable vitals.*

**P6 · Surge.** 3× rate, board density switch, ranked alert feed, forbidden-relaxations display. *Exit: P-20 breaches under load.*

**P7 · Voice.** Speech layered onto the completed typed tree. **Droppable without damage.**

**P8 · Rehearsal.** The §15 demo narrative, three times, timed.

---

## 10. Demo narrative — from §15, replacing the earlier run-of-show

One patient, then the system around them.

1. **P-05** arrives with mild chest discomfort, correctly assigned Yellow. *The nurse did nothing wrong.*
2. Eighteen minutes later, with the nurse registering three new arrivals, **the queue re-orders itself** and P-05 moves to the front — reasoning visible, one factor arguing against.
3. **P-03 and P-04** side by side: both 38.5 °C, a 3-year-old and a 75-year-old, sorted differently. A single adult model would have got one wrong and looked confident doing it.
4. **The R control**: move it, watch the board re-sort, watch nobody move down.
5. **3× load**: what stretches, what holds, and what the system refuses to do to cope.
6. **P-14**: a nurse overrides, and exactly what that leaves behind in the record.

---

## 11. Risks the system plan names for the frontend

| Risk | Response |
|---|---|
| Frontend polish absorbs the schedule | §6 above. One animation. Legible, fast, honest. |
| Speech integration slips | P7, last, droppable. The typed tree is complete on its own. |
| Demo breadth beats demo depth | §2 scope table is a commitment. Nothing from the right column gets a screen. |
| Backend not ready | Mock adapter is the default. Integration is a bonus. |

---

## 12. Definition of done

- [ ] Every §02 submission-gate row demonstrable without touching code
- [ ] All six invariants have a failing test if violated
- [ ] Three time facts on every queue card; breach escalation works on time alone
- [ ] Override renders all 16 fields verbatim
- [ ] R control re-sorts the board live, and reports zero downward moves
- [ ] Typed intake complete and demoable with voice entirely disabled
- [ ] Nothing on screen from the described-not-built column
- [ ] `frontend/IMPLEMENTATION_LOG.md` current
