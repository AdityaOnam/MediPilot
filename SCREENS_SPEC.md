# MediPilot — Screen Specification

Six surfaces. For each: purpose, layout, every state, and what it proves to a judge.

> **Corrected 2026-08-22 against the R2 system plan.** Routes were renamed and one was deleted. The section headings below still carry the old names; read them through this table.
>
> | Old (below) | Now | Note |
> |---|---|---|
> | `/kiosk` | **`/intake`** | Four-step branch in fixed order; ambient-consent toggle removed (not built) |
> | `/bench` | **`/card/[id]`** | Card now has **three** explainability channels, not one |
> | `/corridor` | **`/board`** | Same screen as the old `/bench` list — merged. `SafeWaitRing` → `<CadenceStrip>`, three time facts |
> | `/charge` | **deleted** | Its only distinct content was mass casualty, which is described-not-built (§15) |
> | `/board` | **`/hall`** | Public display, unchanged in behaviour |
> | Demo Control | **`/control`** | Promoted from hidden debug panel to a **graded deliverable** — it hosts the live **R** control (§02) |
>
> See `FRONTEND_PLAN.md` §1 for the full correction table F1–F17, and §7 for the current route list.

> All patient data in this document is **synthetic**, invented for demonstration. Vital values are chosen to exercise UI states, not to encode clinical guidance. Thresholds shown are site-configurable and labelled as such in the UI.

---

## 0. The demonstration corpus — P-01 … P-20

> **Corrected 2026-08-22.** The earlier invented census (P-001…P-020) is **deleted**. This is the authoritative corpus from §14 of the R2 system plan. Each record exists to make exactly one behaviour visible. **Do not invent new records** — if a behaviour needs demonstrating, it already has a record here.

Lives in `lib/seed/corpus.ts`. Deterministic and seeded, so every rehearsal is identical. All data is **synthetic**; nothing here is clinical guidance.

| ID | Presentation | Demonstrates |
|---|---|---|
| P-01 | Adult, crushing chest pain, diaphoretic | Red at the door. Red-flag pass fires **before** the model returns |
| P-02 | Adult, minor laceration, stable | Green that stays Green. The negative control |
| P-03 | 3-year-old, 38.5 °C, tachypnoeic, poor feeding | Age stratification — paediatric |
| P-04 | 75-year-old, 38.5 °C, unremarkable HR | Age stratification — geriatric. **Same number, different meaning** |
| P-05 | Adult, mild chest discomfort, Yellow at arrival | **The hero case.** Deteriorates while waiting; escalates autonomously at minute 18 |
| P-06 | Elderly, confusion, afebrile, no localising signs | Atypical sepsis presentation. Phenotype upweighting |
| P-07 | Adult, epigastric pain — gastritis or inferior MI | **Required:** ambiguous presentation |
| P-08 | Adult, dark skin tone, SpO₂ reads 96 %, distressed | Pulse-oximeter bias. Normal reading carries **no de-escalation authority** |
| P-09 | Adult, last vitals 3 hours old | Freshness contract. Same numbers, decayed confidence, recheck raised |
| P-10 | Adult, cardiac monitor drops out mid-wait | Sensor-loss rule fires **independently of the model** |
| P-11 | Adult, first visit, no record, no ABHA link | **Required:** zero-history patient |
| P-12 | Adult, rich prior history via ABHA | The other half of the 50/50 split. History embedding contributes |
| P-13 | Adult, speaks neither Hindi nor English | Multilingual tree; communication barrier lowers reassurance weight |
| P-14 | Adult, Yellow, nurse finds rigid abdomen | **Required:** clinician override, full 16-field record rendered |
| P-15 | Patient unlike any in the local distribution | OOD gate. Abstains out loud; holds at **Yellow, never Green** |
| P-16 | Unaccompanied, non-responsive, age unknown | Inferred stratum; non-assisted branch; widest-safety configuration |
| P-17 | Adult who declines to share medical history | Consent gate. Triaged on observation alone, **without penalty** |
| P-18 | Woman in active labour | Red-flag on **narrative alone**. Vitals unremarkable |
| P-19 | Stoic patient, denies pain, vitals disagree | Reliability weighting. Reassuring self-report loses weight; alarming physiology does not |
| P-20 | Green patient, two rechecks missed under load | **Wait-ceiling breach** escalates on time alone. Feeds the surge scenario |

The 3× surge run replays this corpus at triple arrival rate with filler patients, so judges watch the **same familiar cases** behave differently under load.

### Which records satisfy which submission gate

| Gate (§02) | Record |
|---|---|
| 15–20 simulated records | All 20 |
| Ambiguous presentation | P-07 |
| Pediatric **and** geriatric | P-03 and P-04, side by side |
| Zero-history first-time patient | P-11 |
| 3× surge behaviour | Full corpus + fillers, driven from `/control` |
| Never a score without confidence | Enforced in `<AcuityCard>`; visible on every record |
| Clinician override with the log shown | P-14 |
| **Escalation bias demonstrated live** | The R control on `/control`, re-sorting all 20 |

## 1. `/` — Launcher

Six tiles, one per surface, each with a one-line description and a device hint (*open this one on a phone*). Mascot present, waving. `SIMULATED DATA` chip visible.

Purpose is practical: on demo day you are opening three surfaces on three devices under time pressure. Do not make yourself type URLs. Add a QR code per tile so you can point a phone at the projector and land on `/kiosk` in two seconds.

---

## 2. `/kiosk` — Patient intake

Portrait. Warm paper theme. Mascot present throughout. One decision per screen.

### K1 · Welcome
Mascot idle, goggles up. `नमस्ते / Hello`. Two large buttons: **हिंदी** · **English**. A third, quieter: *I need help using this*.

### K2 · Is someone with you?
`Yes, someone is with me` · `I'm here alone`.

Choosing alone sets `unaccompanied: true`, which does four things: base type up to 26 px, voice-first mode on, longer timeouts, and — the one that matters clinically — a **shorter safe-wait threshold** on the corridor, because nobody is sitting beside this person to notice them deteriorate. Badge it on the nurse card.

This screen exists because of the meeting note *"explicit handling of non-assisted patients"*. It is thirty seconds of work and it is a genuinely good idea. Point at it.

### K3 · Consent — the Human Lane
Plain language, no legalese, three separate toggles, each with a one-line "what this means":

1. **Let MediPilot listen and fill in the form for you.**
2. **Let MediPilot use your health record to help the nurse.** *(separate from 1 — this is the DPDP §6(1) purpose-specific consent your paper argues ABDM does not by itself cover)*
3. **Ambient sensing in the waiting area.** *(signage-equivalent; declinable)*

If (1) is declined:

> **The Human Lane.** Screen reads *"No problem. A person will take your details."* Token issued immediately. `aiConsent: false` flows to the bench, where the card is replaced by a manual AIIMS-ATP entry form. **The patient's queue position is not penalised, and the screen says so.**

Show this in the pitch. Most teams' consent screen is a checkbox that blocks progress. Yours is a fork with a real second path — the meeting note *"are you comfortable with your medical info…? → No"* answered properly.

### K4 · Voice intake
The centrepiece. Full spec in `DESIGN_SYSTEM.md` §7.

Mascot centre with goggles **down** (listening). Cockpit ring driven by real microphone RMS. Scrolling 8-second captured trail beneath. Signal-quality chip. Language chip flipping `EN` / `हिं` / `EN + हिं`. Live transcript with low-confidence words dotted-underlined.

Typing is always available and equally prominent. Voice is a convenience, never a requirement.

### K5 · Pain
0–10, three redundant encodings: a slider, six faces, and a voice option (*"about a seven"*). From the meeting note on intensity — pain is never captured as yes/no.

### K6 · Readback
MediPilot speaks the captured fields; each highlights as spoken; every field is dashed-bordered because nothing is committed yet. `That's right` · `Fix something`.

### K7 · Token issued
Large token number. Mascot reassuring. *"Token 214. Watch the board. If anything feels worse, press this."* A large, permanent **I feel worse** button — a patient-initiated escalation channel that raises attention on the corridor. Cheap to build, and it means the patient is a sensor too.

### K-INT · Red-flag interrupt
Fires from K4 at any moment. Ring steadies, mascot shifts to calm-serious, screen reads *"Let's get someone to you right now."* Bench alerted. **No acuity word appears anywhere.** No flashing, no alarm — a frightened person in a waiting hall does not need a siren.

---

## 3. `/bench` — Nurse bench

Dark clinical. **No mascot.** Two-column: left, the encounter; right, the card.

### B1 · Encounter list
Incoming arrivals, newest first. Badges: `zero history`, `unaccompanied`, `human lane`, `red-flag`, `pediatric`, `geriatric`.

### B2 · Voice-assisted capture
Same engine as the kiosk, different chrome: horizontal `WaveTrail` instead of the radial ring, no mascot, denser type. The nurse speaks the vitals while working; the form fills; the readback confirms before commit.

The `LockedAcuitySlot` appears here too, at the foot of the structured form. On this surface it reads as a promise to the clinician: *the machine that heard you is not the machine that scored you.*

### B3 · The one card

```
┌───────────────────────────────────────────────────────┐
│  ▲ RED · P1                        re-scored 14:32:05 │
│                                                       │
│  ARGUES FOR                                           │
│  ▸ RR 28 and rising over 3 readings   (trend head)    │
│  ▸ SpO₂ 91% on room air               (T1 vitals)     │
│                                                       │
│  ARGUES AGAINST                                       │
│  ▹ Afebrile, no tachycardia           (T1 vitals)     │
│                                                       │
│  CONFIDENCE   { RED , YELLOW }                        │
│  the true level is in this set 9 times in 10          │
│                                                       │
│  [ Accept ]              [ Override… ]                │
└───────────────────────────────────────────────────────┘
```

Every factor cites which model head produced it. The opposing factor is mandatory and is labelled as an argument against — a falsification target, per your paper's automation-bias reasoning.

### B4 · Abstention state
Replaces B3 entirely. Hatched violet border, `NEEDS YOUR EYES`, no number anywhere on screen, and a stated reason: *conformal set too wide* / *unlike anything in local data* / *critical fields missing*. Offers the frozen ATP rule card as a manual aid. **P-014 Meera Nair** is your scripted abstention.

### B5 · Override dialog
Structured reason plus required note. Shows the exact ledger entry before confirming. If the override is **downward**, an extra confirm-and-hold, and the card animates down slowly with a human badge — motion #4.

### B6 · Human Lane
For `aiConsent: false` (P-016 Deepa Iyer): the card is replaced by a manual ATP entry form. Header reads *"AI processing declined by patient — manual triage."* Loop A still monitors vitals if that consent was given separately, and the UI states which consents are active.

### B7 · Degraded
Model down → `FallbackATPCard`, the frozen AIIMS-ATP red-flag checklist. Network down → a banner reading *"Bench box — local inference, store and forward."* **Never a blank state, never a spinner.**

---

## 4. `/corridor` — Loop A, the money screen

Dark clinical. **No mascot.** This is what stays on the projector for four minutes, so it has to be beautiful and it has to be legible from the back of the room.

### Header
Loop A ring (5-minute cycle, `DEMO ×60` chip when compressed) · waiting count · longest wait · abstention count · `SIMULATED DATA` · model version · connection state.

### Body — three lanes

| Lane | Contents | Sort |
|---|---|---|
| **Needs your eyes** | Abstentions and red-flag interrupts | Newest first |
| **Waiting** | Everyone with an acuity | Red → Yellow → Green, then by wait |
| **In treatment** | Removed from Loop A | — |

### QueueCard
Token, age band, one-line complaint, acuity chip (colour + glyph + word), safe-wait ring, up to three vital sparklines with tabular numerals, badges (`unaccompanied`, `zero history`, `human lane`), and time since last re-score.

### The tick
Every cycle: the ring completes, a shimmer sweeps the list with an 80 ms stagger, and each card's "re-scored" timestamp updates. Even when nothing changes, the board visibly breathes. **That is the product** — a judge watching a calm board still sees continuous observation, which is exactly the thing a static queue cannot do.

### Escalation
`P-007` Yellow → Red at tick 1. Card rises with a 600 ms spring, ghost trail in the vacated slot, chip cross-fade, `▲` for 20 seconds, one soft chime, toast: *"P-007 escalated Yellow → Red. RR rising, SpO₂ falling."* Toast is dismissible but the `▲` is not.

### Safe-wait breach
`P-009`'s ring depletes to zero. A re-assessment task appears in the Needs-your-eyes lane. **The acuity chip does not change** — and the toast says so explicitly: *"Re-assessment due on wait time. Acuity unchanged."* Getting this right is a small thing that shows you understand your own invariant.

### Surge
Above 18 waiting the board auto-switches to compact rows and a banner appears:

> **Surge mode · 3× arrivals.** Department load reaches the routing layer only. Risk scores are unchanged. `[what this means]`

The link opens a small panel showing that census, boarding count and staffing are inputs to L4 and are excluded from L2–L3. This is your paper's §4.1 claim rendered as a UI element a judge can click.

---

## 5. `/charge` — Charge nurse

Dark clinical. **No mascot.**

Department load, bed and bay state, staff on shift, acuity mix over time, mean wait per level, left-without-being-seen counter, abstention rate this shift.

**Mass-casualty mode** sits behind an authentication gate and displays, in plain text, what switching does: the objective changes from individual expected value to resource-constrained population benefit. Your paper says the system never concludes on its own that a mass-casualty event exists — so the UI makes the human declaration explicit, named, and logged. Do not skip the auth screen; it is the point.

---

## 6. `/audit` — Ledger and trust

Dark clinical. **No mascot.** This is the screen that answers the sceptical judge, so build it even though it is the least glamorous.

### A1 · The ledger
Append-only, hash-chained, visibly so. Each row: timestamp, encounter, recommendation, human action, reason, outcome, `prev_hash → hash`. Filters: overrides only, downward overrides only, abstentions, red-flags. Export as JSON.

During the demo you override on `/bench` and the row appears here live. Do that in front of them.

### A2 · Trust panel
- **Under-triage rate at a fixed over-triage rate** — the primary metric, stated as primary, with accuracy and AUROC deliberately absent and a one-line note saying why (1–3 % prevalence).
- **Calibration**: reliability diagram, ECE with the `< 0.05` go-live line drawn on it.
- **Abstention trajectory**: ~30 % month one → < 10 % month six, plotted, labelled *published, not hidden*.
- **Fairness**: false-negative rate by age band, sex, language, payer, skin tone, arrival mode — with the gap shown, not smoothed. A footnote states the choice of equalised FNR over demographic parity and why.
- **Leakage lint**: `PASS · 0 prohibited features · last run <timestamp>`, with the sample `medipilot-lint` output from §9.1 of your paper viewable in a drawer.
- **Model card**: version, training window, external-validation status for this site, shadow-mode days elapsed, ACP/PCCP change status.

Every number carries its denominator and a `simulated` tag. Nothing here should be defensible only until someone asks a second question.

---

## 7. `/board` — Public waiting hall

Light, calm, 16:9, no interaction. Mascot present and ambient.

**Token numbers only.** No names, no acuity, no colour coding that could be decoded by a waiting family, no queue positions that let people infer who is sicker. Now serving, recently called, and an estimated wait band that is deliberately coarse.

A one-line footer states that ambient sensing is active — the signage requirement from your paper, rendered where it actually belongs.

State this constraint out loud in the pitch. *"There is a whole screen here whose main design requirement is what it refuses to display."*

---

## 8. Demo Control — your remote

Backtick key, floating, available on every surface, hidden from screenshots.

| Control | Effect |
|---|---|
| Advance tick | Fires Loop A immediately |
| Tick speed | 5 min / 30 s / 5 s |
| Inject arrival | Adds a patient from the reserve six |
| **Surge ×3** | Injects six at once, flips compact mode |
| Escalate P-007 | Forces the hero escalation on cue |
| Kill network | Degraded banner, local inference |
| Kill model | `FallbackATPCard` everywhere |
| Scripted voice | Replays a recorded waveform and transcript — **your mic-failure insurance** |
| Mute | All sound off |
| Reset | Back to the seeded start state |

Reset must be reliable and instant. You will rehearse this twenty times.
