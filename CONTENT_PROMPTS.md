# MediPilot — Content Creation Prompt Pack

For your Google Pro / Google Flow account. Every entry lists **exactly which files to attach**, the prompt to paste, the settings, and the filename to save it under. Produce them in the order given — later prompts attach earlier outputs to hold the character consistent.

Save everything into `C:\Users\HP\Desktop\IITP\Hackathon\temp\medipilot-web\public\media\` under the subfolder named in each entry. Send me the files when they exist and I will wire them in.

---

## Ground rules — read before generating anything

**1. Never generate footage or images of the product UI.** Record the real app instead. Generated fake dashboards in a prototype pitch are a credibility risk that costs far more than the polish they buy, and a judge who spots one will doubt everything else on screen.

**2. Never generate photoreal patients, clinicians, or hospital interiors.** This is a medical product. Photoreal synthetic patients read as deceptive, and a photoreal Indian ED that never existed is a claim you cannot support. Everything human-adjacent stays **stylised illustration or soft 3D**, and faces stay abstracted. Say "illustrated" in the prompt every time.

**3. No real hospital names, logos, badges, or uniforms.** No AIIMS branding, no Accenture branding inside generated art.

**4. The mascot is patient-side only.** Do not generate any asset that places the mascot next to a triage score, an acuity colour, a clinical dashboard, or a nurse making a decision. That rule is in `DESIGN_SYSTEM.md` §2 and it applies to generated content too.

**5. Consistency comes from the saved Flow Character, not from re-attaching files.** See Part 0.

---

# PART 0 — The Flow workflow

**Status: the `MediPilot` Character exists in Flow, built from IMG-01. Consistency is solved. Do not rebuild it.**

## Attachment convention — revised

Wherever a prompt below says *Attach: `A1`, `A2`*, that now means **select the `MediPilot` Character** in Flow instead. The file attachments are the fallback for tools that have no Character feature (the Gemini app, for instance).

```
CHAR  the saved "MediPilot" Character in Flow   <- use this
A1    ...\Accenture Innovation Hackathon\MediPilot.png          (fallback)
A2    ...\public\media\mascot\pose-sheet.png                    (fallback, output of IMG-01)
```

## Keep the saved Character neutral

The Character's reference poses all have **goggles pushed up**. Leave it that way — it is the neutral, canonical MediPilot.

Do **not** use the *"What do you want to change?"* box on the Character page to pull the goggles down. That edits the character itself, and every scene you generate afterwards inherits it. Goggles-down is a *state*, requested per shot, not a property of the character.

## Character Info — paste this into the empty field

Flow uses this to direct the character in scenes. Leaving it blank wastes the feature.

> MediPilot is a friendly robot shaped like a red medical cross, wearing a brown leather aviator cap with pale blue-green goggles, on slim articulated steel-blue limbs. It is a pilot, not a doctor — calm, warm and unhurried, running a checklist and talking you through it. Its movements are small, deliberate and gentle. It stands still most of the time. It never rushes, never panics, never looks alarmed or frightened, and never appears to be in a hurry. When it is listening it pulls the goggles down over its eyes and tilts its head slightly forward; when it is speaking or waiting the goggles are pushed up on the cap. Always rendered as flat 2D cartoon animation with thick uniform black outlines and flat cel colours — never 3D, never photorealistic, never with lighting effects, glows or particles.

## The voice

Flow assigned **Vindemiatrix — female, gentle, mid pitch**. Gentle and mid-pitch fits the brief. Two notes before you commit:

- This voice is only used in **Flow-generated video**, i.e. the pitch film. The live prototype speaks through the browser's own `speechSynthesis`, so the demo does not depend on it.
- Test it on the Hindi lines in Part 3 before relying on it. If the Devanagari comes out mangled, keep the Flow voice for the English pitch narration only and let the live app handle Hindi.

One thing worth deciding on purpose rather than by default: a gentle female voice is the standard setting for assistant products, and it carries a well-worn association of the deferential female helper. MediPilot is explicitly *not* a nurse persona — it announces and confirms and never advises. Either pick the voice deliberately and be able to say why, or audition a neutral or lower-pitched option alongside it. It is a thirty-second experiment and it is the kind of choice a judge on a responsible-AI panel may well ask about.

## What is missing from the pose sheet

The eight poses are consistent — same proportions, same line weight, same reds. Two gaps to fill before the kiosk can be built:

1. **No goggles-down pose.** This is the important one. Goggles coming down over the eyes is the single gesture that says *"I am now listening to you"*, and it is the anchor of the entire voice interface. IMG-02 and VID-01 exist to produce it.
2. **No genuinely unsmiling pose.** The "calm and serious" slot came back smiling. The red-flag interrupt needs a steady, warm, non-smiling face — IMG-03. Push back explicitly with *"neutral mouth, not smiling, calm and kind"*.

Also: every pose carries a soft ground shadow. Fine on the warm kiosk background, wrong everywhere else. `tools/cutout.py --shadow` strips it.

## Which Flow mode for what

| Want | Mode | Model |
|---|---|---|
| A still (all IMG-*) | image generation with the Character selected | Nano Banana 2 |
| A clip from nothing (VID-02, VID-04) | Text to Video, Character selected | Veo |
| A clip that starts from an exact still | **Frames to Video** — upload the still as the first frame | Veo |
| A seamless loop (VID-01, VID-02) | Frames to Video with the **same image as first and last frame** | Veo |

**Frames to Video is the one to lean on.** Generate the still first, approve it, then animate from it. Text-to-video re-rolls the character's appearance every time and burns credits; frame-to-video locks the look and only asks the model to supply motion. For the two looping assets, setting first frame = last frame is what makes the loop actually seamless instead of nearly seamless.

Clips are ~8 seconds. Do not write prompts that need more; VID-03 and VID-05 are deliberately short beats that get cut together afterwards.

## Getting the files out and web-ready

Flow exports opaque PNGs. The app needs transparency so the mascot can sit on warm paper, on dark clinical chrome, and over video.

```bash
python tools/cutout.py split pose-sheet.png --cols 4 --rows 2 --out poses/
```

```bash
python tools/cutout.py cut poses/*.png --shadow --out ../medipilot-web/public/media/mascot/
```

Corner-seeded flood fill, so the mascot's white eyes survive — a plain "remove white" would punch holes in its face. `--shadow` runs a second looser pass for the ground ellipse. `--tol` if the edge is ragged, `--feather 2` if you see a white halo against the dark theme.

Video: download at the highest quality offered, keep the MP4, and hand me the original rather than a re-compressed copy.

## Credit discipline

Video costs far more than stills, and you have a prototype to build. Suggested split: settle every still first (cheap, and they are what the live demo actually uses), then generate **VID-01 and VID-02 only** — those two appear in the running app. Leave VID-03, VID-04, VID-05 until the prototype is finished, because the pitch film should be cut around real screen recordings, and you will not know their timing until then.

Re-roll a still at most three times. If the third is wrong, the prompt is wrong, not the model.

---

# PART 1 — Images (Gemini image generation)

## IMG-01 · Mascot pose sheet ← **make this first**

**Used in:** every patient-facing screen. This is the master reference for all later prompts.
**Attach:** `A1`
**Settings:** 1:1, highest quality, transparent background if offered, otherwise pure white. Generate at the largest size available.
**Save as:** `public/media/mascot/pose-sheet.png`

> Using the attached character as the exact and only reference, create a clean character pose sheet on a plain white background. Keep the character perfectly consistent with the reference: a red medical-cross-shaped robot body, brown leather aviator cap with pale blue-green goggles, articulated pale steel-blue robot arms and legs, bold black cartoon outlines, flat cel-shaded colouring, friendly cartoon style. Same proportions, same colours, same line weight in every pose.
>
> Arrange eight full-body poses in a 4×2 grid, evenly spaced, each fully separated with clear white space between them, no labels or text anywhere:
> 1. Standing at rest, goggles pushed up on the cap, one hand raised in a small friendly wave.
> 2. Listening: goggles pulled down over the eyes, head tilted slightly forward, both hands lowered, calm and attentive.
> 3. Speaking: goggles up, mouth open mid-word, one hand gesturing openly outward.
> 4. Thinking: goggles up, one hand near the chin, eyes glancing upward.
> 5. Calm and serious: no smile, steady neutral expression, standing upright and still, both hands lowered — reassuring and composed, absolutely not frightened, angry, or alarmed.
> 6. Gesturing to one side with an open palm, as if guiding someone toward a person off-frame, warm and welcoming.
> 7. Holding up a small blank paper slip in one hand, smiling gently.
> 8. Resting: eyes closed peacefully, goggles down, standing still, very slight forward lean.
>
> Flat vector cartoon illustration, thick uniform black outlines, no gradients, no background elements, no shadows on the ground, no text.

**If the grid comes out inconsistent,** generate poses one at a time instead, attaching `A1` each time, and use the phrase *"identical character to the reference, only the pose changes"*.

---

## IMG-02 · Listening hero

**Used in:** `/kiosk` K4, the voice screen — the mascot sits at the centre of the cockpit ring.
**Attach:** `A1`, `A2`
**Settings:** 1:1, transparent background, large.
**Save as:** `public/media/mascot/listening.png`

> Using the attached character references, draw the same red cross robot character in a single centred front-facing pose, from the knees up, filling the frame. Goggles pulled down over the eyes, head tilted very slightly forward, expression calm and attentive, both hands relaxed at its sides. It is listening carefully to someone speaking to it. Identical character design, colours, and line weight to the references. Flat vector cartoon, thick black outlines, fully transparent background, no ring or circle around it, no text, no props, no shadow.

---

## IMG-03 · Calm-serious — the red-flag moment

**Used in:** the intake interrupt (K-INT). This is the most emotionally delicate asset in the set. It must read as *steady*, never as alarm.
**Attach:** `A1`, `A2`
**Settings:** 1:1, transparent, large.
**Save as:** `public/media/mascot/steady.png`

> Using the attached character references, draw the same red cross robot character standing upright and completely still, facing forward, from the knees up. Neutral mouth, no smile, eyes open and steady and kind, goggles up. Both arms lowered calmly. The mood is quiet competence and reassurance — a pilot calmly saying "I've got this". Absolutely no alarm, no fear, no urgency, no wide eyes, no sweat drops, no motion lines, no red glow, no warning symbols. Identical character design and colours to the references. Flat vector cartoon, thick black outlines, transparent background, no text.

---

## IMG-04 · Handing over to a person — the Human Lane

**Used in:** `/kiosk` K3 when the patient declines AI processing. This image has to make declining feel like a good outcome, not a rejection.
**Attach:** `A1`, `A2`
**Settings:** 16:9, transparent, large.
**Save as:** `public/media/mascot/human-lane.png`

> Using the attached character references, draw a wide horizontal composition. On the left, the same red cross robot character stands turned three-quarters to the right, one arm extended in a warm open-palm gesture of introduction, smiling gently, goggles up. On the right, a simple friendly abstract human figure — a soft flat silhouette in warm neutral tones with a suggestion of a shoulder bag or a clipboard, no facial features at all, no uniform, no hospital branding, no identifiable ethnicity. The robot is introducing the person, and the person is welcoming. Generous empty space between them. Identical character design and colours to the references. Flat vector cartoon, thick black outlines on the robot, softer edges on the human figure, transparent background, no text.

---

## IMG-05 · Token handover

**Used in:** `/kiosk` K7, token issued.
**Attach:** `A1`, `A2`
**Settings:** 1:1, transparent.
**Save as:** `public/media/mascot/token.png`

> Using the attached character references, draw the same red cross robot character facing forward, holding up a small blank white paper slip in its right hand at chest height, smiling warmly and reassuringly, goggles up, other hand relaxed. The paper slip is completely blank — no numbers, no text, no marks. Identical character design and colours to the references. Flat vector cartoon, thick black outlines, transparent background.

---

## IMG-06 · Night idle

**Used in:** `/board` and `/kiosk` after hours; the low-activity ambient state.
**Attach:** `A1`, `A2`
**Settings:** 1:1, transparent.
**Save as:** `public/media/mascot/resting.png`

> Using the attached character references, draw the same red cross robot character standing still with its eyes closed peacefully, goggles pulled down, arms relaxed at its sides, a very slight gentle forward lean, calm and quiet. It is resting but still present, not asleep on the floor and not switched off. Identical character design and colours to the references. Flat vector cartoon, thick black outlines, transparent background, no stars, no "Z" symbols, no text.

---

## IMG-07 · App icon

**Used in:** favicon, PWA icons, browser tab, the launcher tile.
**Attach:** `A1`
**Settings:** 1:1, 1024×1024, solid background.
**Save as:** `public/media/brand/icon-1024.png`

> Using the attached character as reference, create a simple bold app icon. A single red medical cross shape, front-facing and centred, wearing a small brown leather aviator cap with pale blue-green goggles pushed up on it. No arms, no legs, no face, no eyes — just the cross shape and the cap. Extremely simplified and geometric, heavy black outline, flat colours matching the reference exactly. Centred on a warm off-white background with generous margin. Must remain instantly recognisable at 32 pixels. No text, no gradients, no shadows.

Also export at 512, 192, 180, 32 and 16 px, plus a 512 px version on a transparent background as `icon-mask.png`.

---

## IMG-08 · Social / OG card

**Used in:** the link you hand the judges; WhatsApp and Slack previews of the Vercel URL.
**Attach:** `A1`, `A2`
**Settings:** 16:9, 1200×630.
**Save as:** `public/media/brand/og.png`

> Using the attached character references, create a clean horizontal banner. The red cross robot character stands on the left third, waving, at a comfortable size with plenty of breathing room. The right two-thirds is empty warm off-white space reserved for text that will be added later — leave it genuinely empty. A very subtle pale line-art pattern of aircraft-cockpit instrument dials sits faintly in the background at low opacity, barely visible. Identical character design and colours to the references. Flat vector illustration, no text anywhere in the image.

---

## IMG-09 · Offline state

**Used in:** the degraded banner illustration when the network is down.
**Attach:** none
**Settings:** 1:1, transparent.
**Save as:** `public/media/states/offline.png`

> A simple flat line illustration of a small rugged grey edge-computing box sitting on a desk, with a single steady pale green status light glowing on its front panel, and a thin cable running off the frame that is clearly unplugged at the loose end. The box looks solid, reliable, and calm — it is still working on its own. Minimal flat vector line art, thin uniform black outlines, muted slate-grey and pale-green palette only, transparent background, no text, no warning symbols, no red.

---

## IMG-10 · Model-down fallback

**Used in:** the frozen ATP rule card state.
**Attach:** none
**Settings:** 1:1, transparent.
**Save as:** `public/media/states/rule-card.png`

> A simple flat line illustration of a single printed reference card or laminated checklist sheet, viewed from slightly above at a gentle angle, with a few abstract horizontal lines suggesting printed rows and a small square checkbox beside each. No readable text — the lines are purely abstract marks. The card looks trustworthy, well-used and dependable. Minimal flat vector line art, thin uniform black outlines, muted slate-grey palette with one small amber accent, transparent background, no text.

---

## IMG-11 · Cockpit background texture

**Used in:** a very low-opacity background layer on `/corridor` and `/bench`.
**Attach:** none
**Settings:** 16:9, 2560 px wide, seamless if the tool offers it.
**Save as:** `public/media/textures/cockpit-dark.png`

> An extremely subtle abstract background texture inspired by aircraft cockpit instrumentation: faint concentric dial rings, thin measurement tick marks, and sparse fine grid lines, arranged in a loose asymmetric composition. Very dark charcoal-blue base, with the line work barely a shade lighter than the background — almost invisible, like an embossed pattern seen in dim light. No numbers, no text, no labels, no bright highlights, no glow, no lens flare. Flat, calm, and quiet. It must never compete with content placed on top of it.

---

## IMG-12 · Waiting hall background

**Used in:** `/board`, behind the token numbers.
**Attach:** none
**Settings:** 16:9, 2560 px wide.
**Save as:** `public/media/textures/hall-light.png`

> A very soft, calm abstract background: a warm off-white paper base with an extremely gentle wide gradient toward a pale sand tone in the lower right, and a barely visible large-scale soft geometric pattern of overlapping rounded rectangles. Nothing sharp, nothing dark, nothing busy. It must stay quiet enough that very large bold numbers placed on top remain the only thing anyone looks at. No text, no icons, no medical imagery.

---

# PART 2 — Video (Google Flow)

Flow will not give you transparency. For anything that must sit on a coloured surface, request the exact background colour listed and I will composite or letterbox it in CSS.

## VID-01 · Boot animation — goggles down

**Used in:** the app boot state and the transition into voice mode. The single most reusable animation in the set.
**Attach:** `A1`, `A2`, `A3`
**Settings:** 1:1, 3 seconds, no audio, seamless start and end on the same frame if the tool supports looping.
**Save as:** `public/media/video/boot-goggles.mp4`

> Using the attached character references, animate the exact same red cross robot character, centred, front-facing, from the knees up, on a completely flat solid warm off-white background (#FBF7F2). The character stands perfectly still. The only movement in the entire shot: it raises one hand to its aviator cap and pulls the goggles down over its eyes in one smooth deliberate motion, then lowers the hand and settles. Nothing else moves. The camera is locked, completely static, no zoom, no push, no parallax, no camera shake. Flat 2D cartoon animation style exactly matching the reference artwork — thick black outlines, flat cel colours, no 3D, no lighting effects, no particles, no glow, no text.

---

## VID-02 · Kiosk attract loop

**Used in:** `/kiosk` K1, playing while nobody is at the kiosk.
**Attach:** `A1`, `A2`
**Settings:** 9:16 portrait, 8 seconds, seamless loop, no audio.
**Save as:** `public/media/video/kiosk-attract.mp4`

> Using the attached character references, animate the exact same red cross robot character standing centred in the lower two-thirds of a vertical frame, on a completely flat solid warm off-white background (#FBF7F2). A slow, gentle, continuous idle animation: a soft breathing rise and fall, an occasional slow blink, and one small friendly wave that begins and completes within the clip. Very slow, very calm, unhurried throughout — this plays on a loop in a waiting room and must never feel busy or attention-grabbing. The camera is completely locked and static. The first and last frames must be identical so the clip loops invisibly. Flat 2D cartoon animation exactly matching the reference artwork, thick black outlines, flat cel colours, no background elements, no text, no 3D, no camera movement.

---

## VID-03 · Pitch opening title

**Used in:** the first eight seconds of the pitch video and the deck's title slide.
**Attach:** `A1`, `A2`
**Settings:** 16:9, 8 seconds, no audio (music added later).
**Save as:** `public/media/video/pitch-open.mp4`

> Using the attached character references, animate the exact same red cross robot character on a completely flat solid warm off-white background (#FBF7F2). The character walks in from the left at a confident, unhurried pace, stops in the left third of the frame, turns to face the camera, and gives one small friendly wave, then holds still. The right two-thirds of the frame stays completely empty for a title to be added later — nothing may enter that space at any point. Flat 2D cartoon animation exactly matching the reference artwork, thick black outlines, flat cel colours, locked static camera, no text, no 3D, no lighting effects, no particles.

---

## VID-04 · The problem — corridor B-roll

**Used in:** the pitch video, over the "one assessment, then silence" line. The only asset that depicts the clinical world, and it stays deliberately abstract.
**Attach:** none — **do not attach the mascot.** The mascot has no place in a scene about a patient deteriorating.
**Settings:** 16:9, 8 seconds, no audio.
**Save as:** `public/media/video/corridor-broll.mp4`

> A stylised illustrated animation, not photorealistic, of a row of simple empty chairs along a plain corridor wall, seen from a low, still, respectful distance. Soft muted colours, gentle flat shading, no harsh light. A slow, almost imperceptible push-in on the chairs. A few very simplified, abstract seated human shapes — soft rounded silhouettes with no facial features, no detail, no identifiable clothing, no ethnicity — sit apart from one another and remain almost entirely still. The mood is quiet, patient, ordinary waiting. Absolutely no medical equipment, no blood, no distress, no staff, no hospital signage, no logos, no text. The whole shot should feel calm and unremarkable rather than dramatic.

---

## VID-05 · Closing card

**Used in:** the last five seconds of the pitch video.
**Attach:** `A1`, `A2`
**Settings:** 16:9, 5 seconds.
**Save as:** `public/media/video/pitch-close.mp4`

> Using the attached character references, animate the exact same red cross robot character standing centred in the lower half of the frame on a completely flat solid warm off-white background (#FBF7F2), facing forward, calm and still, with only a very gentle breathing motion and one slow blink. The upper half of the frame stays completely empty for a tagline to be added later. Locked static camera. Flat 2D cartoon animation exactly matching the reference artwork, thick black outlines, flat cel colours, no text, no camera movement, no effects.

---

## What to record rather than generate

Screen-record these from the running prototype at 1440×900, 60 fps, and hand me the files. They belong in the pitch video where generated art would be a lie.

| Clip | What to capture | Length |
|---|---|---|
| `rec-escalation.mp4` | `/corridor`, P-007 Yellow → Red on the tick, card rising | 6 s |
| `rec-structuring.mp4` | `/kiosk` K4 into the structuring step, ending held on the locked acuity slot | 8 s |
| `rec-abstention.mp4` | `/bench`, P-014 rendering "needs your eyes" | 4 s |
| `rec-override.mp4` | Override dialog → the ledger row appearing in `/audit` | 6 s |
| `rec-surge.mp4` | Surge ×3, board densifying, the "risk unchanged" banner | 5 s |

---

# PART 3 — Voice lines

The live prototype uses the browser's own speech synthesis, so nothing here is required for the demo to work. Generate these only if you want higher-quality audio for the **pitch video**.

Constraints, from `DESIGN_SYSTEM.md` §7 — these are hard limits, not style notes:

- MediPilot never speaks an acuity level. Not "red", not "urgent", not "priority one".
- MediPilot never says "you have", "you might have", or anything diagnostic.
- Warm, mid-pitch, unhurried. A calm pilot on the intercom, not a nurse and not a customer-service bot.

| ID | English | हिंदी |
|---|---|---|
| V-01 | "Hello. Tap here and tell me what's wrong." | "नमस्ते। यहाँ दबाइए और बताइए क्या तकलीफ़ है।" |
| V-02 | "I'm listening." | "मैं सुन रहा हूँ।" |
| V-03 | "Let me read that back to you." | "मैं आपको एक बार दोहरा कर सुनाता हूँ।" |
| V-04 | "Did I get that right?" | "क्या यह सही है?" |
| V-05 | "Token two one four. Please watch the board." | "टोकन दो सौ चौदह। कृपया बोर्ड देखते रहिए।" |
| V-06 | "Let's get someone to you right now." | "अभी किसी को आपके पास भेजते हैं।" |
| V-07 | "No problem. A person will take your details." | "कोई बात नहीं। एक व्यक्ति आपकी जानकारी लेंगे।" |
| V-08 | "If anything feels worse, press this button." | "अगर तकलीफ़ बढ़े, तो यह बटन दबाइए।" |

Note V-06: even at the most urgent moment in the entire product, the patient hears a next step, not a severity. That line is worth reading aloud in the pitch.

---

## Production order

1. **IMG-01** — everything else references it. Do not proceed until the character is right.
2. IMG-02, IMG-03, IMG-07 — needed for P3 (kiosk) and the launcher.
3. IMG-11, IMG-12 — cheap, and they lift every screen immediately.
4. IMG-04, IMG-05, IMG-06, IMG-08, IMG-09, IMG-10.
5. VID-01, VID-02 — the two that appear in the live demo.
6. VID-03, VID-04, VID-05 and the screen recordings — pitch video only, do these last, after the prototype is built.

Send me each batch as it lands and I will wire it in.
