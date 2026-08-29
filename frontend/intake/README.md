# `intake/` — the talking triage conversation

Self-contained rebuild of `/intake`. Nothing outside this folder imports it except
`app/intake/page.tsx` (mounts `IntakeApp`) and `app/api/intake/*` (the three Groq routes).
The previous implementation is parked, unrouted, at `app/_intake-old/`.

## Run it

```bash
npm run dev
```

`/intake` needs **no Python backend** to walk the whole conversation. The orchestrator is only
contacted at the very end, by `api.submitIntake()`; if it is down the kiosk still issues a token
and says so in the console rather than hanging.

**Chrome only.** Speech recognition is `webkitSpeechRecognition`, which Firefox and Safari do not
implement, and it needs a network connection (Chrome does the recognition server-side). Every
question is fully answerable by tapping or typing, so a non-Chrome browser or a denied microphone
degrades the experience rather than blocking it — that is the fallback we demo if venue wifi dies.

## How a turn works

```
SPEAKING ──▶ ARMING (2 s) ──▶ LISTENING ──▶ SETTLING (300 ms) ──▶ MATCHING
   │             │                │
   │             │                └─ no silence timer runs until speech ONSET
   │             └─ noise floor sampled HERE, from this room, this question
   └─ recogniser aborted outright — this is what stops the kiosk
      transcribing its own prompt and answering itself
```

Chrome's `webkitSpeechRecognition` opens its **own** capture and ignores any `MediaStream` you
hand it, so muting a track does nothing to it. `abort()` is the only real close, which is why
`useSpeech` calls it rather than muting.

Silence windows adapt to the question — 1.5 s after a yes/no, 3 s after free text, 5 s ceiling.
A flat 5 s reads as a crash when the answer was "haan".

## Answering: three tiers, Groq last

| Tier | What | Cost |
|---|---|---|
| 0 | Exact lexicon — yes/no and 0–10, EN + Devanagari + romanised | instant, offline |
| 1 | Similarity over labels, value slugs and `synonyms`, plus an edit-distance rescue for ASR near-misses | instant, offline |
| 2 | `/api/intake/match` — Groq picks one of the given option values, or NONE | network, exception path only |

`synonyms` on each question is what keeps tier 2 rare: every extra spoken form you add is one more
answer that resolves without a round-trip. Adding one is a row edit in `tree/branches/*`.

The tier-2 output vocabulary is **closed by construction** — anything the model returns that is not
one of the option values is read as NONE, on both sides of the wire. It can never invent an option,
and it is never asked what an answer means clinically.

## Red flags

Two tiers, and the deterministic one never depends on the network:

- **Tier A** (`redflags/detect.ts`) — bilingual phrase table over the eight codes, plus the yes/no
  `observes` path so a bare "yes" to *"are you sweating?"* still fires. Instant, offline.
- **Tier B** (`/api/intake/observe`, B7) — Groq returns a subset of the same closed eight-code list
  and nothing else. It reports what was said; a fixed table decides what it means.

RF-03 is a **compound** rule: chest pain *with* sweating, radiation or breathlessness. Chest pain
alone is common and routes into the branch instead — firing on it would call a nurse for every
reflux presentation.

### `observeOn` — read this before adding a yes/no question

A yes/no answer is the literal word "yes" or "no", so the text scan cannot see it. `observes`
handles that, and **`observeOn` says which answer is the alarming one.** It defaults to `'yes'`,
but several questions are phrased positively because that is what a distressed patient can
actually answer:

| Question | Alarming answer |
|---|---|
| *"Can you speak a full sentence without stopping for breath?"* | **no** |
| *"Does the bleeding slow down when you press on it?"* | **no** |
| *"Is the child feeding or drinking normally?"* | **no** |
| *"Are you fully awake and thinking clearly?"* | **no** |

Getting this backwards fails in the worst direction — a patient answering truthfully would
*suppress* the alert rather than raise it. `/api/intake/selftest` pins every inverted question in
both directions; add a row there whenever you add one.

`urgentOn` is the separate case: it calls a person **without** claiming one of the eight codes.
Used only for self-harm risk, which is a nurse-now situation the physiological table does not
cover. It submits as `humanAssistanceRequested`, never as a fabricated red flag.

The eight codes are copied verbatim from
`Backend/MediPilot/medipilot-model/config/red_flags.yaml`. **Do not rename them here alone** — the
band engine keys off these exact strings when `redFlagsFired[]` arrives on submit.

## Groq, and what happens without it

Set `GROQ_API_KEY` in `.env.local` (see `.env.example`). **Server-only** — no `NEXT_PUBLIC_`
prefix, so it is never inlined into a client bundle, and `intake/server/*` must only ever be
imported from `app/api/`.

Everything works without the key. Classification falls back to the offline keyword table, option
matching falls back to *"please pick one below"*, and red flags still fire from tier A. The key
buys the exception paths, not the safety net. `MEDIPILOT_INTAKE_OFFLINE=1` forces that state
deliberately, for rehearsing without burning free-tier quota.

Two models, from our own bake-off: `gpt-oss-120b` (F1 0.962, **0** red flags missed) for
observation extraction, `gpt-oss-20b` (F1 0.816) for matching and classification, where a miss is
recoverable.

Every prompt lives in `server/prompts.ts`, readable top to bottom, and `server/validate.ts` is
what *enforces* the closed vocabulary the prompts ask for — a hallucinated branch, option or
observation code is discarded there rather than entering the tree.

## Checking it still works

```bash
curl -s localhost:3000/api/intake/selftest
```

118 fixtures. Dev only; 404s in production. Replace with a real test runner when one is added.

| Group | Covers |
|---|---|
| `match` | Tier 0/1 across EN, Devanagari, romanised Hindi, ASR near-misses, negation |
| `redflags` | The phrase table, the RF-03 compound rule, and *"no chest pain at all"* not firing |
| `classify` | The offline keyword router |
| `validators` | Adversarial model responses — invented codes, an `acuity`/`band` key, an option never offered |
| `inversions` | Every `observeOn` question driven through the real reducer, **in both directions** |
| `coverage` | Every branch has ≥3 questions and at least one route to a nurse |

## Layout

| Path | Owns |
|---|---|
| `tree/` | Question data, the 16 branches, the tail, and `engine.ts` — pure reducers, no React |
| `voice/` | `useSpeech` (the state machine), `vad` (noise floor, onset, silence), `tts` |
| `match/` | The three tiers |
| `redflags/` | The eight codes and the offline detector |
| `components/` | `Screen` (owns speak-on-mount), `QuestionCard` (renders any kind), the step screens |
| `session.ts` | The React context; every mutation routes through `engine.ts` |
| `server/` | Groq client, prompts, and the validators. **Never import from a client component.** |

## Speech effort

`useSpeech` reports `SpeechMetrics` alongside each transcript, measured from the VAD already
running for silence detection — segments, longest run, span. A patient who cannot get six words
out without stopping is producing a respiratory-effort finding a stated respiratory rate can miss.

It is recorded as `observed_speech_effort` in `symptomAnswers`, for the nurse card. It is
**never** an automatic red flag: it is noisy — a nervous patient stammers, a thoughtful one
pauses — so nothing downstream escalates on it alone.
