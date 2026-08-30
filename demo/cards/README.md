# The seven cards — how to generate them

These are **not** Flow generations. `MediPilot-Pixel-Triage-Reel.md` §09 lists seven title/graphic
cards (`G-01`…`G-04`, `A-01`…`A-03`) that sit between the Flow clips and the screen recordings.
They exist to state real numbers precisely — throughput stats, bake-off results, the six
invariants — and a video model cannot be trusted to render legible, stable digits (that's the
whole reason rule 2 in the shot list bans Flow from ever showing the app's interface). So these
seven are built the way any film's title cards are built: as **static graphics**, not video.

## The method

1. **HTML/CSS, not a design tool.** Each card is a self-contained `.html` file in this folder,
   fixed at exactly 1920×1080, with the real numbers typed in from `../reel.config.json`. This
   beats Canva/Figma for this job because the numbers are typed once, in one place, and a wrong
   digit is a one-line diff instead of a re-export.
2. **Export each one as a single PNG still**, not a recording. A screen-recorded browser can
   soften fine monospace text with capture-codec compression; a direct screenshot at native
   resolution can't. Every card in this reel is meant to be *read*, so crispness matters more
   here than anywhere else in the film.
3. **Hold the PNG for its duration in your editor**, with the editor's own fade-in (200–400 ms)
   and, for the one spot the shot list marks a cross-dissolve (into `A-01` at ~4:05), the editor's
   own dissolve. Don't bake motion into the HTML — a still card that the *editor* controls the
   timing of is far easier to trim to the beat of the cut than a fixed-length recorded clip.

This also means: if you want a **rolling counter** on `G-02` (0 → 30 arrivals ticking up) or a
typewriter reveal on `A-03`, that's a nice-to-have, not the default. Do it last, and only if there's
time — screen-record the page for 2–3 seconds of the animation, then cut to the static PNG hold.
The PNG-only path below is the one to rehearse against; treat the recorded-motion version as a
stretch goal that can silently fail without damaging the film.

## Step by step

**1. Export each card as a PNG**, at exactly 1920×1080, using headless Chrome. From this folder,
on Windows (PowerShell):

```powershell
$chrome = "C:\Program Files\Google\Chrome\Application\chrome.exe"
$cards = "g-01","g-02","g-03","g-04","a-01","a-02","a-03"
foreach ($c in $cards) {
  & $chrome --headless=new --disable-gpu --window-size=1920,1080 `
    --screenshot="$PWD\$c.png" "file:///$PWD/$c.html"
}
```

If `--headless=new` isn't recognised (older Chrome), drop it and use plain `--headless` instead —
try both, keep whichever one actually produces a 1920×1080 PNG rather than a cropped one.

One at a time, if you'd rather check each before moving on:

```powershell
& "C:\Program Files\Google\Chrome\Application\chrome.exe" --headless=new --disable-gpu `
  --window-size=1920,1080 --screenshot="g-01.png" "file:///$PWD/g-01.html"
```

**2. Verify before importing.** Open each PNG and check it's genuinely 1920×1080 with nothing
clipped at the edges — a viewport that isn't exactly 1920 wide will wrap or overflow the layout
(this happened once already while building these; the fix was making sure the headless window
size was set correctly, not the HTML). If you're checking in a browser tool instead of a file
viewer, resize the *tab*, not just the pane — a preview pane smaller than 1920×1080 scales the
render down and can look fine while the underlying layout is actually overflowing.

**3. Import into the edit** at the duration given in the shot list's §09 table (`G-01` 8 s, `G-02`
/ `G-03` / `G-04` 10 s each, `A-01` / `A-02` / `A-03` 12 s each) as a **clean solid-background cut**
— these no longer composite over a dimmed room still (see below), so a straight cut in and out is
correct, with your editor's own 200–400 ms fade.

## Palette — the real app's, not an invented one

These run on the **exact tokens from `frontend/app/globals.css`**, verified against the running
code, not guessed from the design docs:

| Token | Value | Source |
|---|---|---|
| `--bg` | `#FBF7F2` | warm paper — `data-surface="landing"` / `"ward"` / `"patient"` |
| `--bg-card` | `#FFFFFF` | card fill |
| `--line` | `#E7DED2` | borders, rules |
| `--text` / `--text-dim` | `#1C1B1A` / `#6B6560` | ink / secondary ink |
| `--accent` (brand red) | `#DF423D` | `--mp-red`, the logo's cross |
| `--focus` (leather) | `#926A47` | `--mp-leather`, the aviator cap |
| `--steel` / `--glass` | `#A7C4CC` / `#C9EBED` | the gradient-border's 3rd stop and the goggle tint |
| Acuity on paper (`G-02` only) | red `#C62D26` / amber `#9A6206` / green `#1B7A4B` / purple `#5B4BC4` | `globals.css` lines 161–168, the light-surface acuity re-tint |

Two things worth knowing if you touch these later:

- **Every warm-paper surface in the shipped app uses this same palette** — not just the landing
  page. Grepping `data-surface` across the actual page components shows `/board`, `/card/[id]`,
  `/counter` and `/control` are all `"ward"`, the same tokens as `"landing"` and `"patient"`. Only
  `/audit` stays on the dark `clinical` surface (`#0A0D14`, blue `#58A6FF` focus). So this is what
  the product looks like almost everywhere now, not a landing-page-only choice.
- **`G-02`'s Red/Yellow/Green/Abstained pills use the acuity-on-paper hex values, not the brand
  red.** They're deliberately a different, more muted shade (`#C62D26` vs the brand's `#DF423D`)
  so a viewer isn't reading "acuity signal" and "brand decoration" as the same colour — matching
  how the real app keeps those two meanings visually distinct. Each pill also carries the acuity
  glyph from `DESIGN_SYSTEM.md` §3 (▲ ◆ ● ◇) alongside colour and word, per the "never colour
  alone" rule.
- The `SIMULATED DATA` chip is steel/leather-toned, not red — it's an honesty disclosure, not a
  call to action, and red in this palette reads as the latter (it's the CTA button colour on the
  real landing page).

## A note on `reel.config.json`

`../reel.config.json` is the numbers these cards were typed from. It is **not** machine-read —
these are static HTML files, not templates, so if a number in the config changes (say, the
throughput script gets re-run and `arrivalsTotal` comes out at 28 instead of 30), you must update
**both** the config file and the corresponding card HTML by hand. That file also uses `//`
comments for context, which makes it JSONC, not strict JSON — don't feed it straight to
`JSON.parse` expecting it to work.
