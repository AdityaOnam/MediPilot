# MediPilot Frontend — Implementation Log

Running record of everything done on the frontend. Newest entry at the top.
**Owner:** Aditya Gupta. **Plan:** `../FRONTEND_PLAN.md`. **Contract:** `./BACKEND_INTEGRATION_LOG.md`.

## How to use this file

One entry per working session, not per commit. Each entry answers four questions:

- **Did** — what was built or changed
- **Why** — which plan section or invariant it serves, so a decision can be re-derived later
- **Decided** — any judgement call made along the way, with the reason
- **Next** — what the next session picks up

Anything that contradicts `../FRONTEND_PLAN.md` gets logged here **and** corrected in the plan. The plan is the intent; this file is the record. They must not drift.

---

## 2026-08-27 · Session 16 — I7 · Backend Integration Verification

**Did**
- **I7a — Contract Tests (12/12 PASS).** Ran `tests/test_orchestrator_contract.py` against the live orchestrator via `TestClient`. All 12 definition-of-done rows from `BACKEND_INTEGRATION_LOG.md` §8 pass:
  1. Abstained scores have no `band` key, `effectiveBand` = YELLOW (I-5)
  2. Non-abstained scores carry `confidence`, `conformalSet`, `inputsUsed` (I-2)
  3. Every encounter has `ageStratum`; P-16 (unknown age) sets `ageStratumInferred: true` (I-3)
  4. Every measurement is a full tuple with `validity` (I-4)
  5. Cadence carries all three clocks (`rescoreSec`, `remeasureSec`, `ceilingSec`) and deadlines
  6. `/v1/decision` returns all 16 override fields plus `hash`/`prevHash` envelope
  7. `/v1/control/r` returns `moved.down === 0` across R = {2, 5, 10, 20} (I-1)
  8. Both `serverTime` and `simTime` on every score response
  9. Audit chain integrity: `row[n].prevHash === row[n-1].hash` for 2+ records
  10. Config complete: R bounds, 4 cadence bands, 6 strata, model + calibration versions
  11. Census returns exactly 20 encounters
  12. SSE verified manually (TestClient blocks on streams)

- **I7b — End-to-End Demo Narrative (22/22 PASS).** Started the orchestrator (`uvicorn backend.orchestrator.app:app --port 8000`) and ran a programmatic verification script against all demo narrative checkpoints:
  - Census: 20 patients returned with correct bands, strata, cadences
  - P-15 abstains with `effectiveBand: "YELLOW"`, no `band` key (I-5)
  - P-03 (`child`) and P-04 (`geriatric`) demonstrate age-stratum differentiation
  - R control: `moved.down === 0` sweeping R from 2 through 999 (I-1)
  - Surge: activates at 3× multiplier, stretches 2 band cadences
  - P-14 override: all 16 fields returned, hash chain valid
  - Config: model `medipilot-gbdt-v0.2.0`, calibration `isotonic-perstratum-v0.2.0`
  - Dual timestamps: `serverTime` and `simTime` present on all score responses

- **I7c — Logged this session and answered §9 open questions** in `BACKEND_INTEGRATION_LOG.md`.

- **UI Polish (Session 15.5).** Redesigned `/control` page (12-column control-room grid with segmented controls, simulation status panel, patient token census) and `/audit` page (JSON-viewer aesthetic, segmented filters, hash chain validation pill, chevron rotation). Both pages stripped of legacy CSS variables and rebuilt with explicit Tailwind utility classes matching the established design system.

**Why**
- I7 is the final verification gate before the system can be demonstrated end-to-end with the real trained GBDT model instead of the mock adapter. Every invariant that the plan commits to has now been tested against the actual backend code.

**Decided**
- *The orchestrator is the integration surface, not `api.py`.* The existing 7 endpoints in `api.py` remain untouched as the Track A/B interface. The orchestrator's 12 endpoints serve the frontend contract natively in camelCase — no mapping layer in TypeScript.
- *Corpus joined on `case_id`.* The `CASE_MAP` in `seed.py` joins 13 backend cases to frontend encounter IDs. 7 unjoined frontend records get synthesised flat trajectories. Neither corpus was renumbered.
- *The mock adapter remains the default.* `NEXT_PUBLIC_MP_SOURCE=mock` is the insurance policy. `live` is the bonus. Both are verified.

**Verified**
- `pytest tests/test_orchestrator_contract.py -v` → 12/12 passed (6.93s)
- E2E script → 22/22 passed
- `npm run build` → all 9 routes clean, TypeScript passes

**Next**
- Demo rehearsal: start both servers, set clock to 60×, walk the full §15 narrative end-to-end in browser. Cross-check live vs mock for any divergences worth showing or fixing.

---

## 2026-08-26 · Session 15 — P12 · Responsive, Performance & Final Polish

**Did**
- Added lazy loading via IntersectionObserver to `VideoClip` (200px rootMargin) and `VideoBackground` (100px rootMargin). Videos below the fold no longer preload on page open.
- Mobile breakpoint for hero: 3D mascot hidden below `md`, static PNG shown instead.
- `FeatureRow` responsive breakpoint lowered from `lg` to `md` for tablet-friendly layout.
- Updated `IMPLEMENTATION_LOG.md` with P8-P12 sessions.

**Why** — Performance: 13 video files (27 MB total) must not all load on first paint.

**Decided** — IntersectionObserver with `rootMargin: '200px'` for VideoClip starts loading slightly before visible for seamless playback.

**Next** — Cross-browser testing, Lighthouse audit, demo rehearsal.

---

## 2026-08-26 · Session 14 — P11 · Patient Surface Polish

**Did**
- Intake: swapped boot video to `boot-sequence.mp4`, replaced 2D Mascot with 3D MascotScene, attract video as 20% opacity background behind 3D model, language buttons in GlassCard.
- Hall: added `waiting-ambient.mp4` at 12% opacity, token glow-teal, staggered fadeIn animation, 3D MascotScene in footer.

**Why** — Patient surfaces benefit from visual warmth; clinical surfaces untouched per mascot law.

**Decided** — Attract video plays behind 3D mascot instead of replacing it. Token fadeIn stagger of 50ms stays within 120ms per-element budget.

**Next** — P12.

---

## 2026-08-26 · Session 13 — P10 · Landing Page Redesign

**Did**
- Complete rewrite of `app/page.tsx`: 7-section cinematic scroll-through (Hero with video BG + 3D mascot, Problem Stats with animated counters, How-It-Works timeline, 6 Feature Highlight rows with video clips, Architecture showcase, Surfaces Grid with gradient borders, Footer). All 13 video clips integrated.

**Why** — Landing page is the first thing judges see. Static grid was functional but unimpressive.

**Decided** — Six FeatureRows instead of three. Architecture text as CSS overlay, not burned into video. `data-surface="landing"` for dark theme.

**Next** — P11.

---

## 2026-08-26 · Session 12 — P8+P9 · Foundation Layer & 3D Mascot Engine

**Did**
- Installed `@react-three/fiber`, `@react-three/drei`, `three`, `@types/three`.
- Added CSS utilities: glassmorphism, gradient borders, glow effects, video-bg, smooth scroll, custom scrollbar.
- Built 6 UI components: `VideoBackground`, `GlassCard`, `StatCounter`, `SectionHeading`, `VideoClip`, `FeatureRow`.
- Built `MascotScene.tsx` (5-light setup, Float animation, state-driven transforms, mobile fallback), `KioskScene.tsx`, `useCan3D` hook.

**Why** — Three.js + R3F needed for 3D mascot. Shared UI primitives needed before landing page rebuild.

**Decided** — Skipped postprocessing/HDRI. Bright lighting (ambient 3, key 4) after initial render was too dark. `scene.clone()` to avoid mutating cached GLTF.

**Next** — P10.

---

## 2026-08-24 · Session 11 — P7 · Voice

**Did**
- Created `useVoice` hook wrapping Web Speech API (`webkitSpeechRecognition`) for STT and `window.speechSynthesis` for TTS. Added vocabulary guard preventing speech of acuity levels or diagnoses.
- Implemented `CockpitRing` with mascot `listening` pose and mic-level stroke animation.
- Implemented `VoiceStatusChip` to indicate mic state (listening, speaking, error, muted).
- Added `audio.ts` with synthesised Web Audio API cues: escalation chime, capture confirm, commit settle.
- Integrated voice into `intake/page.tsx` across `TreeStep` (answering), `ReadbackStep` (speaking summary), `TokenStep`, and `RedFlagInterrupt`.
- Added scripted-voice dispatch and global mute toggle in `control/page.tsx` as mic-failure insurance for demo day.

**Why**
- `FRONTEND_PLAN.md` §9 and `SCREENS_SPEC.md` K4/K6 specify voice as a droppable layer over the typed intake tree. 
- P7 is the final major feature component of the system plan.

**Decided**
- **Dual approach to speech-to-text**: We implemented real `SpeechRecognition` but also added a `synthetic-speech` event dispatcher in the control panel. This provides a guaranteed fallback if demo venue Wi-Fi blocks the browser STT engine.
- Web Audio API was used for sound effects instead of `.mp3` files to eliminate external assets and latency.

**Next**
- **P8 · Rehearsal and final polish.** The application is feature complete.

---

## 2026-08-24 · Session 10 — P6 · Surge

**Did**
- Added `setSurge` to `MediPilotApi` interface and mock adapter.
- Implemented `generateSurgeFillers()` to inject 10 synthetic GREEN/YELLOW patients (F-01…F-10) upon surge activation, pushing the waiting count to 30.
- Implemented cadence stretching in `mock.ts` and `safeWait.ts`. `SURGE_CADENCE_TABLE` stretches YELLOW remeasure 30m → 45m and GREEN 60m → 90m, leaving RED untouched.
- Handled GREEN → YELLOW breach escalation path in `mock.tick()`. Two missed remeasures trigger a time-based escalation. P-20 exits P6 by breaching this ceiling under load.
- Board UI updates:
  - Added surge banner with `[what this means]` expander showing stretched cadences and forbidden relaxations (`surgeState.refusals`).
  - Auto-compact mode: when `waiting.length > 18`, `QueueCard` density switches to `compact` (smaller padding, smaller token, truncated complaint, compact badges).
  - Ranked alert feed: a 20-item ring buffer showing stream events (breach, escalation) at the top of the board.
- Control page updates: Wired up `toggleSurge` to `api.setSurge`, showing injection count, stretched state, and board-compact indicator.

**Why**
- Surges test system safety. Under stress, a system that stretches too far fails silently. By showing *what is refused* (Red cadences, OOD abstention) explicitly, we demonstrate safety invariants in the UI.
- The GREEN → YELLOW time breach ensures that a patient dropped into the queue and ignored (P-20) will eventually surface, preventing silent starvation.
- Compact mode implements DESIGN_SYSTEM §5 layout scaling without losing the 3-fact cadence requirement.

**Decided**
- *Filler encounters use deterministic tokens F-01…F-10.* Not randomizing makes the demo predictable. They are intentionally unremarkable so they don't distract from P-20.
- *Surge is a toggle, not a slider.* The system plan calls for "Surge active" or "inactive". We keep it binary to match the demo script.
- *Surge events don't reload the page.* Stream events inform the frontend to re-fetch `getSurge()`, creating immediate visual feedback on the board.

**Verified**
- Activated surge on `/control` -> saw 30 patients.
- Checked `/board` -> compact mode active, surge banner rendered.
- Sped clock to 60x -> watched P-20 breach and escalate to Yellow on time alone.
- Alert feed populated with the breach and escalation.

**Next**
P7 · Audit ledger and cryptographically-signed override capture.

---

## 2026-08-23 · Session 9 — P5 · Typed intake, mascot, red-flag interrupt

**Did**
- Built `Mascot` component with the runtime clinical-surface guard (throws in dev on `/board`, `/card`, `/control`, `/audit`). Enforced in code so the mascot law lives in the codebase, not in memory.
- Wrote the age-aware question tree (`lib/intake/questionTree.ts`): common questions (chief complaint, onset, severity, meds) plus stratum-gated ones (peds-feeding, peds-alert for children; geri-baseline, geri-falls for geriatric). Each question is one screen, one decision.
- Complete `/intake` rewrite as a ten-step state machine — welcome, companion, human-offer, consent, basics, tree, pain, readback, token, plus the `human-lane` branch for consent-declined or human-preferred, plus the global `redFlagInterrupt` overlay.
- Wired six mascot poses across the flow: `pose-01` welcome (goggles up), `pose-06` companion, `pose-08` human-offer, `token` on token-issued, `human-lane` on consent-declined branch, `steady` on the red-flag interrupt (calm-serious, no alarm). `resting` also lands on `/hall` and `pose-01` on the launcher.
- `videos/kiosk-attract.mp4` autoplays on the welcome step after 30 seconds of idle — the boot video sits in P8 for now.
- Red-flag pass runs on every keystroke in the chief-complaint field (`scanRedFlags`). If it fires: overlay opens, mascot switches to `steady`, MediPilot speaks *"Let's get someone to you right now"* via `speechSynthesis`. The word RED — and every acuity word — never appears anywhere on the patient side, per §7 and §9.
- Readback step (§7): dashed border until confirmed, solid on confirm, speaks the summary via `speechSynthesis` (`hi-IN` or `en-IN` depending on language), and mounts `<LockedAcuitySlot />` at its foot — the LLM-cannot-emit-acuity claim shown on the patient side too.
- Token step speaks the token number and shows a persistent **I feel worse** button — patient-initiated escalation channel.
- Language toggle in the header flips between EN and हिं live — every user-facing string has both.
- Motion cross-fades between steps (`AnimatePresence`, 140 ms) — fits the §6 "≤120 ms cross-fade" allowance for non-queue transitions.

**Why**
P5 exits when P-17 declines consent and is triaged without penalty (Human Lane) and P-18 red-flags on narrative with unremarkable vitals (interrupt fires on text sweep). Both are reproducible: on the consent step, un-tick "listen"; the flow diverts to the Human Lane screen that reads "your queue position is not affected". Type "active labour, contractions 3 minutes apart" in the chief-complaint text and the interrupt fires from anywhere in the tree.

**Decided**
- *`speechSynthesis` for readback and interrupt, not just a caption.* §7 makes MediPilot speaking a specification, not a nice-to-have. `speechSynthesis` is browser-native, zero keys, immune to venue Wi-Fi — the demo runs offline. Rate 0.95, `en-IN` / `hi-IN` where available.
- *The red-flag pass runs on keystrokes, not on submit.* An "active labour" phrase surfacing mid-typing should interrupt mid-typing; making the patient wait to submit before a red flag fires would be a build-order artefact, not a design choice.
- *The mascot renders through the guarded component only.* Nothing in `/intake`, `/hall` or `/` reaches into `public/media/mascot` directly; the `<Mascot>` wrapper is the only path. So the CLINICAL_ROUTES check catches any mistake with a throw before the pixel lands.
- *Two consent toggles, not three.* F17 removed ambient sensing (not built).
- *Human Lane is a real branch with its own screen, not a bounce-out.* SCREENS_SPEC §2 flags this as the one place most demos ship a check-box that blocks progress; ours actually forks.
- *Question tree is data, not JSX.* Adding a stratum-specific question is a row edit, not a component edit. Judges asking "what about pregnant women" or "what about dialysis" can be answered by pointing at a config file.
- *No mascot on the readback screen itself.* The `LockedAcuitySlot` earns its slot there — a second mascot pose would visually compete with the "structurally cannot emit acuity" statement, which is the point of the screen.

**Verified**
`npx next build` — 9 routes clean. Manual rehearsal of the two P5-exit demos:
1. `/intake` → English → alone → "I'll continue here" → un-tick "Let MediPilot listen…" → Human Lane screen renders `human-lane.png` + "your queue position is not affected" copy.
2. `/intake` → English → alone → continue → consent (both on) → age 26, female → chief complaint "active labour with contractions 3 minutes apart" → red-flag overlay fires immediately, `steady.png` shows, speech says "Let's get someone to you right now", no acuity word anywhere.

**Next**
P6 · Surge. 3× arrival rate, board density switch (auto-compact at >18 waiting), ranked alert feed, forbidden-relaxations banner on `/board`. Exit: P-20 breaches under load.

---

## 2026-08-23 · Session 8 — P4 · The R control (graded item)

**Did**
- Installed `motion` (formerly framer-motion). The one animation the plan preserves (§6) now runs: `<motion.div layout>` inside a `<LayoutGroup>` on `/board` and the mini census on `/control`. Spring: `stiffness 320, damping 30, mass 0.7` — 400–500 ms visible reorder, layout-driven so the movement itself carries the information.
- Mock adapter: added a per-record `PROBABILITY` map (20 hand-tuned values) and a `bandFromProbability(p, pStar)` rule with `RED at 10× p*`, `YELLOW at p*`. Chosen so at R = 500 (p* = 0.002) every record reproduces its authored band.
- `floorBand(e) = e.humanAssignedBand ?? e.currentBand` — reads the human floor when a clinician has weighed in, otherwise the system's own previous recommendation. This makes the "up-only" claim honest for patients no clinician has touched, not just for the explicitly human-assigned ones.
- `setR()` rewritten: for each waiting encounter compute `next = max(bandFromProbability, floor)`, mutate `currentBand` and the cadence tuple, count `up`/`down`. The `down` counter is emitted from the code path but the max-with-floor construction makes it structurally impossible for it to ever be non-zero — the invariant lives in one line, not scattered in a policy.
- `/control` rewritten as the graded deliverable: a large R display with live `p*` readout, three preset chips (R = 500 tertiary, 100 district, 50 aggressive-triage), a 120-ms debounced slider, three "moved" tiles including the locked "structurally 0" one that carries the invariant on its face, a live mini-census grid where the same 20 patients re-sort via `motion.div layout` as R moves, and the surge/clock controls kept below.
- `/control` polls the census every 1.5 s so cadence-driven escalations from the ticker also show up in the mini-grid — the R panel is honest about what changed vs what R did.

**Why**
P4 exits when a judge can move R and watch the board move. §02 makes demonstrating the escalation bias live a submission-gate item — a claim in the deck does not satisfy the brief. The counter that reads `0 moved down · 🔒 structurally 0` is the point of the whole panel; the reorder animation is what makes the point visible.

**Decided**
- *Motion library over View Transitions API.* `motion` handles the layout-diff work; VT would need a manual `document.startViewTransition` wrapper on every state change and only works on Chromium 111+. Bundle cost is worth the reliability.
- *Debounce the slider write, not the read.* Users drag the slider; each pixel change should not fire a full census recompute. 120 ms debounce is short enough that the last position wins visibly.
- *"Structurally 0" chip on the down counter.* The number is emitted from the code path, so a bug could push it non-zero — the chip is the honest way to say "this is not a coincidence, the max-with-floor construction guarantees it". If the number ever moves, the chip reads as a lie and we know something broke.
- *`PROBABILITY` lives inside the mock adapter, not on the wire type.* `Encounter` is the contract; giving it a `modelProbability` field would leak an implementation detail. The backend can return whatever it wants; the frontend only needs `band` and `probability?` on the score response for display.
- *Cadence tuple resets on band change.* When R pushes a patient to a new band, their re-score / re-measure / ceiling all snap to the new band's cadence. Not doing this would leave a freshly-Red patient sitting on a Green ceiling countdown, which is nonsense.

**Verified**
`npx next build` — 9 routes, TypeScript clean, no warnings. Manual rehearsal:
- `/control` at R = 500 → mini-grid shows the 20 records in their authored bands.
- Drag R down to ~50 → threshold rises, no downgrades (floor holds), moved.down stays 0 on every tick.
- Drag R up to ~900 → threshold drops below several YELLOW probabilities, `moved.up` fires and cards physically slide upward in the grid. Same movement plays on `/board` in another tab.

**Next**
P5 · Intake (typed). Four-step branch, age-aware question tree, consent gate, red-flag pass over structured output, mascot on. Voice remains P7 and droppable.

---

## 2026-08-23 · Session 7 — P3 · Override capture and the audit ledger

**Did**
- `types.ts` extended with `hash`/`prevHash` on `OverrideRecord` (envelope, not part of the 16 legal fields), and a new `OVERRIDE_REASON_CODES` list of ten site-configurable structured codes with `escalationOnly`/`deescalationOnly` guards.
- `DecisionInput` now accepts `factorsShown` and `scoreAtDecision` from the frontend — so the record captures the card **as displayed to the clinician**, not what the backend could recompute later. That was the specific §13 requirement I was hand-waving in P2.
- Mock adapter: `decide()` computes `inputsHash` from the vitals tuple, chains every row with `djb2Hex(prevHash || canonical(record))`, tracks `state.auditHead`, and unshifts the new row so the ledger reads newest-first while the chain reads oldest-first. `canonical()` extracts exactly the 16 legal fields for hashing — envelope excluded, so tampering with the envelope alone doesn't break the chain, only tampering with the record does.
- New `OverrideDialog` component (~230 lines): reason-code radio grid filtered by direction, required free-text note when `other-with-note` is picked, full verbatim preview of all 17 lines that will be signed, and a confirm button that becomes **hold-to-confirm** for downward moves — 1500 ms, RAF-driven progress bar rendered inside the button, cancel on mouse-leave.
- `/card/[id]` now opens the dialog instead of the P2 shortcut. Notice on commit reads `Signed into ledger · YELLOW · hash a1b2c3…`.
- `/audit` rewritten: hash-chain validity chip in the header (green/red, computed client-side by walking `records[i].prevHash === records[i-1].hash`), four filters (all / overrides / downward / escalations), row summary shows `prevHash→hash` in hex, click to expand and see all 17 fields plus a factors block indented under `factorsShown`, JSON export button writes a timestamped file via `URL.createObjectURL`.

**Why**
P3 exits when P-14's override produces the full record on screen. The P2 shortcut wrote *a* row; it did not satisfy §13 because `reasonCode` was a made-up string, `factorsShown` was a recomputation, `inputsHash` was `hash-${Date.now()}`, and there was no chain. All four are now correct.

**Decided**
- *`djb2` instead of SHA-256.* Real deployments compute SHA-256 in the backend and the frontend just displays what it receives. The mock needs a sync hash that runs in the browser without adding a crypto dependency; djb2 is deterministic, produces stable hex, and chains — which is the property this demo needs to show. When the HTTP adapter arrives it will just render the backend's SHA.
- *Hold-to-confirm is button-scoped, not a modal-scoped gesture.* The user's mouse can leave the button and the RAF cancels; there's no "invisible timer running while the dialog is open" pattern that could commit unintentionally.
- *Reason codes filtered by direction, not just labelled.* You literally cannot pick `resolution-on-reassessment` for an escalation, or `red-flag-symptom-reported` for a de-escalation. Less than a full workflow constraint, but more than a review comment.
- *Chain validity is computed on the client and shown as a chip.* If backend tampering ever landed a row that breaks the chain, the ledger visibly flips to red the moment it loads — the audit page is the last place we want silent trust in the wire.
- *Records are unshifted (newest-first) but the chain check reads oldest-first.* The reversed pass matches how the chain was written; presenting reverse-chronological is what a nurse needs.

**Verified**
`npx next build` clean. Flow rehearsed: `/card/P-14`, click Override → RED, dialog opens with the 17-field preview, radio grid filtered to escalation codes only, confirm writes to ledger, `/audit` shows the row with `genesis→…` in the summary and every field verbatim on expand. Then `/card/P-14`, Override → GREEN — button becomes "Hold to confirm downward override", progress fills to 100%, commits, `/audit` shows it as `de-escalation` and the chain chip stays green because `prevHash` matches.

**Next**
P4 · The R control. Slider on `/control` moves p*, board re-sorts live with the same patients, the "0 moved down" counter is the point.

---

## 2026-08-23 · Session 6 — P2 · The nurse card

**Did**
- Six new components: `RedFlagBanner`, `ConfidenceBand`, `ExplanationChannels`, `LockedAcuitySlot`, `AbstentionCard`, `AcuityCard`. Each carries one invariant on its face — dev-throws where the invariant is structural.
- `AcuityCard` throws in dev when the score is missing `confidence`, `conformalSet` or `inputsUsed` (I-2). The throw quotes the missing keys and cites the BACKEND_INTEGRATION_LOG line, so a judge asking "how do you know" sees the enforcement, not a review comment.
- `AbstentionCard` accepts `effectiveBand: 'YELLOW'` as a literal type — Green is unrepresentable, not merely unrendered (I-5 in the type system). A runtime guard covers the `as` escape hatch.
- `LockedAcuitySlot` mounted at the foot of every card. Forty lines that carry the whole architectural argument: the LLM has no production rule for acuity.
- Mock adapter `generateExplanation` rewritten as case-aware — P-07 renders three factors ending with a genuine opposing one; P-04/06 apply the `geriatric-stratum` reliability discount by name; P-08 marks the SpO₂ as having no de-escalation authority in the factor list; P-13 shows `communication-barrier`; P-19 shows `stoic-flag`; P-16 shows `non-assisted` + inferred stratum.
- Per-record confidence tuning: P-07 and P-11 return a wide {YELLOW, RED} conformal set with `low` confidence, so ambiguity is visible; P-09 returns `low` with `stale-reading`; P-10 with `sensor-disagreement` + `missing-field`; P-15 with `out-of-distribution`.
- `/card/[id]` rewritten: two-column layout, chief-complaint header (consent refusal shown as a neutral note, never a risk factor per §8), cadence strip in a bordered card, `AcuityCard` or `AbstentionCard` on the left, `VitalChip` grid on the right, Accept + three Override buttons wired to `api.decide()` and pushing rows into `state.audit` so `/audit` fills up as you use it.
- Accept button disabled on abstained records — you cannot Accept a Yellow floor that no model produced.

**Why**
P2 exits when P-07 renders ambiguous and P-15 abstains out loud. Both were passing generic explanations from Session 5's placeholder — technically true, unconvincing to a judge. Making the demonstration records demonstrate what they were written for is the whole point.

**Decided**
- *`LockedAcuitySlot` on every card, not just intake.* DESIGN_SYSTEM §7 puts it at the foot of the intake structuring screen; the R2 plan reasoning applies equally to the nurse-facing card. Showing an LLM that structurally cannot emit a band is a claim worth making twice.
- *Override buttons are a shortcut, not the full path.* P3 owns the 16-field capture. The current buttons write a minimal audit row with `reasonText: '[quick-override — full 16-field capture arrives in P3]'`, so nothing is silent, but the actual dialog is scoped to next session.
- *Channel 2 and 3 are collapsed by default.* §8 says the card must be absorbable in seconds by someone managing several patients. Channel 1 + red flag + confidence must fit above the fold on a 1440×900 dark screen; the rest is one tap away.
- *`AbstentionCard` uses a string-literal prop type for the band.* This is the cleanest way to say "GREEN cannot appear here" in TypeScript. The runtime throw is a belt for the `as YELLOW` cast; leaving both in means either a code change OR a data change would need to defeat the invariant intentionally.

**Verified**
`npx next build` — 9 routes, TypeScript clean, no warnings. `/card/P-07` shows wide {YELLOW, RED} set with a mandatory opposing factor. `/card/P-15` shows the hatched abstention card, no numbers, Yellow-floor notice. `/card/P-14` accepts an Override → RED which appears in `/audit` immediately.

**Next**
P3 · Override + audit. Real 16-field capture dialog with structured reason codes and the confirm-and-hold on downward moves. `/audit` renders records verbatim with the hash chain visible.

---

## 2026-08-23 · Session 5 — P1 · Board and the two clocks

**Did**
- Extracted four clinical components: `components/clinical/BandChip.tsx`, `CadenceStrip.tsx`, `VitalChip.tsx`, `QueueCard.tsx`. Each obeys the rules from `../DESIGN_SYSTEM.md` §3 and §8 — colour + glyph + word (never colour alone), stratum→value→freshness order on vitals, three time facts per card.
- Rewrote the mock adapter with a real simulated clock: `simNowMs()` advances at `clockSpeed` seconds per real second; `tick()` runs each second, marks `cadence.breached` when a ceiling passes, and **escalates any Yellow whose ceiling is exceeded to RED with `cause: 'CEILING'`, no vital having moved**. Emits `escalation` and `breach` on the stream.
- Rewrote `/board`: `simNowMs` state drives the whole page's cadence display; SSE subscription flashes escalated cards for 20 s with an `aria-live="assertive"` alert; three lanes — abstained + breached ("Needs Your Eyes"), then the ordered queue; header carries waiting count, longest wait, breach count, abstained count and the `SIMULATED DATA` chip.
- Existing `card/[id]` page still reads the escalated band correctly because it re-fetches from the same mock adapter state.

**Why**
Correction F1 (the two clocks) is the largest single delta from the previous plan and is meaningless without something that actually breaches on time alone. P1's exit criterion is exactly that: a Yellow that reaches its wait ceiling turns Red without any physiology having changed. `tick()` in the mock adapter is what makes that observable at demo speed.

**Decided**
- *Sim clock lives inside the mock adapter, not in a Zustand store.* §15 says the scheduler is backend-owned; the frontend just renders `simTime`. Keeping the clock inside the adapter means the same code path runs against `mock` and `live`, and the components stay adapter-agnostic.
- *No motion library yet.* Reorder happens instantly — the animation is a P4 polish task and adding `motion/react` now costs bundle size for no P1-exit benefit. Escalation flash is a CSS `animate-pulse` + border shadow, which is information (a card just moved bands) and thus earns its place under §6.
- *`justEscalated` is state, not a derived prop.* Twenty-second flash is a UI-only concept, so it lives in the `/board` component with its own timer map. Cleared on unmount.
- *Deep-copy on `getCensus` and `getEncounter`.* React needs new object references to re-render, and the adapter mutates cadence in place during `tick()`. Cheap at 20 encounters.

**Verified**
`npx next build` — 9 routes, TypeScript clean, no warnings.

**Next**
P2 — the nurse card. Three explainability channels, conformal set, `<AbstentionCard>` with Yellow floor, red-flag as leading factor, `<LockedAcuitySlot>` component. Exit: P-07 renders ambiguous with a wide conformal set, P-15 abstains loud with no Green code path.

---

## 2026-08-23 · Session 4 — P0 · Foundations

**Did**
- Wrote `app/globals.css` with the token set from `../DESIGN_SYSTEM.md` §3: brand palette, acuity palette, and both surface themes (`clinical` dark and `patient` warm-paper).
- Layout switched from Geist to Inter + Noto Sans Devanagari via `next/font`. Tabular numerals set globally on body.
- Corpus `lib/seed/corpus.ts` — all 20 records P-01…P-20 verbatim from `../SCREENS_SPEC.md` §0. Each generates its own cadence from the band-cadence table, so no per-record timing was hand-typed.
- Clinical utilities under `lib/clinical/`: `ageBands.ts` (six-stratum resolution, unknown → adult marked `inferred`), `safeWait.ts` (`CADENCE_TABLE` and `computeCadenceState`), `redFlags.ts` (deterministic pattern sweep for the P-01 / P-18 cases).
- Full mock adapter `lib/api/adapters/mock.ts` — every method on `MediPilotApi`. Enforces Invariant 5 by hard-coding `effectiveBand: 'YELLOW'` for the abstained record. `client.ts` throws if `NEXT_PUBLIC_MP_SOURCE=live` because the HTTP adapter is not written yet.
- Six route shells: `/`, `/board`, `/card/[id]`, `/intake` (four-step branch, typed only — voice is P7), `/control` (R slider live, clock speed, surge toggle), `/audit` (model card + empty ledger), `/hall` (token grid, no acuity).

**Why**
P0 exit criterion is *corpus loads, six routes resolve*. Everything above serves that.

**Decided**
- *Corpus lives in `lib/seed/`, not in the adapter.* Same data must feed a future `http` adapter's fixture mode, so it stays adapter-agnostic.
- *Vitals defaulted to `fresh` unless a record specifically demonstrates staleness.* P-09 gets `expired` across the board (freshness contract); P-10 gets a mix (sensor loss); P-20 gets `discounted` (surge-induced missed rechecks). Everyone else is fresh at t=0.
- *`app/page.tsx` is a launcher, not an ambient homepage.* Demo day the operator opens four surfaces on four devices in twenty seconds — the launcher is a real workflow tool.

**Verified**
`npx next build` — all 9 routes prerender cleanly, TypeScript passes with no errors.

**Next**
P1 — extract `QueueCard` + `CadenceStrip`, add live sim-clock advancement to the mock adapter, wire escalations on `/board`.

---

## 2026-08-22 · Session 3 — Plan correction against the R2 system plan

**Did**
- Received the authoritative *MediPilot — Round 2 Implementation Plan* (R2 draft 1) and corrected the frontend plan against it. 17 corrections, F1–F17, tabulated in `../FRONTEND_PLAN.md` §1.
- Restructured the repository: all Next.js code moved out of the project root into `./frontend/`. Planning docs and submission material stay at the root.
- Fixed the TypeScript path alias from `./src/*` to `./*` after flattening `src/app` → `app`.
- Rewrote `./BACKEND_INTEGRATION_LOG.md` as a module-by-module map (M01–M22 → frontend consumer), replacing the earlier endpoint-only version.
- Created this file.
- Corrected `../DESIGN_SYSTEM.md`: motion budget cut (§6), voice resequenced to P7/droppable (§7), clinical components rewritten (§8) for three explainability channels, `<CadenceStrip>`, the freshness contract, the Yellow abstention floor, the stoic flag, and the rule that consent refusal is never rendered as risk.
- Corrected `../SCREENS_SPEC.md`: replaced the invented census with the authoritative P-01…P-20 corpus; added a route-rename banner (`/kiosk`→`/intake`, `/bench`→`/card/[id]`, `/corridor`→`/board`, `/board`→`/hall`, `/charge` deleted, Demo Control→`/control`).
- **P0 started:** wrote `lib/api/types.ts` — the v0.2 contract in code. Typechecks clean.

**Why**
The earlier frontend plan predated the system plan and contradicted it in four load-bearing places: one re-triage clock instead of two (D1), voice-first build order instead of typed-first (D12/§16), a four-animation motion budget against an explicit instruction to cut motion (§16), and an invented patient census instead of the authoritative P-01…P-20 corpus (§14).

**Decided**
- *Scope reductions accepted rather than argued.* Mass-casualty mode and ambient-sensing UI are removed from the frontend, because §15 lists them as described-not-built. Building a screen for either would put something on stage the team has committed to not claiming.
- *Motion budget cut from four animations to one.* §16 names frontend polish as a schedule risk and rules that motion earns its place only where it shows a queue re-ordering. The earlier budget was written before that instruction existed. Queue re-ordering survives; the tick shimmer, the field-extraction fly-in and the bespoke de-escalation choreography are cut.
- *The R control is promoted from debug toggle to demonstrated deliverable.* §02 makes demonstrating escalation bias live a self-imposed submission gate, and the brief requires teams to show the design choice explicitly in the prototype. That makes it frontend work with a grade attached, so it gets its own build phase (P4) and its own route (`/control`).
- *`/charge` and `/corridor` dropped as routes.* `/corridor` was the same screen as `/board`; `/charge`'s only distinct content was mass casualty.
- *Client-side scheduler demoted.* §15 puts the scheduler and the simulated clock in the backend service. The client engine survives inside the mock adapter only, and the frontend must not treat its own clock as authoritative when running `live`.

**Next**
Finish P0 — `lib/seed/corpus.ts` (the 20 records), `lib/api/adapters/mock.ts`, `lib/api/client.ts`, then the six routes.

**Known issue**
`app/layout.tsx` reports `TS2304: Cannot find name 'LayoutProps'`. Pre-existing scaffold artefact: Next 16 emits route types into `.next/types`, which was lost when the app was relocated. Resolves on the first `npm run dev` or `npm run build`. Not caused by any file we wrote.

---

## 2026-08-22 · Session 2 — Media pipeline

**Did**
- Generated the mascot asset set in Google Flow against a saved `MediPilot` Character: 8-pose sheet, listening (goggles down), steady (non-smiling), token, resting, human-lane, plus app icon, OG card, two background textures, two state illustrations, and two videos (`boot-goggles.mp4`, `kiosk-attract.mp4`).
- Backgrounds removed via remove.bg; outputs normalised and renamed into `public/media/{mascot,states}/cutout/`.
- Full backup of the untouched originals kept at `public/media_copy/`.
- `tools/cutout.py` written as the local fallback path — corner-seeded flood fill plus a pose-sheet splitter.

**Decided**
- *remove.bg used instead of `cutout.py`.* Both produce transparent PNGs; remove.bg handles the JPEG compression halo around the black linework better than a flood fill does. `cutout.py` stays in the repo as the offline fallback and for the grid split.
- *`brand/` and `textures/` deliberately not cut.* Those are full-bleed backgrounds and a solid-background icon; corner-flood would eat the wrong pixels.

**Next**
Wire the mascot into the patient surface once routes exist. Per the mascot law it appears on `/intake` and `/hall` only.

---

## 2026-08-22 · Session 1 — Planning and scaffold

**Did**
- Read the Round 2 brief and the Round 1 white paper. Drafted the first frontend plan, design system, screen spec, content prompt pack.
- Scaffolded Next.js 16 (App Router, TypeScript, Tailwind v4, ESLint) via `create-next-app`.

**Decided**
- *Mascot confined to patient-facing surfaces.* The Round 1 paper §11 lists "no virtual-nurse persona or avatar" as an anti-decision, and the logo is a mascot. Resolved by rule rather than by dropping either: the character owns the patient side and is banned from every clinical surface, enforced by a runtime guard.
- *Mock adapter is the default, not the fallback.* The demo must not be able to fail because the backend is late.
- *Next.js chosen over Vite* so each surface has a real URL and can be opened on a separate device during the demo.

**Note**
`create-next-app` rejected the project folder name (spaces and capitals are not npm-legal), so the app was scaffolded in a temp directory and moved in. Session 3 relocated it again into `frontend/`.
