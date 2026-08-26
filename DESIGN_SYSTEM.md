# MediPilot — Design System

Everything here is derived from the logo at `MediPilot.png` and from the constraints the white paper imposes. Where the two conflict, the paper wins and the logo bends.

> **Corrected 2026-08-22** against the R2 system plan. Changed sections: **§6 Motion** (budget cut from four animations to one), **§7 Voice** (resequenced to last and made droppable), **§8 Clinical components** (two clocks, three explainability channels, freshness contract, Yellow abstention floor). See `FRONTEND_PLAN.md` §1 for the full correction table F1–F17.

---

## 1. The logo, read carefully

A red medical cross rendered as a friendly robot, wearing a brown leather aviator cap with pale-blue goggles, on articulated steel limbs, in a heavy black cartoon outline.

The important word is **pilot**, not doctor. A pilot does not diagnose you. A pilot flies you somewhere, runs the checklist, watches the instruments, and talks to you calmly while doing it. That reading is the entire brand voice, and it happens to be exactly what your architecture does: MediPilot flies the patient through intake and watches the corridor. The nurse remains the physician of record.

**Colours sampled from the file:**

| Token | Hex | Where it came from |
|---|---|---|
| `--mp-red` | `#DF423D` | the cross body |
| `--mp-leather` | `#926A47` | the aviator cap |
| `--mp-glass` | `#C9EBED` | the goggle lenses |
| `--mp-steel` | `#A7C4CC` | the limbs |
| `--mp-steel-dark` | `#7F7E7C` | limb shadow |
| `--mp-ink` | `#1C1B1A` | the outline |

---

## 2. The mascot law

Your white paper, §11 *Anti-decisions*: **"No virtual-nurse persona or avatar, which manufactures false clinical authority."**

This is not a problem with the logo. It is the rule that tells you where the logo goes.

**Permitted — patient-facing surfaces.** `/kiosk`, `/board`, consent screens, the token slip, loading and boot states, error and empty states, the app icon, the pitch deck, the launcher.

**Forbidden — clinical decision surfaces.** `/bench`, `/corridor`, `/charge`, `/audit`. No mascot, no character voice, no cartoon anywhere near an acuity recommendation, a confidence band, or an override.

Enforce it in code, not in memory:

```tsx
// components/mascot/Mascot.tsx
const CLINICAL = ['/bench', '/corridor', '/charge', '/audit'];
if (process.env.NODE_ENV !== 'production' && CLINICAL.some(r => pathname.startsWith(r))) {
  throw new Error('Mascot rendered on a clinical surface. See DESIGN_SYSTEM.md §2.');
}
```

Say this on stage in one sentence: *"The character talks to patients. It is not allowed in the room where acuity is decided — that's a rule in our code, not a preference."* A judge who read your paper is watching for exactly this.

---

## 3. Colour law

**Rule: saturated red is a clinical signal, never a brand decoration.**

The logo is red. If the chrome is also red, a Red-acuity patient stops being visually urgent. So:

- Brand red lives **only inside mascot artwork and patient-side accents**.
- Clinical surfaces are slate and ink. The only saturated red on a clinical screen is a Red-acuity patient.
- No red destructive buttons, no red error toasts, no red badges of any kind on `/bench`, `/corridor`, `/charge`, `/audit`. Errors there use amber-grey with an icon.

### Acuity palette — dark clinical surfaces only

Acuity is never rendered on the kiosk or public board, so it only has to work on dark.

| Level | Text/border | Fill | Glyph | Label |
|---|---|---|---|---|
| Priority 1 | `#FF5A4E` | `#3A1512` | ▲ filled triangle | `RED · P1` |
| Priority 2 | `#FFB020` | `#3A2A08` | ◆ half-filled diamond | `YELLOW · P2` |
| Priority 3 | `#3DD68C` | `#0E2E20` | ● outlined circle | `GREEN · P3` |
| Abstained | `#9B8CFF` | `#1C1836` + 45° hatch | ◇ hollow, dashed | `NEEDS YOUR EYES` |

Four hard rules:

1. **Never colour alone.** Every acuity chip carries colour *and* glyph *and* the word. Print the board in greyscale; if you cannot triage from it, it is broken.
2. **Abstention is not a fourth acuity level.** Different hue family, hatched fill, dashed border, and it never sorts into the Red/Yellow/Green ordering. It sorts to the top of a separate "awaiting your assessment" lane.
3. **Escalation adds motion and a chevron**, never a brighter colour. A card that just escalated shows `▲` for 20 seconds.
4. Contrast floor: 4.5:1 for text, 3:1 for chip borders, against the surface behind them. Check every pair before shipping.

### Surface tokens

```css
:root[data-surface="clinical"] {
  --bg:        #0D1117;   /* the ED at 3am; this is the default clinical theme */
  --bg-raised: #151B23;
  --bg-card:   #1A222C;
  --line:      #263140;
  --text:      #E6EDF3;
  --text-dim:  #8B98A5;
  --focus:     #58A6FF;
}
:root[data-surface="patient"] {
  --bg:        #FBF7F2;   /* warm paper, not hospital white */
  --bg-raised: #FFFFFF;
  --bg-card:   #FFFFFF;
  --line:      #E7DED2;
  --text:      #1C1B1A;
  --text-dim:  #6B6560;
  --accent:    #DF423D;   /* brand red is allowed here */
  --focus:     #926A47;
}
```

Clinical surfaces default to dark because triage benches are dim at night and a white screen at 3am is a physical imposition on the person you are trying to help. Patient surfaces are warm paper because a waiting room is already frightening enough.

---

## 4. Typography

| Role | Face | Notes |
|---|---|---|
| UI | **Inter** | via `next/font`, variable |
| Devanagari | **Noto Sans Devanagari** | required — your intake is code-mixed Hindi–English |
| Vitals and numerals | Inter with `font-variant-numeric: tabular-nums` | **mandatory** |
| Token numbers on `/board` | Inter, 700, wide tracking | readable at 6 metres |

Tabular figures are not a nicety. Loop A re-scores every five minutes; without them, a heart rate ticking 98 → 101 makes the whole row jitter sideways, and jitter on a clinical board reads as instability. Set it globally on any element displaying a measurement.

Scale: 12 / 14 / 16 / 20 / 26 / 34 / 48 / 72. Kiosk starts at 20 and goes up; when `unaccompanied` is set, the kiosk base jumps to 26.

---

## 5. Layout

- Clinical surfaces: 8 px grid, 1440 × 900 as the design target, degrade cleanly to 1024 × 768 (test this — venue projectors are old).
- Kiosk: 9:16 portrait, designed for a tablet on a stand and usable on a phone. One decision per screen. Thumb-reachable controls in the bottom third.
- `/board`: 16:9, no interaction, no scroll, legible at 6 metres, auto-paginates if the queue overflows.
- Corridor has two densities: **comfortable** (default) and **compact** (auto-switches above 18 waiting, which is what surge triggers).

---

## 6. Motion law — corrected, cut back

> **Rewritten 2026-08-22.** The earlier four-animation budget is withdrawn. The R2 system plan (§16) lists *"frontend polish absorbs the schedule"* as a live risk and rules: **the interface must be legible, fast and honest; motion earns its place only where it shows a queue re-ordering, which is the one thing worth animating.** That is an instruction, not a preference.

**The motion budget: one animation.**

| Animation | Spec | Meaning it carries |
|---|---|---|
| **Queue re-ordering** | A card changes position — from an autonomous escalation, a breach escalation, or the R control re-sorting the board. ~500 ms, spring, driven by layout rather than hand-written FLIP. | The movement *is* the information: a queue a human ordered has just re-ordered itself. |

Everything else — state changes, route changes, panel opens, card expansions — is a **120 ms cross-fade at most, or nothing at all**.

**Cut entirely:** the Loop A tick shimmer sweep, the field-extraction fly-in, and the bespoke slow de-escalation choreography.

Human de-escalation is now distinguished by **a required confirm-and-hold and a human badge on the record**, not by a different animation curve. The asymmetry is carried by the interaction cost and by the signed record, which is where it belongs — an animation is a weaker claim than an audit entry.

Rules that survive:
- **Nothing autonomous ever animates downward.** There is no code that can do it.
- No spinners on clinical surfaces. Skeletons with the last known value dimmed, plus a staleness timestamp.
- Respect `prefers-reduced-motion`: the re-order becomes an instant position change. The escalation chime and the up-chevron glyph still fire, because those carry information rather than decoration.
- Mascot media (`boot-goggles.mp4`, `kiosk-attract.mp4`) plays on the **intake idle screen only**. Never during a clinical interaction, never on a clinical surface.


## 7. Voice UI — the specification

> **Resequenced.** The system plan (§15, §16) builds the **typed question tree first and requires it to be complete on its own**; speech is sequenced last with a typed fallback, because ASR on code-mixed Indian speech is a named risk and *the demo must not depend on it*. Voice is build phase **P7 and is droppable without damage**. Everything below describes the voice layer when it lands — it is not the centrepiece of the intake screen, and the intake screen must be fully demoable with voice disabled entirely.

When it does land it should be real: actual `getUserMedia`, actual `AnalyserNode`, actual RMS driving actual pixels. Judges can tell a faked waveform.

### The six states

```
IDLE ──▶ LISTENING ──▶ CAPTURED ──▶ STRUCTURING ──▶ READBACK ──▶ COMMITTED
                │                                        │
                └──── RED-FLAG INTERRUPT ────────────┐   └──▶ CORRECTING ──┘
                                                     ▼
                                              HUMAN ESCALATION
```

### State by state

**IDLE.** Mascot at rest, goggles up. Copy: *"Tap and tell me what's wrong."* No microphone access requested yet — permission is asked at the moment of tapping, with a plain-language reason.

**LISTENING.** Four simultaneous signals, because "your voice is being taken carefully" has to be shown four ways at once:

1. **The cockpit ring** — a radial ring around the mascot on kiosk, a horizontal bar on bench. Driven by real RMS amplitude at 60 fps, smoothed with a 3-frame moving average so it breathes rather than twitches. Goggles come *down* over the mascot's eyes when listening starts. That single gesture communicates "I am now paying attention" better than any label.
2. **The captured trail** — a scrolling waveform of the **last 8 seconds** of audio, drawn left to right. This is the critical one. A live-amplitude blob shows the mic is on; a *trail* shows the system retained what you said. Users who see their own speech accumulate as a physical shape trust the capture.
3. **Signal quality** — a three-state chip: `too quiet, come closer` / `background noise — I'm still getting it` / `clear`. Never blocks; only guides.
4. **Language chip** — flips live between `EN`, `हिं`, and `EN + हिं` as code-mixing is detected. This is a small element that quietly says *we designed for how Indians actually speak.*

Plus an unmistakable recording state: a solid dot, the word "listening", and a Stop control that is always reachable without scrolling.

**CAPTURED.** The trail freezes and settles. Partial transcript resolves to final. **Low-confidence words are underlined with a dotted line, never hidden and never silently corrected.** Tapping an underlined word offers alternatives. Hiding uncertainty in the transcript is the same sin as hiding it in the score.

**STRUCTURING — the most important screen in your entire prototype.**

The transcript sits at the top. Below it, the structured schema fills in as chips fly from the transcript into their slots: `age`, `chief complaint`, `onset`, `pain 0–10`, `SpO₂`, `HR`, `BP`, `temp`.

And then, at the bottom of that form, a slot that is greyed, locked, and permanently empty:

```
┌──────────────────────────────────────────────┐
│  🔒  acuity                                   │
│      not produced by the language model       │
│      no production rule exists in the output  │
│      grammar — see architecture, layer L1     │
└──────────────────────────────────────────────┘
```

That component is `LockedAcuitySlot.tsx`. It is perhaps forty lines of code and it carries the whole architectural argument of your paper. Every other team's demo will show an LLM producing a triage level. Yours shows an LLM that *structurally cannot*. Put it on screen for a full three seconds during the pitch and say the sentence from the run-of-show.

**READBACK.** MediPilot speaks the captured fields aloud; each field highlights as it is spoken; a caption track shows the same text for anyone who cannot hear it. Two controls: *that's right* and *fix something*. **Nothing commits until this is confirmed** — that is straight from your paper's L1 description and it is a genuinely good workflow detail, so make the "not yet committed" state visible (dashed borders on every field until confirmed).

**CORRECTING.** Tap any field, correct by voice or keypad. Corrected fields keep a small `edited` marker permanently — the audit log records who changed what.

**RED-FLAG INTERRUPT.** If a red-flag phrase lands mid-intake (`lib/clinical/redFlags.ts`), intake stops immediately:
- the ring turns steady, not pulsing; the mascot shifts to its calm-serious pose (no alarm, no flashing);
- the screen reads *"Let's get someone to you right now."*;
- the bench receives an immediate alert;
- **the patient never sees the word RED or any acuity level.** Your paper forbids speaking acuity within patient earshot, and the screen is within earshot too.

This is a five-second moment in the demo that will land harder than any dashboard.

### Voice out

`speechSynthesis` for the prototype — free, offline, zero keys, immune to venue Wi-Fi. Pick a warm mid-pitch voice, rate 0.95. Note in the deck that production uses an Indic TTS with a Hindi voice, and that the voice is deliberately *not* a nurse persona: it announces and confirms, it never advises.

Fixed vocabulary rules for anything MediPilot says:
- Never says an acuity level. Ever. Not on the kiosk, not on the board, not through the hall speaker.
- Never says "you have" or "you might have". It has no diagnostic vocabulary.
- Says token numbers, confirmations, next steps, and reassurance. That is the whole list.

### Sound

Three sounds, all under 400 ms, all soft:
- **escalation chime** on the clinical surface — a rising two-note interval, deliberately not an alarm; alarms cause fatigue and your paper cares about that;
- **capture confirm** on the kiosk — a single soft tick;
- **commit** — a low, brief settle.

Nothing else makes noise. There is a global mute in Demo Control for a quiet judging room.

---

## 8. Clinical component rules — corrected

### AcuityCard — three channels, not one

Corrected per §12 of the system plan. The card shows **three channels**; channels 2 and 3 live behind a tap so the whole thing is absorbable in seconds by someone already managing several patients.

**Leading position — red flags.** If the red-flag pass fired (§10), the flag sits at the very top as the leading factor, with the observation that triggered it. A red-flag Red is **not system-overridable downward** by any later model output; only a clinician can move it, with a reason. Nobody should be left wondering why a patient with unremarkable vitals went to the front.

**Channel 1 — what drove this.** The two strongest contributing factors with direction and magnitude, plus **one factor arguing the other way**. The opposing factor is mandatory and is labelled as an argument against — a falsification target, which is the practical defence against nodding along. If the model has no opposing factor, that is an abstention, not an empty list.

**Channel 2 — what was considered and did not move it.** Normal and weakly-contributing parameters, so the nurse does not assume every available number was decisive. **This is where an applied reliability discount is named** (§7 of the system plan) — by name, so a clinician can see and reject the reasoning. That is also how we detect it going wrong.

**Channel 3 — what was said, and what happened since.** The narrative contribution — the phrases extracted and what they triggered — kept **separate** from the timeline of band changes, alarms, stale readings, missed rechecks and overrides. Narrative evidence is the least familiar input a nurse will meet, so it gets its own space rather than being folded into a feature list.

Every card also carries the confidence indicator and, where relevant, **why** confidence is low: missing field, stale reading, inferred age stratum, disagreeing sensors, or a patient unlike the local distribution.

```tsx
if (!score.confidence || !score.conformalSet || !score.inputsUsed) {
  throw new Error('Refusing to render a score without a confidence indicator.');
}
```

Keep that throw. The submission gate requires uncertainty enforced *at the output contract, not by UI convention*. If a judge asks how you know, show them the throw.

### CadenceStrip — replaces SafeWaitRing

The single wait ring is gone. Every queue card carries **three time facts** (§8 of the system plan):

```
  re-scored 40s ago        thin, quiet, ambient
  re-measure in 12 min     primary
  ceiling in 28 min        the one that turns
```

The ceiling is independent of physiology — time in queue alone forces action. On breach the card shows the breach kind: `REMEASURE_MISSED`, `CEILING_EXCEEDED`, or `UNMET_REVIEW`. A Yellow whose forced re-measurement is not completed within 15 minutes escalates to Red **on time alone**, and the card says so in those words.

### RecheckTask — a recheck has an owner

Every recheck names who owes it and how much its result is trusted:

| Owner | Trust | May close |
|---|---|---|
| Recheck station | full | any band |
| Nurse / attendant | full | any band |
| Accompanying family | partial | Green only — raises a flag on Yellow/Red, never satisfies it |
| Patient self-report | signal only | nothing — can escalate, never closes a recheck, never de-escalates |

Render trust visually, not just as a word: a full-trust reading and a family-reported one must not look identical on a board being read at speed.

### VitalChip — stratum, then value, then freshness

Three things, in this order, because the order is the argument:

```
  Temp  38.5 °C   [high for child 1–12y]   station · fresh
  Temp  38.5 °C   [high for geriatric]     station · fresh     <- same number, different meaning
  SpO2  96%       [normal for adult]       device  · fresh     de-escalation authority: none
  HR    —         last read 3h ago                             EXPIRED — rendered as missing
```

- **Stratum first.** No band comparison renders without a resolved stratum (Invariant 3). Unknown age shows `stratum: inferred (widest-safety)` and pins confidence down permanently — an inferred stratum never silently resolves.
- **Freshness is part of the value** (Invariant 4). Past 2× the band's cadence the reading is visibly discounted; past 3× the chip renders **missing**, not a stale number. Showing an expired number as if it were current is the failure this contract exists to prevent.
- **Reliability is asymmetric.** A normal SpO₂ carries `de-escalation authority: none` under the pulse-oximeter bias rule. The chip says the measurement carries no *downward* authority — exactly what the paper claims, and no more.

### The stoic-presentation flag

A one-tap nurse control, set when a patient's manner and their physiology disagree. Clinician-set, never model-guessed. It applies a named reliability discount that lowers the weight of *reassuring* self-report only — it can never make an alarming report count for less.

### AbstentionCard — and the Yellow floor

Replaces the AcuityCard entirely. Hatched border, `NEEDS YOUR EYES`, no number anywhere, and a stated reason: conformal set too wide, out of distribution, or critical fields missing.

**There is no Green code path in this component** (Invariant 5). An abstained patient holds at a **Yellow floor**. Past 15 minutes unreviewed they leave the queue and enter a breach list as an unmet-review breach — not left sitting quietly in a queue nobody is looking at.

### OverrideDialog — and the 16-field record

Structured reason code plus required free text. Show the nurse **exactly what will be written** before they confirm; nobody signs a record they have not seen. A downward override requires confirm-and-hold.

The resulting record has sixteen fields (§13) and `/audit` renders it **verbatim** — no summarising, no prettifying. `factorsShown` must be the card as displayed, because that is what establishes what the clinician was actually told.

### Consent must never be rendered as risk

A patient who declines to share history is triaged on vitals and observation. They may get a wider conformal set and therefore a more cautious band — which under Invariant 1 means **more attention, not less**. The card must **not** display the refusal as a risk factor, and no surface may present declining as a reason for a worse queue position.

## 9. Accessibility and dignity

These are product requirements, not compliance chores, and two of them come straight from your paper.

- **No acuity is ever displayed or spoken where a patient can see or hear it.** The hall board shows token numbers only. This constrains `/board` completely and it is a design *feature* — mention it.
- **Unaccompanied mode**: base type 26 px, voice-first, longer timeouts, no step that requires two hands.
- Full keyboard operation on clinical surfaces; visible focus rings; the nurse should be able to accept a card without touching the mouse.
- Every acuity legible in greyscale (glyph + word).
- All caption tracks for spoken output.
- `aria-live="polite"` for the transcript, `aria-live="assertive"` for escalations.
- Never use the word "patient" as an identifier on shared displays. Token numbers.

---

## 10. Tone of voice

**MediPilot to patients:** short, warm, concrete, never medical. *"You're in the queue. Token 214. Someone will call your number. If anything feels worse, press this."* Never "don't worry".

**System to nurses:** terse, factual, no adjectives, no exclamation marks, no encouragement. *"Re-scored 14:32. Yellow → Red. RR 28, rising. SpO₂ 91%, falling."*

**The product to judges:** claims that are bounded. Every number on the trust panel carries its denominator and its source. "Simulated" is written on the screen, not buried in the appendix.

---

## 11. Persistent chrome

Present on every surface, top-right, small, never dismissible:

`SIMULATED DATA` · model version · Loop A ring · connection state

Honesty as a design element. You are demoing a medical device to people who have watched a lot of demos claim more than they can support. The chip costs you nothing and buys you the benefit of the doubt on everything else.
