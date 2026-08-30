# MediPilot — Business Deck: Design Brief

**Hand this whole file to Claude in a fresh session.** It contains the design
system, the slide plan, and the image manifest. Everything in it is read from
this repository — no invented values.

Companion documents (same house style, same numbers):
`docs/submission/BIT01_solution.pdf`, `BIT01_implementation_readme.pdf`,
`BIT01_business_proposal.pdf`.

---

## 0. What to build

**A 16:9 HTML/CSS deck, one `<section>` per slide, printable to PDF.**

Reasons this beats generating a `.pptx` directly: the house style *is* CSS, the
existing pitch artefacts in `docs/submission/` are already standalone HTML, the
diagrams are SVG and stay vector, and a browser print at A4-landscape gives a
PDF a judge can open anywhere.

If an **editable** `.pptx` is genuinely required — because someone else must
edit slides without touching code — build it with `python-pptx` instead, using
the same tokens in §1. Say so up front rather than half-doing both; a deck
converted from HTML to PPTX loses every gradient, rule and web font.

Target length: **20 slides**, 12–14 minutes.

---

## 1. The design system

Ported from `docs/paper/business_proposal.tex`. Use these values exactly.

### 1.1 Palette

```css
:root {
  /* Brand — chrome only, never clinical meaning */
  --acc-purple:  #A100FF;   /* rules, section numbers, figure labels, page no. */
  --sec-purple:  #6F00B8;   /* links, code paths, sub-heads */
  --dark-plum:   #24003D;   /* inverted "thesis" slides */

  /* Ink */
  --near-black:  #111111;
  --med-gray:    #666666;   /* captions, footer */

  /* Ground */
  --card-bg:     #F7F7F7;
  --soft-gray:   #F2F2F2;
  --border:      #E2E2E2;
  --white:       #FFFFFF;

  /* Acuity — meaning, never decoration. Values taken from the APP
     (web/app/globals.css, light-ground set) so slide chips match screenshots. */
  --acuity-red:        #C62D26;  --acuity-red-fill:    #FBE7E5;
  --acuity-yellow:     #9A6206;  --acuity-yellow-fill: #FCF1DC;
  --acuity-green:      #1B7A4B;  --acuity-green-fill:  #E4F4EB;
  --acuity-abstained:  #5B4BC4;  --acuity-abstained-fill: #ECE9FB;
}
```

> **The one colour rule.** Purple is brand chrome. Red/amber/green/violet carry
> clinical meaning and nothing else — never use an acuity colour to decorate a
> heading, and never use brand purple for a band. Abstention violet `#5B4BC4`
> is deliberately close to but distinct from brand purple; do not merge them.
> The paper has no abstention colour because it never needed one; the deck does.

### 1.2 Type

| Role | Font | Notes |
|---|---|---|
| Body / prose | Times-like serif — `Tinos`, `Liberation Serif`, Georgia fallback | the paper uses `newtxtext` |
| Headings, UI, tables, captions | **Inter** | the app's own font (`--font-inter`), so chrome matches screenshots |
| Code, paths, IDs | `Geist Mono`, `SF Mono`, `Consolas` | matches the app |

Section heads: **uppercase, Inter bold**, with a purple number prefix, sitting
on a **1pt `--acc-purple` rule that runs the full content width**. This rule is
the single most recognisable element of the house style — put it on every slide
that has a heading.

### 1.3 Components to port

Four box styles from the paper (`tcolorbox`), as CSS classes:

| Class | Background | Accent | Use |
|---|---|---|---|
| `.mpbox` | `--card-bg` | 2.2pt left border `--acc-purple` | a supporting point |
| `.mpthesis` | `--dark-plum`, white text | none | the one claim of the slide |
| `.mpcode` | `--near-black`, white mono | none | commands, paths |
| `.mpwarn` | `--soft-gray` | 2.2pt left border `--acuity-red` | a caveat or limit |

Tables: **booktabs only** — a top rule, one rule under the header, a bottom
rule. No vertical lines, no zebra striping. Header row `rgba(161,0,255,0.10)`.

Captions: `Figure 3.` in **bold `--acc-purple`**, the rest in `--med-gray`
Inter at ~13px.

Footer on every slide: a 0.4pt `--border` rule, then
`MediPilot • Business Proposal • Team 01 BIT` on the left in `--med-gray`, and
the slide number on the right with the current number in `--acc-purple`.

### 1.4 Handling the theme clash — read this before placing any screenshot

**The app is not purple.** Its accent is coral `#DF423D`, and its surfaces are a
warm off-white `#FBF7F2`, not the paper's cool `#F7F7F7`. This is a real
mismatch and it must be managed, not ignored.

Do this:

1. **Never re-theme the app for screenshots.** Showing a purple product that
   doesn't exist is the kind of thing a judge finds out about in Q&A.
2. **Keep purple at chrome level** — rules, numbers, captions, the frame around
   a screenshot. Let the screenshot be itself inside that frame.
3. **Frame every screenshot identically**: 1px `--border` stroke, 6px radius, a
   soft shadow, and a caption underneath. Consistency of the *frame* is what
   makes mixed-palette screenshots read as one deck.
4. **One surface is dark.** `/audit` is `data-surface="clinical"` (`#0A0D14`);
   every other route is warm light. Put the audit shot on a `--dark-plum`
   slide and let it be the deliberate tonal break in the deck — around slide
   11, where the argument turns to accountability.

---

## 2. Slide plan

Each slide: **one claim, one number, one image.** The proposal is 13 pages of
argument; the deck is not a summary of it, it is the spine. Do not port tables
wholesale — a table with more than 5 rows does not belong on a slide.

| # | Slide | The one number | Image |
|---|---|---|---|
| 1 | Title — MediPilot / PatientTriage.ai, Team 01 BIT | — | B1, B2 |
| 2 | Nobody waits unseen | 32.2% ESI mistriage | A15 |
| 3 | Why clinical AI has failed here | Epic Sepsis: AUC 0.63 vs 0.76–0.83 marketed; 109 alerts per true positive | — (typographic) |
| 4 | The gap is the wait itself | 100–500 visits/day, ~50% with any prior record | A15 or A17 |
| 5 | The product in one screen | — | **A1 (hero, full bleed)** |
| 6 | Architecture | — | D1 |
| 7 | The invariant: the model never assigns acuity | — | D2 |
| 8 | Four lanes out of the bench | — | D3 |
| 9 | The card a nurse sees | confidence band + opposing factor | A3 |
| 10 | When it doesn't know, it says so | ~8% abstention | A4 |
| 11 | Override is one tap, and always logged | 17 substantive fields, SHA-256 chained | A9 + A10 *(dark slide)* |
| 12 | Age is not a modifier, it's a stratum | 6 strata; neonate FNR 0.195 | A5 + per-stratum table |
| 13 | Floors that don't negotiate | red flags; SpO₂ 11.7% vs 3.6% occult hypoxaemia | A6 + A7 |
| 14 | 3× surge without lying | — | A16 + A2 |
| 15 | **What it actually buys you** | **21.6 min mean head start, 16/20 patients** | C1 + C2 |
| 16 | We grade ourselves on 8 gates — and report 7/8 | 7/8 on the fresh split | C3 |
| 17 | Every model choice was measured | 4 risk models, 10 LLMs, 12 ASR backends | C5 + C6 |
| 18 | Scales down as well as up | 3 independently adoptable tiers | D4 |
| 19 | Business case and roadmap | < Rs. 5/encounter (illustrative) | — |
| 20 | Risks, honestly — and the ask | — | B2 |

**Slide 16 is the one that wins or loses the room.** Do not soften it. The
shipped model passes 7 of 8 gates and fails `beats_handcoded_baseline`; the
argument is that a rule card a learned model cannot reliably beat is the
correct floor to build on, and that the model's real value is temporal — which
slide 15 has already demonstrated with a measured number.

---

## 3. Image manifest

### 3.1 Already in the repo — nothing to procure

| ID | File | Note |
|---|---|---|
| D1 | `docs/diagrams/01-full-architecture.svg` | **use the .svg, not the .png** — vector, no trimming |
| D2 | `docs/diagrams/02-post-risk-engine-decision-path.svg` | |
| D3 | `docs/diagrams/03-in-the-room-lanes-and-voice.svg` | |
| D4 | `docs/diagrams/04-tech-stack-three-tiers.svg` | |
| D5 | `docs/diagrams/05-vigil-story-diagram-page2.svg` | optional |
| B1 | `docs/paper/assets/accenture_logo.png` | |
| B2 | `web/public/media/brand/icon-1024.jpeg`, `og.jpeg` | |
| M1 | `web/public/media/mascot/` — `listening.png`, `resting.jpeg`, `steady.jpeg`, `token.jpeg`, `pose-sheet.jpeg` | use sparingly; this is a business deck |
| M2 | `web/public/media/states/offline.jpeg`, `rule-card.jpeg` | good for slides 7 and 18 |
| M3 | `web/public/media/textures/hall-light.jpeg`, `cockpit-dark.jpeg` | slide backgrounds only, heavily dimmed |

The PNG diagrams carry ~55% blank canvas and needed measured `trim` values in
LaTeX. **In HTML use the SVGs and this problem disappears** — do not port the
trim numbers.

### 3.2 Charts — regenerate, do not screenshot the PDF

Re-render these as SVG from the committed JSON. Screenshotting the PDF gives
raster charts with the paper's serif labels; the deck wants Inter and crisp
vectors.

| ID | Chart | Source data |
|---|---|---|
| C1 | Head start per patient (P-03 & P-09 at 55 min, down to P-11 at 15) | `docs/benchmarks/time_to_detection.json` → `per_patient` |
| C2 | p(t) curves, P-01 / P-14 / P-20, with `p*_yellow`=0.0760 and `p*_red`=0.1473 threshold lines | same file → `curves` |
| C3 | 8-gate matrix, 4 models × 8 gates | `docs/benchmarks/risk_engine_bakeoff_results.json` |
| C4 | Under-triage vs over-triage, model vs rule card | `.../medipilot-gbdt-v0.2.0/metrics.json` |
| C5 | Latency budget: ASR + structurer + risk engine (3 ms) | `structurer_bakeoff_results.json`, `time_to_detection.json` |
| C6 | ASR WER vs latency, 12 backends | `docs/benchmarks/asr_bakeoff_results.json` |

C6 carries a caveat that must stay in the caption: **only two reference
utterances.** A WER chart invites more confidence than that sample supports.

### 3.3 App screenshots — **this is what you need to procure**

All routes run against the **mock adapter** — no backend, no database. The
20-patient corpus is synthetic, so there is no PHI and no consent question.

```bash
cd web && npm install && cp .env.example .env.local && npm run dev
```

Confirm `NEXT_PUBLIC_MP_SOURCE=mock` in `.env.local`, then open
`http://localhost:3000`.

**Capture settings for every shot:** viewport **1600×900**, device pixel ratio
**2** (so the PNG lands at 3200×1800), browser chrome hidden, no cursor, no
devtools. Same window size for all of them — mismatched crops are the fastest
way to make a deck look assembled rather than designed.

| ID | Route | State to set up | Must be visible | Slide |
|---|---|---|---|---|
| **A1** | `/board` | Normal load, let it settle ~30s so cadence timers show real values | ≥8 queue cards, a mix of red/amber/green, the three time facts per card | **5 (hero)** |
| A2 | `/board` | Set R=3 in `/control` first, wait for arrivals | Same framing as A1, visibly denser queue | 14 |
| A3 | `/card/P-01` | `deteriorates_while_waiting` | Confidence band, the **opposing factor**, the locked acuity slot | 9 |
| A4 | `/card/P-08` | `ood_abstention` | `AbstentionCard` — "no colour given", top of list | 10 |
| A5 | `/card/P-11` | `neonate_fever_floppy` | Age-stratified thresholds differing from adult | 12 |
| A6 | `/card/P-14` | `adult_stroke_redflag` | `RedFlagBanner` at full width | 13 |
| A7 | `/card/P-05` | `spo2_bias_dark_skin` | A **normal SpO₂** that grants no de-escalation | 13 |
| A8 | `/card/P-06` | `stale_vitals_3h` | `VitalChip` showing expired validity | 12 or 13 |
| A9 | `/card/P-09` | Open `OverrideDialog`, mid-entry with a reason typed | The dialog over the card, reason field populated | 11 |
| A10 | `/audit` | After performing the A9 override so the entry is real | Hash-chained entries, the chain visibly linking | **11 (dark)** |
| A11 | `/audit` | Scroll to trust panel / model card | Model card section | 16 or 20 |
| A12 | `/intake` | Step 1 | Language choice — Hindi / English / both | 4 |
| A13 | `/intake` | A question step in the age-aware tree | Branch options, large tap targets | 4 or 7 |
| A14 | `/intake` | Voice active | Mic listening state, live transcript | 7 |
| A15 | `/hall` | Let a few tokens populate | **Token numbers only — no names, no acuity** | 2 or 4 |
| A16 | `/control` | R slider raised to 3 | Slider, surge rate, sim speed | 14 |
| A17 | `/counter` | Mid vitals entry | Vitals counter with a measurement in progress | 4 |
| A18 | `/` | Top of landing | Hero | 1 (optional) |

**A15 matters more than it looks.** The public display showing tokens and no
acuity is the privacy claim made visually — it is the fastest way to show a
judge that the design took DPDP seriously rather than writing a paragraph
about it.

### 3.4 Video frames — a shortcut, with a check

`web/public/media/videos/clips/` holds 13 clips including `nurse-board.mp4`,
`nurse-override.mp4`, `red-flag-response.mp4`, `surge-arrivals.mp4`,
`voice-interaction.mp4`, `age-stratification.mp4`.

```bash
ffmpeg -i web/public/media/videos/clips/nurse-board.mp4 -vf "select=eq(n\,120)" -vframes 1 out.png
```

**Verify before relying on these:** confirm each clip is a real screen capture
of the running app and not a motion-graphic reconstruction. If they are
reconstructions, they are fine as ambient slide backgrounds but must not be
captioned as product screenshots. If they are real captures, `nurse-board.mp4`
and `surge-arrivals.mp4` can supply A1/A2 directly, and embedding a 4-second
loop of `surge-arrivals.mp4` on slide 14 will land better than a still.

### 3.5 What not to procure

- **No stock hospital photography.** It is the visual signature of a deck with
  nothing real to show, and this deck has a working product. If a human moment
  is genuinely needed, the mascot renders in §3.1 are yours and licensed.
- **No re-themed screenshots.** See §1.4.
- **No real patient data, ever** — the corpus is synthetic and that is a
  strength worth stating on slide 15, not a gap to paper over.

---

## 4. Instructions to give Claude

> Build a 20-slide 16:9 HTML/CSS deck for MediPilot, following
> `docs/paper/ppt_design_brief.md` exactly.
>
> - One `<section class="slide">` per slide, 1280×720 CSS px, `@media print`
>   rules for A4 landscape so it exports clean.
> - Use the tokens in §1.1 as CSS custom properties. Obey the colour rule in
>   §1.1: purple is chrome, acuity colours are meaning.
> - Every heading gets the uppercase Inter treatment on a 1pt purple rule (§1.2).
> - Port `.mpbox`, `.mpthesis`, `.mpcode`, `.mpwarn` from §1.3.
> - Screenshots go in the standard frame from §1.4 item 3, never bled to the
>   edge except on slide 5.
> - Inline the diagram SVGs from §3.1 rather than `<img>`-ing them, so they
>   inherit `currentColor` and stay crisp.
> - Build charts C1–C6 as inline SVG from the JSON in §3.2. Do not hardcode
>   numbers you have not read out of those files.
> - Follow the slide plan in §2. One claim per slide. If a slide needs more
>   than ~40 words of body text, it is two slides.
> - Leave a labelled placeholder `<div class="shot" data-id="A3">` wherever an
>   image from §3.3 has not been captured yet, so the deck is reviewable before
>   the screenshots exist.
>
> Every number must trace to a file. If you cannot find a number in the repo,
> leave it as `[TK]` and list it at the end — do not estimate.

---

## 5. Numbers you may use, with their sources

Copied from the proposal so the deck cannot drift from it.

| Claim | Value | Source |
|---|---|---|
| ESI mistriage rate | 32.2% | literature, cited in proposal §1 |
| Epic Sepsis Model AUC | 0.63 (marketed 0.76–0.83), 38,455 hospitalisations | proposal §1 |
| Epic sensitivity / alert burden | 33% / 109 alerts per true positive | proposal §1 |
| Occult hypoxaemia | 11.7% vs 3.6% (17% / 6.2% multicentre) | proposal §1 |
| Mean head start | **21.6 min** (median 17.5, max 55), 16/20 patients | `time_to_detection.json` |
| Red-threshold head start | 6.9 min, 8/20 patients | same |
| Serving latency | p50 3.0 ms, p95 4.3, p99 8.0 | same |
| Gates passed | **7/8** fresh split (8/8 own split) | `risk_engine_bakeoff_results.json` |
| Gate failed | `beats_handcoded_baseline` | same |
| Neonate FNR | 0.195, CI 0.075–0.325, n₊=41 | `metrics.json` |
| Audit fields | 17 substantive + 2 chain = 19 | `backend/triage/audit_log.py` |
| Test suite | 278 passed, 4 failed (3 need a regenerable split, 1 stale assertion) | `docs/README.md` §4 |
| Unit economics | < Rs. 5/encounter — **illustrative, no pilot, no agreed price** | proposal §9 |

The last row must keep its caveat on the slide, not just in the notes.
