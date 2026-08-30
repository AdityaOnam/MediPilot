# DECISIONS.md — Judgment calls, ambiguities, deviations

## Ambiguity: Two `main.tex` files

`Backend/MediPilot/main.tex` (902 lines, 45,535 bytes) and
`Backend/MediPilot/docs/main.tex` (46 lines, 1,470 bytes) are genuinely
different files. Compare-Object showed 920 differing lines.

**Decision**: Per the brief:
- `docs/main.tex` (the small wrapper/stub) → `docs/paper/main.tex`
- `Backend/MediPilot/main.tex` (the full 902-line paper) → `archive/main-root-variant.tex`
- Same for `main.toc` files (docs version = 46 lines, root version = larger)

Both archived variants carry `archive/main-root-variant.{tex,toc}`.

---

## `frontend/CLAUDE.md` merge

`frontend/CLAUDE.md` contained only `@AGENTS.md` (a pointer). After merging
into root `AGENTS.md`, CLAUDE.md becomes self-referential. It was left at
`web/CLAUDE.md` in place (not deleted, not moved — the brief says no deletes).
Its content still reads `@AGENTS.md` which now resolves to the root AGENTS.md.
This is harmless.

---

## `README.md` at repo root — INTENTIONALLY NOT EDITED

The brief explicitly forbids editing `README.md` at repo root:
> "FORBIDDEN in this phase: README.md at repo root"
> "Do not write a new README. Do not restyle the existing one."

As a result, the following old-path references survive in `README.md`:
- `Backend/MediPilot/medipilot-model` (lines 97, 362)
- `Backend/MediPilot/Metrics/` (line 167)
- `medipilot-model/` (lines 281, 362)
- `frontend/` (lines 138, 220)

These are deliberate. The brief says README will be rewritten by someone else.

---

## Kaggle notebooks (`.ipynb`) — NOT EDITED

`backend/eval/kaggle/asr_bakeoff.ipynb` and `llm_structurer_bakeoff.ipynb`
contain `medipilot-model/` references in Jupyter cell strings. The tooling
rules forbid editing `.ipynb` files:
> "You may not edit file extensions: [.ipynb]"

Surviving references:
- `asr_bakeoff.ipynb`: lines 26, 121, 131
- `llm_structurer_bakeoff.ipynb`: lines 22, 123, 127

These reference the Kaggle dataset name (where the zip was uploaded), not a
local filesystem path. The zip itself is now archived. If re-run on Kaggle,
the dataset name would need updating — but that is post-audit work.

---

## `model/calibration.py` — MODEL_VERSION string not changed

`backend/model/calibration.py` line 30:
```python
MODEL_VERSION = "medipilot-model-v0.1.0"
```
This is a **model artifact version identifier**, not a filesystem path. The
string `medipilot-model` here is the model family name. Changing it would:
1. Break artifact lookup logic that matches this string to directory names
2. Constitute a program logic change (forbidden in Phase 2)

Decision: leave unchanged, document here.

---

## Historical log references to `frontend/` — NOT CHANGED

`docs/logs/IMPLEMENTATION_LOG.md` lines 363 and 418 contain:
- "all Next.js code moved out of the project root into `./frontend/`"
- "Session 3 relocated it again into `frontend/`"

These describe historical facts about past work sessions. Rewriting them would
falsify the historical record. Left unchanged.

`docs/logs/IMPLEMENTATION_LOG_FRONTEND.md` lines 96 and 617 show `frontend/`
in a directory tree listing and a note about GitHub. These are historical
documentation. Left unchanged.

---

## `web/lib/intake/questionTree.ts` — NOT QUARANTINED

The brief said to quarantine `lib/intake/questionTree.ts`, claiming it was only
imported by `_intake-old/`. However, grep shows:

```
web/lib/api/adapters/mock.ts:752:  const { questionsFor } = await import('../../intake/questionTree');
web/lib/api/adapters/mock.ts:762:  const { questionsFor } = await import('../../intake/questionTree');
```

`mock.ts` (the mock adapter used in NEXT_PUBLIC_MP_SOURCE=mock mode — the
default demo mode) **actively imports** `lib/intake/questionTree.ts`. Quarantining
it would break the build. Decision: leave in place, document here.

The brief's claim ("It is the ONLY importer") was incorrect for `questionTree.ts`.

---

## `Backend/MediPilot/.gitignore` — archived, not merged

The original `Backend/MediPilot/.gitignore` was a Python-specific ignore file
(data/*.jsonl, model splits, bakeoff outputs). Its content was reviewed and
the relevant rules were incorporated into the consolidated root `.gitignore`.
The original was moved to `archive/backend-medipilot-gitignore.txt` (renamed
to `.txt` to avoid it being treated as an active gitignore).

---

## `backend/medipilot-model.zip` path correction

The zip was tracked at `Backend/MediPilot/medipilot-model.zip` (not
`backend/medipilot-model.zip` as listed in the brief). It was correctly
quarantined from its actual tracked path to `archive/medipilot-model.zip`.

---

## Phase 3 — `experiments/whisper-live/whisper-live-bundle.zip`

The brief says "leave" this zip in place. It was moved from
`Backend/MediPilot/speech_layer/` to `experiments/whisper-live/` in Phase 1
as part of the speech_layer move. It remains there (not quarantined).

---

## `backend/eval_output.txt` — untracked, not quarantined

Untracked with `git rm --cached` and added to `.gitignore`. The file remains
on disk but is no longer in the git index. This is per Phase 3 spec.
