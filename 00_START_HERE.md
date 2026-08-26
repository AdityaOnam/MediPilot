# MediPilot Frontend — Start Here

**Team 01 BIT · Accenture Innovation Challenge 2026 · Round 2 · PatientTriage.ai**
Plan authored 2026-08-22. Ignore any earlier implementation plan in this folder.

---

## What these files are

| File | Read it when |
|---|---|
| `00_START_HERE.md` | Now. The decisions that everything else assumes. |
| `FRONTEND_PLAN.md` | Before you write a line of code. Stack, file tree, build order, demo run-of-show. |
| `DESIGN_SYSTEM.md` | While building. Tokens, colour law, motion law, the voice-UI spec. |
| `SCREENS_SPEC.md` | While building each surface. Screen-by-screen states and behaviours. |
| `BACKEND_INTEGRATION_LOG.md` | **Give this to your teammates today.** The API contract + running change log. |
| `CONTENT_PROMPTS.md` | When you sit down at Google Flow / Gemini. Copy-paste prompts with exact attachments. |

Frontend code lives at `C:\Users\HP\Desktop\IITP\Hackathon\temp\medipilot-web`.
Plans and submission material stay here.

---

## The seven decisions everything else rests on

**1. The mascot is patient-side only. It is banned from clinical decision surfaces.**
Your white paper §11 lists "no virtual-nurse persona or avatar, which manufactures false clinical authority" as an anti-decision. The MediPilot character is a *pilot*, not a nurse — it flies the patient through intake, waits with them, and speaks to them. It never appears next to an acuity recommendation, never on the Nurse Bench, never on the Corridor board. Ship this rule visibly and you convert your biggest apparent inconsistency into evidence that you understood your own paper. Say it out loud in the pitch.

**2. Frontend and backend are separated by one file, not by good intentions.**
Every call to a teammate's code goes through `lib/api/` behind a TypeScript interface with two implementations: `mock` (seeded, in-browser, always works) and `http` (their FastAPI). One env var flips it. Consequence: **the demo cannot fail because the backend is late.** Build the entire frontend against `mock` and integrate on day 5.

**3. Build in order of demo value, not architectural layer.**
Corridor board first (it is the money shot and it proves Loop A), then Nurse Bench, then Kiosk + voice. If you run out of time, you run out of time on the least important thing.

**4. Saturated red is a clinical signal, not a brand colour.**
The logo is red. Clinical screens are slate/ink. The only saturated red on a clinical screen is a Red-acuity patient. Brand red is confined to the mascot artwork and to patient-side surfaces.

**5. The frontend enforces the invariants, not just the backend.**
No score renders without a confidence indicator — in dev the component *throws*. No autonomous downward animation exists in the codebase. The LLM structurer view shows a locked, empty "acuity" slot. Your paper's argument is "enforced mechanically, not procedurally discouraged"; make the UI obey the same standard.

**6. Two Round-2 requirements your paper does not yet cover — the frontend is where you add them.**
- *Age-stratified thresholds.* Round 2 names this explicitly ("38.5°C in a 3-year-old versus a 75-year-old"). Every vital renders against its age band.
- *Wait-time-triggered re-assessment.* Round 2 asks for escalation when wait exceeds a safe threshold for that severity, independent of vitals. Loop A currently re-scores on physiology only. Add a depleting safe-wait ring per patient.

**7. Honesty is a design element.**
A persistent `SIMULATED DATA` chip in the chrome. An abstention rate shown, not hidden. A fairness panel that shows the gap. Judges have seen twenty demos that claim perfection; yours claims a trajectory.

---

## What I took from the meeting notes, and what I left

**Taken into the frontend:**
- *"Are you comfortable with your medical info being handled by AI?" → No* → a first-class **Consent** screen with a real **Human Lane**, not a dark pattern. Declining must not cost the patient time.
- *Explicit handling of non-assisted patients* → an "Is someone with you?" question that sets `unaccompanied`, which enlarges type, switches to voice-first, badges the nurse card, and **shortens the safe-wait threshold** — nobody is watching this person deteriorate.
- *Red-flag check / "if delay may cost the life"* → a red-flag **interrupt** that stops intake mid-sentence and alerts the bench, while the patient only ever sees "let's get someone to you now".
- *Intensity, not binary* → a 0–10 pain scale with faces and voice entry, never a yes/no.
- *LLM as interface, not decision-maker* → the Structuring animation: transcript → field chips → and one locked, greyed slot labelled "acuity — not produced by the language model". This single UI element carries your entire architectural argument.
- *Speech-to-text, code-mixed Hindi/English* → real microphone capture with a live language chip and low-confidence words underlined rather than hidden.
- *Preferential weights / reliability of a measurement* → reliability chips on vitals (`measured` / `stated` / `unreliable — cuff size`), which also gives you an honest way to show the SpO₂-bias rule.

**Left out (backend or business-proposal territory, not frontend):**
MIMIC vs synthetic data strategy, the synthetic generation function, the ask to the professor for real data, and the V1→V2→Vs maturity ladder. One exception: the maturity ladder surfaces indirectly as the abstention-rate trajectory on the Trust panel (30% month one → <10% month six), which is already in your paper.
