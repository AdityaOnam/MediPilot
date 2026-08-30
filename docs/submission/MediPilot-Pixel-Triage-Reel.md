# MediPilot — The Pixel Triage Reel

**Production shot list · Team 01 BIT · IIT Patna · Accenture Innovation Challenge 2026 · Round 2**
The demo film. Every generated shot is **pixel art** — no real hospital, no real people. See
`README.md` for the system this film is about.

| | |
|---|---|
| **Runtime** | ~6 min 30 s |
| **Aspect** | 16:9 · 1920×1080 · **every clip, no exceptions** |
| **Frame rate** | 24 fps project-wide |
| **Flow clips** | 16 (`F-01` … `F-16`) — generated in Google Flow |
| **Your recordings** | 9 (`R-01` … `R-09`) — the real app, real routes, real data |
| **Graphics cards** | 4 (`G-01` … `G-04`) — numbers, all from the config file |
| **Architecture cards** | 3 (`A-01` … `A-03`) — the 30–40 s technical block |
| **Style** | Nintendo DS era JRPG. Pokémon *Diamond/Pearl* overhead tile world, *Black/White* camera moves and sprite animation. |

---

## 00 · The five rules

**1 · No real hospital, no real people. Pixel sprites only.**
Every human in this reel is a chunky 2D sprite with no facial detail. This is not a stylistic
whim — the content rules in `CONTENT_PROMPTS.md` forbid photoreal synthetic patients and
clinicians, because a photoreal Indian ED that never existed is a claim we cannot support. Pixel
art states plainly that the *room* is a reconstruction while the *numbers* are not.

**2 · Flow never renders the MediPilot interface.**
Video models reconstruct screens as plausible-looking texture: numbers drift between frames,
labels come out as near-words. Since the whole claim of this demo is that the numbers are real,
one hallucinated screen undoes it. So in every Flow prompt, kiosk and wall screens are **turned
away, at a grazing angle, or showing abstract pixel bars and blocks with no letterforms**.
Anything a viewer needs to *read* comes from an `R-` recording. Flow supplies the room, the
sprites and the motion. The two halves never overlap — which is exactly what makes them cuttable.

**3 · No acuity word or colour is ever shown on a patient-facing surface.**
`DESIGN_SYSTEM.md` §9 and the R2 plan both bind this. In the pixel world:
- Zone colour-coding on the **floor and walls** is fine — it is a real AIIMS-ATP convention and
  it is staff wayfinding, not a label on a person.
- **No sprite ever wears a band.** No red glow over a patient, no colour badge, no floating
  acuity chip above anyone's head. Ever.
- The public hall screens show **token-shaped blocks only**.

This is worth saying on stage: *"there is a whole screen in this system whose main design
requirement is what it refuses to display."*

**4 · The mascot is patient-side only.**
MediPilot may appear on the kiosk housings, in the lounge, and on the hall display. It is
**banned from the nurse bay and from any frame where a decision is being made** —
`DESIGN_SYSTEM.md` §2, enforced in our code by a throw. Keep the rule visible in the film too.

**5 · Every number on screen comes from `demo/reel.config.json` (§07) or from a recording.**
Nothing is invented in a prompt. If a graphic states a figure, that figure exists in the config
file with a source tag, and the config is the single place it gets corrected.

---

## 01 · The department, defined once

Everything is one rectangle, viewed from a fixed overhead three-quarter angle. Corners run
**clockwise from the north-east: A → B → C → D.**

```
     D (NW)                       NORTH                        A (NE)
     +--------------------------------------------------------------+
     |  STAFF WORK SPACE      |                 |  WAITING STATION 1 |
     |  lockers, trolleys     |                 |  green zone        |
     |                        |   KIOSK ROW     |--------------------|
WEST |  WAITING LOUNGE        |   6 MediPilot   |  WAITING STATION 2 | EAST
     |  benches, seated       |   machines      |  red / yellow zone |
     |  sprites, mascot decal |   in a line     |--------------------|
     |                        |                 |  NURSE BAY         |
     |                        |                 |  bench + 4 screens |
     |                        |                 |  mounted above     |
     |------------------------+-----------------|  RESUS BAYS x4     |
     +--------------------------------------------------------------+
     C (SW)                       SOUTH                        B (SE)
```

| Zone | Contents | Appears in |
|---|---|---|
| **A · north-east** | Two waiting stations, colour-banded floor tape (green zone / red-yellow zone) | F-01, F-08, F-10, F-15, F-16 |
| **B · south-east** | Four resuscitation bays, curtains, monitor trolleys | F-01, F-14, F-15 |
| **Beside B** | The **nurse bay** — a long bench, staff sprites, four wall screens mounted above it | F-11, F-12, F-13 |
| **Centre** | The **kiosk row** — six MediPilot machines in a straight line, each with a big green button and a screen angled away from camera | F-04 … F-08 |
| **C/D · west** | Waiting lounge (benches, seated sprites, MediPilot decal on the wall) and staff work space | F-02, F-10, F-16 |

**Hold this map.** Every Flow prompt below names its zone so the geography stays coherent across
sixteen separately-generated clips. A viewer should be able to draw this rectangle from memory by
the end of the reel.

---

## 02 · The story, in one paragraph

A quiet morning department. Doors open and thirty patients arrive inside forty minutes. They
queue at six MediPilot kiosks and answer a spoken, branching triage conversation — one of them,
**Token 205**, a 45-year-old man with mild chest discomfort he thinks is acidity. He is banded
**Yellow**, sent to a counter for vitals, and sits down to wait. Twenty-nine other people are
triaged around him in parallel; five are routed straight to a nurse. Eighteen minutes into his
wait — with the nurse registering new arrivals and nobody watching him — **the queue re-orders
itself.** His respiratory rate has climbed across three readings, his SpO₂ has fallen, and the
system escalates him **Yellow → Red on its own**, with the reasoning on the card and one factor
arguing against. A nurse walks him into a resus bay. Then: what the system refuses to do under
load, what it wrote into the audit ledger, and how it is built.

**The one thing this reel exists to show:** *the nurse did nothing wrong, and the patient still
got worse — and something was watching.*

---

## 03 · Timeline — the edit order

Cut everything **straight**. The only cross-dissolve in the reel is into the architecture block
at ~4:05.

| # | ID | Src | Len | Beat |
|---|---|---|---|---|
| 1 | `F-01` | Flow | 7 s | Overhead establish — the whole rectangle, quiet |
| 2 | `F-02` | Flow | 6 s | Push into the waiting lounge, four seated sprites |
| 3 | `G-01` | Card | 8 s | Title: **MediPilot** · PatientTriage.ai · SIMULATED DATA |
| 4 | `F-03` | Flow | 7 s | Doors open. Sprites stream in from the west |
| 5 | `F-04` | Flow | 7 s | A queue forms at the kiosk row |
| 6 | `F-05` | Flow | 7 s | Hero sprite steps up, presses the green button |
| 7 | `R-01` | Rec | 25 s | `/intake` — welcome → language → companion → human offer → consent |
| 8 | `F-06` | Flow | 6 s | Over-shoulder: hero speaking to the kiosk, screen angled away |
| 9 | `R-02` | Rec | 35 s | `/intake` — the spoken conversation, branch questions, pain, readback, **token + counter** |
| 10 | `F-07` | Flow | 7 s | Token slip prints; hero takes it and turns toward the counter |
| 11 | `F-08` | Flow | 7 s | Wide overhead — all six kiosks working at once, queue moving |
| 12 | `G-02` | Card | 10 s | **Throughput card** — 30 patients / 40 min, the split, the redirects |
| 13 | `R-03` | Rec | 15 s | `/hall` — token numbers only, "being called to Counter 3" |
| 14 | `F-09` | Flow | 7 s | Counter station: cuff and oximeter, staff sprite taking vitals |
| 15 | `R-04` | Rec | 25 s | `/counter` — pull the token, enter the vitals, band recomputes |
| 16 | `F-10` | Flow | 7 s | Hero sits in the lounge. A wall clock sprite ticks |
| 17 | `R-05` | Rec | 20 s | `/board` — the queue, three time facts per card, cadence counting down |
| 18 | `F-11` | Flow | 6 s | Nurse bay: staff at the bench, backs to camera, wall screens ticking |
| 19 | `R-06` | Rec | 25 s | **`/board` at ×60 — Token 205 rises to the front.** The money shot |
| 20 | `F-12` | Flow | 6 s | A calm alert glyph appears above the bench; a nurse sprite's head turns |
| 21 | `R-07` | Rec | 30 s | `/card/P-05` — three channels, the opposing factor, conformal set |
| 22 | `F-13` | Flow | 7 s | Nurse sprite crosses the floor to the hero and gestures east |
| 23 | `F-14` | Flow | 7 s | Hero walks into a resus bay at B; the curtain closes |
| 24 | `G-03` | Card | 10 s | **The refusal card** — what surge may not do |
| 25 | `R-08` | Rec | 25 s | `/control` — move **R**, board re-sorts, `0 moved down · structurally 0` |
| 26 | `F-15` | Flow | 7 s | Overhead at 3× load — dense, still orderly |
| 27 | — | — | 1 s | **Cross-dissolve** (the only one) |
| 28 | `A-01` | Card | 12 s | Architecture — perception → fixed table → band engine |
| 29 | `A-02` | Card | 12 s | Stack, and the bake-off numbers |
| 30 | `A-03` | Card | 12 s | The six invariants |
| 31 | `R-09` | Rec | 15 s | `/audit` — hash chain, the 16-field record verbatim |
| 32 | `F-16` | Flow | 7 s | Back to the opening frame. Calm. One token slip left on a bench |
| 33 | `G-04` | Card | 10 s | End card — team, SIMULATED DATA, what we do **not** claim |

**Totals** — Flow 108 s · recordings 215 s · cards 64 s ≈ **6 min 27 s**.

---

## 04 · Before you generate anything: the Flow set-up

Same workflow that produced the mascot sheet in `CONTENT_PROMPTS.md` Part 0 — **consistency comes
from saved Characters, not from re-attaching files.**

### Build these four Characters first, in this order

| ID | Character | Built from | Used by |
|---|---|---|---|
| `CH-ROOM` | **Style plate** — a still of the empty department, overhead, correct palette | Generate from the `F-01` prompt as a *still* first, approve it, save it | Every clip. This is the look bible |
| `CH-HERO` | **Token 205** — adult male sprite, mid-40s, olive-green shirt, dark trousers, small satchel | Still, three-pose sheet (front / side / back) | F-05, F-06, F-07, F-10, F-13, F-14 |
| `CH-NURSE` | **Nurse sprite** — teal scrubs, short dark hair, lanyard, no face detail | Still, three-pose sheet | F-11, F-12, F-13 |
| `CH-KIOSK` | **MediPilot machine** — waist-high pedestal, angled screen, large green button, small MediPilot decal on the housing | Still, single object, three-quarter view | F-04 … F-08 |

**Character Info to paste for `CH-HERO`:**

> A pixel-art sprite of an adult man in his mid-forties, rendered in Nintendo DS era JRPG style:
> roughly 48 pixels tall, chunky uncleaned pixels, no anti-aliasing, four-frame walk cycle, black
> 1-pixel outline, flat cel colours with a single dither band for shadow. Olive-green short-sleeve
> shirt, dark grey trousers, a small brown shoulder satchel. His face is two dark pixel eyes and
> nothing else — no mouth, no nose, no expression detail. He moves calmly and a little heavily. He
> is never rendered in 3D, never photorealistic, never with lighting effects or glows.

Write the equivalent for `CH-NURSE` and `CH-KIOSK` before generating a single video.

### Which Flow mode for what

| Want | Mode |
|---|---|
| Any still (the four Characters, the style plate) | Image generation, Character selected |
| A clip that must match an approved still exactly | **Frames to Video** — upload the still as first frame |
| A looping ambient clip (`F-01`, `F-16`) | Frames to Video, **same image as first and last frame** |
| A clip from nothing | Text to Video — avoid; it re-rolls the look and burns credits |

**Lean on Frames-to-Video.** Generate the still, approve it, then ask the model only for motion.
Text-to-video re-rolls the palette and the pixel scale every time, and sixteen clips at slightly
different pixel scales read as sixteen different games.

### Credit discipline

Settle `F-01` completely first — it is the style plate and everything inherits it. Then generate
`F-05`, `F-06`, `F-11` and `F-12`, because those carry the story. `F-02`, `F-09`, `F-15` and
`F-16` are ambience and can be cut if credits run out. Re-roll any clip at most three times; if
the third is wrong, the prompt is wrong, not the model.

---

## 05 · The global spec block

**Paste this verbatim at the end of every single Flow prompt below.** It is what holds sixteen
separate generations together.

```
STYLE: 2D pixel art, Nintendo DS era JRPG, in the visual tradition of Pokemon Diamond/Pearl
and Pokemon Black/White. Overhead three-quarter tile-based perspective. Chunky visible pixels
with a consistent pixel grid, hard edges, NO anti-aliasing, NO gradients except ordered
dithering. Limited flat palette: warm off-white floors, muted teal and sage walls, soft brown
wood benches, grey-blue equipment, one accent of deep red used ONLY on floor tape and signage.
Black 1-pixel outlines on all sprites and props. Character sprites are small, 32-48 pixels tall,
with two-pixel dot eyes and no other facial detail. Sprite animation is deliberately low frame
rate, 8-12 frames per second, stepped not smoothed, over 24 fps footage.
CAMERA: locked, or a slow perfectly straight horizontal or vertical pan along the tile grid, in
the manner of a Nintendo DS overworld camera. No handheld, no roll, no dolly zoom, no rack focus.
The shot begins and ends on settled framing with no motion across the cut.
FORMAT: 16:9 widescreen, 1920x1080, 24 fps.
NEGATIVE: no photorealism, no 3D render, no cel-shaded 3D, no anime illustration, no smooth
vector art, no legible on-screen text anywhere, no readable user interface, no dashboards facing
camera, no letterforms or numbers on any screen, no floating UI overlays, no health bars, no
colour auras or glows around characters, no lens flare, no depth-of-field blur, no motion blur,
no slow motion, no logos, no blood, no gore, no injury detail, no distressed or screaming faces,
no real hospital branding, no identifiable human faces.
```

**Two things I could not verify for you.** Flow's clip length, aspect and frame-rate options move
between model releases — confirm the 8 s / 16:9 / 24 fps assumptions in the tool before generating
all sixteen. And I cannot test-render these, so treat `F-01` as the look test: if the room, the
palette and the pixel scale are right there, the rest of the reel inherits them.

### The finishing pass that makes it look like one game

Video models will not hold a true pixel grid across clips — some come back at an effective
64-pixel scale, others at 90. Fix it in the edit, once, on every Flow clip:

1. Scale the clip **down** to 480×270 with **nearest-neighbour** (not bilinear) sampling.
2. Scale it back **up** to 1920×1080, again **nearest-neighbour**.
3. Optional: a posterise pass to knock stray anti-aliased pixels back onto the palette.

Four-pixel-wide pixels, hard edges, identical across all sixteen clips. This step is not optional
— it is the difference between "pixel-art-styled video" and "a game".

---

## 06 · The sixteen Flow prompts

Each entry gives its zone, its length, what to attach, where to trim, and the prompt. **Append the
§05 global spec block to every one.**

---

### `F-01` · Establish — the department at rest
**Zone** whole rectangle · **7 s** (generate 8, trim both ends) · **Attach** `CH-ROOM`, `CH-KIOSK`
**Cut on** the settled wide frame · **Also generate as a still first — this is the style plate**

> A wide overhead three-quarter view of an entire hospital emergency department, drawn as a
> single tile-based pixel-art map, like the interior of a large building in a Nintendo DS
> role-playing game. The room is a rectangle. In the far north-east corner, two waiting areas
> separated by a low partition, each with rows of wooden benches, one area edged with green floor
> tape and one edged with deep red floor tape. Along the south-east edge, four curtained treatment
> bays with equipment trolleys. Beside them a long staff bench with four small wall-mounted
> screens above it, all of them angled away from the camera so nothing on them is readable — they
> show only abstract blocks and bars of colour. Down the centre of the room, a straight line of
> six identical waist-high machines, each with an angled screen turned away from camera and a
> large green button on top. To the west, a waiting lounge with benches and a friendly robot
> character decal on the wall, and beyond it a staff work area with lockers and trolleys.
> Morning light falls through high windows onto a warm off-white tiled floor.
> MOTION: the department is quiet and almost empty. Two staff sprites in teal move slowly along
> the south wall. A ceiling fan turns. Dust motes drift in the window light. The camera is locked
> and does not move. Nothing dramatic happens.

---

### `F-02` · The lounge, before
**Zone** C/D west · **6 s** · **Attach** `CH-ROOM` · **Cut on** the end of the pan

> A slow, perfectly straight horizontal camera pan across a hospital waiting lounge rendered as a
> pixel-art tile map, overhead three-quarter view. Rows of brown wooden benches. Four small
> character sprites sit spaced far apart — one reading, one holding a bag on their lap, one with a
> child sprite beside them, one asleep against the wall. A friendly red robot character decal is
> painted on the wall behind them. A water cooler and a potted plant in the corner.
> MOTION: the camera pans left to right along the tile grid at a slow constant speed and comes to
> a complete stop. The seated sprites make small idle animations — a breathing bob, a page turn.
> The room is calm and underpopulated.

---

### `F-03` · The doors open
**Zone** west entrance → centre · **7 s** · **Attach** `CH-ROOM` · **Cut on** the moment the queue
first touches the kiosk row

> An overhead three-quarter pixel-art view of the west entrance of a hospital emergency
> department. Double glass doors slide open. A steady stream of small character sprites walks in
> from outside — adults, an elderly sprite with a walking stick, a parent carrying a small child
> sprite, someone supported by a companion. They spread into the room and move east toward a line
> of machines in the centre.
> MOTION: sprites enter continuously in ones and twos with a stepped low-frame-rate walk cycle.
> The camera is locked. The room fills visibly but without panic — nobody runs, nobody collides.
> The tone is busy, not chaotic.

---

### `F-04` · The queue forms
**Zone** centre kiosk row · **7 s** · **Attach** `CH-ROOM`, `CH-KIOSK` · **Cut on** the settled queue

> An overhead three-quarter pixel-art view of a straight row of six identical waist-high
> self-service machines in the middle of a hospital floor. Each machine has an angled screen
> turned away from the camera and a large green button on its top surface. A small friendly red
> robot decal is printed on the side of each housing. Character sprites form six short orderly
> queues, one per machine, standing on floor markers.
> MOTION: sprites shuffle forward one tile at a time as each machine frees up. One sprite steps
> away from a machine holding a small white paper slip and walks east. The camera is locked. The
> screens on the machines show only soft abstract blocks of colour, never letters or numbers.

---

### `F-05` · Token 205 steps up
**Zone** centre, third kiosk · **7 s** · **Attach** `CH-HERO`, `CH-KIOSK`, `CH-ROOM`
**Cut on** the frame the button lights · **This clip cuts directly into `R-01`**

> A medium overhead three-quarter pixel-art shot of a single self-service machine on a hospital
> floor. An adult male sprite in an olive-green shirt with a brown shoulder satchel — the saved
> character — walks up to it, stops, hesitates for a beat with one hand resting on his chest, then
> reaches out and presses the large green button on top of the machine.
> MOTION: four-frame walk cycle in, a two-frame pause, then the press. The green button depresses
> and lights up brighter for the last few frames. The machine screen is angled away from camera
> throughout and shows only abstract colour, no text. The camera is locked. The shot ends on the
> lit button with the sprite standing still.

---

### `F-06` · Talking to the machine
**Zone** centre, third kiosk · **6 s** · **Attach** `CH-HERO`, `CH-KIOSK`
**Cut on** the still frame after he stops speaking · **Sits between `R-01` and `R-02`**

> A closer over-the-shoulder pixel-art shot, still in overhead three-quarter perspective, of the
> same olive-shirted adult male sprite standing at a self-service machine. We see him from behind
> and slightly above. The machine's screen is at a steep grazing angle to the camera, so only its
> edge and a faint abstract glow are visible — nothing on it can be read.
> MOTION: the sprite's head tilts slightly forward as he speaks. Three small stepped pixel arcs
> rise from his mouth toward the machine to suggest speech, then fade. A small ring of pixels on
> the machine's housing pulses gently in time, indicating it is listening. The camera is locked.
> No speech bubble, no text, no letters anywhere.

---

### `F-07` · The token slip
**Zone** centre → east · **7 s** · **Attach** `CH-HERO`, `CH-KIOSK` · **Cut on** the first step east

> An overhead three-quarter pixel-art shot of a self-service machine. A small white paper slip
> feeds out of a slot in the front of the housing. The olive-shirted adult male sprite takes it,
> looks down at it for a beat, then turns and begins walking east across the tiled floor.
> MOTION: the slip emerges in stepped increments. The sprite's take-and-look is three poses, held.
> Then a four-frame walk cycle as he moves out of frame to the right. The paper slip is plain
> white with a faint grey band; no readable number is printed on it. The camera is locked.

---

### `F-08` · Six at once
**Zone** whole centre band · **7 s** · **Attach** `CH-ROOM`, `CH-KIOSK` · **Cut on** the settled wide

> A wide overhead three-quarter pixel-art view of the whole centre of a hospital emergency
> department. All six self-service machines are occupied simultaneously, each with a short queue
> behind it. Sprites cycle through steadily: one steps away with a paper slip, the next steps
> forward, the queue shuffles up one tile. Staff sprites in teal move between the machines and the
> east side of the room.
> MOTION: continuous, overlapping, and rhythmic — the whole row working in parallel rather than
> one at a time. Slightly quicker sprite animation than the earlier shots, to read as throughput.
> The camera is locked. No screen in frame shows readable content.

---

### `F-09` · The vitals counter
**Zone** east, beside the nurse bay · **7 s** · **Attach** `CH-ROOM`, `CH-NURSE`
**Cut on** the settled frame after the cuff inflates · **Sits before `R-04`**

> An overhead three-quarter pixel-art shot of a small measurement counter in a hospital. A staff
> sprite in teal scrubs stands behind it. A seated patient sprite has a blood-pressure cuff on the
> upper arm and a small clip on one fingertip. A boxy grey-blue monitor sits on the counter,
> screen turned away from the camera.
> MOTION: the cuff inflates in three stepped frames and holds. A tiny indicator light on the
> fingertip clip blinks slowly. The staff sprite leans in, then straightens. The camera is locked.
> The monitor shows only an abstract pulsing bar, never numbers or letters.

---

### `F-10` · Sitting down to wait
**Zone** A, red/yellow waiting station · **7 s** · **Attach** `CH-HERO`, `CH-ROOM`
**Cut on** the wall clock's second full tick

> An overhead three-quarter pixel-art view of a hospital waiting area with rows of wooden benches
> on a floor edged with deep red tape. The olive-shirted adult male sprite walks in, sits down on
> a bench near the wall, and settles. Six or seven other sprites are already seated around him,
> spaced apart. A round analogue wall clock hangs above them.
> MOTION: the sprite sits in three stepped poses, then goes into a slow idle bob with one hand
> resting on his chest. The clock's hand advances in visible discrete ticks. Nobody else moves
> much. The camera is locked. The shot is deliberately uneventful and a little too still.

---

### `F-11` · The nurse bay
**Zone** beside B · **6 s** · **Attach** `CH-NURSE`, `CH-ROOM`
**Cut on** the settled frame · **NO mascot anywhere in this shot — see rule 4**

> An overhead three-quarter pixel-art view of a long staff bench in a hospital emergency
> department, with four small screens mounted on the wall above it. Two staff sprites in teal
> scrubs stand at the bench with their backs to the camera, working. A third crosses behind them
> carrying a clipboard.
> MOTION: the wall screens flicker through abstract blocks and bars of colour that change every
> second or so — no letters, no numbers, nothing readable. The staff sprites make small stepped
> working animations. Nobody looks up. The camera is locked. There is no robot character or mascot
> anywhere in this shot.

---

### `F-12` · Something is noticed
**Zone** beside B · **6 s** · **Attach** `CH-NURSE`, `CH-ROOM`
**Cut on** the held frame with the nurse turned · **Cuts directly into `R-07`**
**No siren, no flashing, no red wash. Calm-serious is the whole brief.**

> An overhead three-quarter pixel-art view of the same staff bench with four screens above it. One
> of the screens changes: its abstract blocks reorganise and a small solid chevron shape appears
> at its top edge, pointing upward. A single soft pixel glyph — a small filled triangle — fades in
> above the bench.
> MOTION: one nurse sprite in teal scrubs, previously facing the bench, turns her head and then
> her body toward the screen in three stepped poses, and holds. Nothing flashes. Nothing pulses
> rapidly. There is no alarm colour wash over the room, no red lighting, no strobe. The change is
> quiet and the reaction is immediate but unhurried. The camera is locked.

---

### `F-13` · Crossing the floor
**Zone** nurse bay → A → east · **7 s** · **Attach** `CH-NURSE`, `CH-HERO`, `CH-ROOM`
**Cut on** the moment both sprites face east

> An overhead three-quarter pixel-art view of a hospital floor. A nurse sprite in teal scrubs
> walks briskly but calmly from a staff bench, diagonally across the tiled floor, to a waiting
> area edged with red floor tape. She stops in front of a seated olive-shirted adult male sprite,
> crouches to his level for a beat, then stands and gestures with an open hand toward the east
> side of the room. He rises from the bench.
> MOTION: a purposeful four-frame walk cycle, a three-pose crouch, a clear open-handed gesture,
> then both sprites turn to face east and hold. Other seated sprites do not react. The camera is
> locked. No colour badge, glow or marker appears above either character.

---

### `F-14` · Into the bay
**Zone** B, resus bays · **7 s** · **Attach** `CH-HERO`, `CH-NURSE`, `CH-ROOM`
**Cut on** the closed curtain, held

> An overhead three-quarter pixel-art view of a row of four curtained treatment bays along the
> south-east wall of a hospital. A nurse sprite in teal scrubs and an olive-shirted adult male
> sprite walk together into the nearest bay. Equipment trolleys and a wheeled monitor stand
> waiting inside it. A second staff sprite steps in behind them.
> MOTION: the two sprites walk in with a steady four-frame cycle. The curtain draws across in four
> stepped frames and comes to rest. The frame holds on the closed curtain for a full second. The
> camera is locked. Nothing inside the bay is visible once the curtain closes — no medical
> procedure, no injury, no distress is shown at any point.

---

### `F-15` · Three times the load
**Zone** whole rectangle · **7 s** · **Attach** `CH-ROOM`, `CH-KIOSK` · **Cut on** the settled wide

> A wide overhead three-quarter pixel-art view of the whole hospital emergency department,
> identical framing to the opening establishing shot, but now densely populated. Every bench in
> both waiting areas is occupied. All six central machines have queues. Staff sprites in teal move
> constantly between the machines, the counter and the treatment bays.
> MOTION: many small sprites moving at once, in ordered lanes along the tile grid — busy but never
> chaotic, no collisions, no crowding into a mass. Queues stay in straight lines. The camera is
> locked. The room reads as under heavy load and still functioning.

---

### `F-16` · Back to the start
**Zone** whole rectangle · **7 s** · **Attach** `CH-ROOM` · **Loop: same first and last frame**
**Cut on** the settled wide — this is the last motion in the reel

> A wide overhead three-quarter pixel-art view of a hospital emergency department, exactly the
> same framing and lighting as the opening establishing shot. The room is quiet again and mostly
> empty. On one bench in the north-east waiting area, a single small white paper slip has been
> left behind.
> MOTION: almost none. A ceiling fan turns. One staff sprite crosses slowly along the south wall.
> Light shifts by a barely perceptible amount. The camera is locked and the first and last frames
> match so the shot can hold or loop under the end card.

---

## 07 · The config file

Create `demo/reel.config.json`. **Every number that appears in a graphics card comes from here**,
so a correction is one edit and not a re-render hunt. Fields marked **`[CLIN]`** need the clinical
reviewer's sign-off before the reel is cut — bundle them into the one review sitting the R2 plan
§16 already calls for.

```jsonc
{
  "meta": {
    "reel": "MediPilot Pixel Triage Reel",
    "version": "0.1",
    "dataSource": "SIMULATED",
    "note": "Every figure below is synthetic or measured on synthetic data. No clinical claim.",
    "clinicalSignOff": { "reviewer": null, "date": null, "status": "PENDING" }
  },

  "hero": {
    "encounterId": "P-05",
    "token": "205",
    "caseId": "deteriorates_while_waiting",
    "ageYears": 45,
    "sex": "M",
    "stratum": "adult",
    "complaint": "Mild chest discomfort, \"probably just acidity\"",
    "bandAtArrival": "YELLOW",
    "bandAfter": "RED",
    "escalationAtMin": 18,
    "escalationCause": "MODEL",
    "counter": "Counter 3",
    "_comment": "Do NOT type this patient's vitals into a graphic. Screen-record them from the running app in R-04/R-05/R-07 so the numbers on screen are the numbers the engine used."
  },

  "throughput": {
    "_comment": "The G-02 card. Set these from one scripted run of the seeded corpus + surge fillers, not from memory.",
    "arrivalsTotal": 30,                    // [CLIN] plausible for the stated 500/day design point
    "windowMinutes": 40,
    "medianIntakeMinutes": 3,               // [CLIN] kiosk conversation, start to token
    "concurrentKiosks": 6,
    "routedToNurseImmediately": 5,          // red-flag interrupts + human-lane requests
    "bandSplit": { "red": 4, "yellow": 11, "green": 13, "abstained": 2 },
    "abstentionRatePct": 6.7,               // = abstained / arrivalsTotal
    "escalatedWhileWaiting": 3,
    "escalatedOnTimeAlone": 1,              // wait-ceiling breach, no vital changed
    "deEscalatedAutonomously": 0            // structurally 0 — Invariant 1. NEVER edit this.
  },

  "cadence": {
    "_comment": "From config/band_cadence.yaml. Two clocks plus a ceiling. Minutes.",
    "red":       { "rescoreSec": 60,  "remeasureMin": 5,  "ceilingMin": 0   },
    "yellow":    { "rescoreSec": 300, "remeasureMin": 30, "ceilingMin": 60  },
    "green":     { "rescoreSec": 300, "remeasureMin": 60, "ceilingMin": 120 },
    "abstained": { "rescoreSec": 300, "remeasureMin": null, "ceilingMin": 15 }
  },

  "surge": {
    "multiplier": 3,
    "stretched": { "yellowRemeasureMin": 45, "greenRemeasureMin": 90 },
    "held":      { "redRemeasureMin": 5 },
    "refusals": [
      "may not raise R to reduce alarm volume",
      "may not resolve abstentions by guessing",
      "may not de-escalate anyone to free capacity"
    ]
  },

  "threshold": {
    "R": 500,
    "pStar": 0.002,
    "presets": { "tertiary": 500, "district": 100, "aggressive": 50 }
  },

  "model": {
    "modelVersion": "medipilot-gbdt-v0.2.0",
    "calibrationVersion": "isotonic-perstratum-v0.2.0",
    "strata": 6,
    "corpusSize": 20,
    "invariantTests": 6
  },

  "bakeoff": {
    "_comment": "REAL measured numbers. docs/benchmarks/. Do not round differently on the card.",
    "structurer": {
      "chosen": "groq:openai/gpt-oss-120b",
      "symptomF1": 0.962,
      "redFlagsMissed": 0,
      "forbiddenKeyHits": 1,
      "candidatesEvaluated": 10
    },
    "asr": {
      "chosen": "groq:whisper-large-v3-turbo",
      "meanWer": 0.0,
      "meanLatencyS": 0.298,
      "silenceHallucinations": 0
    }
  },

  "claimsWeDoNotMake": [
    "No clinical claim.",
    "No performance claim against Indian patients.",
    "No causal claim about outcomes.",
    "All data synthetic. Prototype rung of the maturity ladder."
  ]
}
```

**Two rules about this file.**

1. **`deEscalatedAutonomously` is not a tunable.** It is zero by construction — the band engine
   takes `max(model_band, human_floor)`, so the number cannot be anything else. If it is ever
   non-zero the invariant has leaked and the reel is wrong, not the config.
2. **Never put the hero's vitals in here.** Graphics cards state aggregates; individual vitals
   come from screen recordings. The moment a card asserts a heart rate that a viewer cannot see
   the app produce, the reel is making a claim the demo does not back.

---

## 08 · The recordings — `R-01` … `R-09`

Record the browser at exactly **1920×1080**, chrome hidden, **24 fps**, cursor visible. Set the
sim clock from `/control` before each take. Reset to the seeded state between takes so every
rehearsal is identical.

| ID | Route | Len | Do exactly this | Proves |
|---|---|---|---|---|
| `R-01` | `/intake` | 25 s | Welcome → pick English → "I'm here alone" → decline the human offer → both consent toggles on → age 45, male | The human offer comes **before** the machine proceeds alone (R2 §9 / D4) |
| `R-02` | `/intake` | 35 s | Say the opening complaint aloud; let it branch to `chest_pain`; answer 3–4 branch questions by voice; pain scale; readback with dashed borders; confirm; **token 205 + Counter 3 + required vitals icons** | Talk-first triage, branching on the answer, nothing committed until confirmed |
| `R-03` | `/hall` | 15 s | Let it sit. Show the "being called to Counter 3" lane, then the waiting grid | **Token numbers only.** The screen defined by what it refuses to display |
| `R-04` | `/counter` | 25 s | Search token 205, show the owed-vitals list, enter HR / BP / RR / SpO₂ / temp, submit, band recomputes against the adult stratum | Vitals are a station's job, not a triage decision. No override control on this screen |
| `R-05` | `/board` | 20 s | Slow scroll. Hold on one card's `CadenceStrip` — re-scored age, re-measure deadline, ceiling | **Three time facts per card.** The two clocks plus the ceiling |
| `R-06` | `/board` | 25 s | Clock at ×60. Hold wide. Let **205 escalate and physically rise** through the queue. Catch the chevron and the toast | The money shot: a queue a human ordered re-ordering itself |
| `R-07` | `/card/P-05` | 30 s | Channel 1 with the **mandatory opposing factor**; expand Channel 2 for the named reliability discount; Channel 3 narrative; the conformal set; scroll to `LockedAcuitySlot` and **hold on it for 3 full seconds** | The LLM structurally cannot emit a band. This is the architectural argument |
| `R-08` | `/control` | 25 s | Drag **R** from 500 down and back up. Let the mini-census re-sort. Hold on `0 moved down · structurally 0` | Escalation bias demonstrated **live**, not claimed in a deck (§02 gate) |
| `R-09` | `/audit` | 15 s | Hash-chain chip green; expand one override row; scroll all 16 fields verbatim | Override is a medico-legal record, rendered not summarised (§13) |

**`R-07` is the one to rehearse most.** The three-second hold on the locked acuity slot is the
single most important frame in the reel.

---

## 09 · The cards — `G-01` … `G-04` and `A-01` … `A-03`

Build these in the editor over a **still frame exported from `F-01`**, dimmed to ~25 %, so the
cards sit inside the pixel world instead of interrupting it. Set all card type in a pixel/bitmap
face at a whole-number size (8, 16, 24, 32 px) so it stays on the same grid as the footage.

| ID | Len | Content | Pulls from |
|---|---|---|---|
| `G-01` | 8 s | **MediPilot** / PatientTriage.ai / Team 01 BIT · IIT Patna / `SIMULATED DATA` chip, bottom-right, small | — |
| `G-02` | 10 s | `arrivalsTotal` in `windowMinutes` · median intake `medianIntakeMinutes` · `concurrentKiosks` running at once · `routedToNurseImmediately` straight to a nurse · band split · **`0` de-escalated autonomously** | `throughput` |
| `G-03` | 10 s | **What surge is not allowed to do.** The three `refusals`, verbatim, one per line, with the line *"each is blocked in code, not in policy"* | `surge.refusals` |
| `G-04` | 10 s | Team, `modelVersion`, `calibrationVersion`, then `claimsWeDoNotMake` in full | `model`, `claimsWeDoNotMake` |
| `A-01` | 12 s | Three stacked blocks: **the model reports what was said** → **a fixed table decides what it means** → **the band engine assigns and can only escalate.** One arrow between each | R2 plan §10 |
| `A-02` | 12 s | Stack: GBDT + per-stratum isotonic + Mondrian conformal · browser speech + Groq matcher · Next.js / FastAPI · **bake-off**: 10 candidates, chosen F1 `symptomF1`, `redFlagsMissed` red flags missed | `model`, `bakeoff` |
| `A-03` | 12 s | The six invariants, one line each, with `invariantTests` tests noted underneath | R2 plan §04 |

**`G-02`'s last line is the point of the card.** Every other figure on it is throughput; the zero
is the architecture.

---

## 10 · Sound

- Generate every Flow clip **silent** if the option exists. Room tone from sixteen different
  generations will not match.
- Lay **one continuous ambience bed** under the whole reel: a low room hum, distant indistinct
  movement, no voices.
- Optional and effective: a **chiptune** underscore, sparse, in the DS-era register. Drop it out
  entirely for `F-12` → `R-06`, and bring it back on `F-13`. Silence is the loudest tool you have
  at the escalation.
- **Three sounds only**, all under 400 ms, all soft, straight from `DESIGN_SYSTEM.md` §7: a
  rising two-note **escalation chime** on `F-12`, a single soft **tick** on `F-05`'s button press,
  and a low **settle** on `F-07`'s token slip. Nothing else makes noise.
- **No alarm, no siren, ever.** Alarms cause fatigue and the paper says so.

### Voice-over — spine only, ~35 words per beat

Record flat and unhurried. The film is not selling; it is showing.

| Over | Line |
|---|---|
| `F-01`–`G-01` | "A morning shift. Thirty people will arrive in the next forty minutes, and one nurse will meet all of them." |
| `F-04`–`R-02` | "Every patient talks to the machine in their own language. It asks what a nurse would ask, and it branches on the answer." |
| `G-02` | "Six conversations at once. Five people went straight to a nurse. Nobody was de-escalated by a machine — that path does not exist in the code." |
| `F-10`–`R-05` | "This man was correctly assigned Yellow. The nurse did nothing wrong. He then sat down and waited." |
| `R-06` | *(silence — let the card move)* |
| `R-07` | "Eighteen minutes later the queue re-orders itself. His breathing rate rose across three readings. The card shows what drove it, and one factor arguing against." |
| `G-03`–`R-08` | "Under three times the load, this is what the system refuses to do to cope." |
| `A-01`–`A-03` | "The language model reports what was said. A fixed table decides what it means. Only a clinician can move a patient down." |
| `F-16`–`G-04` | "All of this data is synthetic. We make no clinical claim. What we can show you is the architecture that would make one safe." |

---

## 11 · Merge settings — the things that judder if you get them wrong

- **Frame rate is the one that bites.** Screen recorders default to 30 or 60 fps; Flow output here
  is 24. Mixing them without conforming gives visible stutter on every screen clip. Set the
  recorder to 24, or set the project to 30 and generate at 30. **Pick one number and hold it
  everywhere.**
- **Resolution.** Record at exactly 1920×1080 so nothing is scaled. Scaled UI text is the fastest
  way to make a real screen look fake.
- **Colour.** Flow arrives Rec.709, recordings are sRGB — close enough to cut without correction.
  Do not apply a LUT to one and not the other.
- **Trim both ends of every Flow clip.** The first and last few frames of a generation are the
  least stable. Generate at 8 s, use 6–7.
- **Run the §05 nearest-neighbour pass on every `F-` clip and on nothing else.** The recordings
  must stay pin-sharp — their sharpness against the chunky pixel world is what tells the viewer
  which half is real.

---

## 12 · Open items

| # | Item | Owner |
|---|---|---|
| 1 | Fill `demo/reel.config.json` from one scripted run, not from memory | Whoever runs the demo |
| 2 | Clinical sign-off on the four `[CLIN]` fields | The reviewer already identified in R2 §16 |
| 3 | Confirm Flow's clip length / aspect / fps before generating all sixteen | Whoever holds the Flow account |
| 4 | `R-04` needs `/counter` working against whichever adapter you demo on — the live orchestrator does not yet expose `POST /v1/encounter/{id}/vitals`, so **record `R-03`, `R-04` and `/hall` on the mock adapter** unless that endpoint lands first | Backend |
| 5 | Decide the underscore: chiptune or ambience only | Everyone, once, then stop |
