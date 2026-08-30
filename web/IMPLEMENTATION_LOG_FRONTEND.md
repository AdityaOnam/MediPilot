# MediPilot Frontend — Implementation Log

> **Last Updated:** 2026-08-26  
> **Status:** Frontend complete, running on mock adapter, ready for backend integration  
> **Stack:** Next.js 16.3.2 · React 19 · Tailwind CSS 4 · Motion (Framer Motion) · Three.js / R3F

---

## Table of Contents

1. [Project Overview](#1-project-overview)
2. [Architecture Summary](#2-architecture-summary)
3. [Directory Structure](#3-directory-structure)
4. [Pages & Routes](#4-pages--routes)
5. [Design System](#5-design-system)
6. [UI/UX Polish Summary](#6-uiux-polish-summary)
7. [API Contract & Mock Adapter](#7-api-contract--mock-adapter)
8. [Backend Integration Guide](#8-backend-integration-guide)
9. [Key Technical Decisions](#9-key-technical-decisions)
10. [Environment Variables](#10-environment-variables)
11. [Build & Deploy](#11-build--deploy)

---

## 1. Project Overview

MediPilot is a **clinical triage decision-support system** for hospital emergency departments. The frontend provides:

- **Patient-facing intake kiosk** — bilingual (EN/HI), voice-enabled, accessibility-first
- **Clinician-facing triage board** — real-time patient queue sorted by acuity
- **Per-patient clinical card** — vitals, risk scoring, AI explanations, override workflow
- **Judge/researcher control panel** — Cost Ratio R slider, simulation clock, surge controls
- **Cryptographic audit ledger** — hash-chained override records, exportable as JSON
- **Landing page** — project showcase with architecture video and feature walkthrough

The frontend currently runs entirely on a **mock adapter** (`lib/api/adapters/mock.ts`) that simulates all backend behavior in-browser. Switching to a real backend requires implementing a single adapter file.

---

## 2. Architecture Summary

```
┌─────────────────────────────────────────────────────────┐
│                    Next.js App Router                    │
│                                                         │
│  app/                                                   │
│  ├── page.tsx          Landing page                     │
│  ├── intake/page.tsx   Patient kiosk (multi-step form)  │
│  ├── board/page.tsx    Clinician triage board            │
│  ├── card/[id]/page.tsx  Per-patient clinical card       │
│  ├── control/page.tsx  Judge control panel               │
│  ├── audit/page.tsx    Audit ledger                      │
│  └── hall/page.tsx     Showcase/hall page                │
│                                                         │
│  components/                                            │
│  ├── clinical/         Domain-specific UI components    │
│  ├── mascot/           3D mascot (Three.js / static)    │
│  ├── 3d/               WebGL scene components           │
│  └── ui/               Generic UI primitives            │
│                                                         │
│  lib/                                                   │
│  ├── api/                                               │
│  │   ├── types.ts      ← SHARED API CONTRACT (376 lines)│
│  │   ├── client.ts     ← Adapter selector               │
│  │   └── adapters/                                      │
│  │       └── mock.ts   ← Full mock implementation       │
│  ├── clinical/         Cadence tables, safeWait logic   │
│  ├── hooks/            Custom React hooks               │
│  ├── intake/           Intake flow state machine        │
│  ├── seed/             Patient corpus (20 patients)     │
│  └── voice/            Web Speech API, audio utils      │
└─────────────────────────────────────────────────────────┘
```

### Data Flow

```
User Interaction
    ↓
Page Component (app/*.tsx)
    ↓
api.method()  ←  lib/api/client.ts
    ↓
Adapter (mock.ts or future live.ts)
    ↓
Response → State update → Re-render
```

**Critical design principle:** Nothing in the app talks to the backend except through `lib/api/client.ts`. Every page calls `api.getCensus()`, `api.score()`, `api.decide()`, etc. The adapter is selected at boot via the `NEXT_PUBLIC_MP_SOURCE` environment variable.

---

## 3. Directory Structure

```
frontend/
├── app/
│   ├── page.tsx                 # Landing page (28KB, 7 sections)
│   ├── layout.tsx               # Root layout (Inter font, metadata)
│   ├── globals.css              # Tailwind + CSS custom properties
│   ├── intake/page.tsx          # Patient intake kiosk (37KB, 12 steps)
│   ├── board/page.tsx           # Clinician triage board
│   ├── card/[id]/page.tsx       # Per-patient clinical card
│   ├── control/page.tsx         # Judge control panel
│   ├── audit/page.tsx           # Audit ledger
│   └── hall/page.tsx            # Showcase page
├── components/
│   ├── clinical/
│   │   ├── AbstentionCard.tsx   # "Model abstained" display
│   │   ├── AcuityCard.tsx       # Acuity band display
│   │   ├── BandChip.tsx         # RED/YELLOW/GREEN pill
│   │   ├── CadenceStrip.tsx     # Re-measure/re-score/ceiling timers
│   │   ├── ConfidenceBand.tsx   # Conformal prediction set display
│   │   ├── ExplanationChannels.tsx  # 3-channel AI explanation
│   │   ├── LockedAcuitySlot.tsx    # "Cannot de-escalate" indicator
│   │   ├── OverrideDialog.tsx      # Clinician override modal
│   │   ├── QueueCard.tsx           # Board row for each patient
│   │   ├── RedFlagBanner.tsx       # Urgent red-flag alert
│   │   └── VitalChip.tsx          # Individual vital sign chip
│   ├── mascot/
│   │   └── Mascot.tsx           # Static mascot image component
│   ├── 3d/                      # Three.js scene components
│   └── ui/                      # Generic UI components
├── lib/
│   ├── api/
│   │   ├── types.ts             # ← THE API CONTRACT (376 lines)
│   │   ├── client.ts            # Adapter selector
│   │   └── adapters/
│   │       └── mock.ts          # Full in-browser mock (23KB)
│   ├── clinical/
│   │   └── safeWait.ts          # Cadence table & safe-wait logic
│   ├── hooks/                   # useVoice, useTimer, etc.
│   ├── intake/                  # Intake state machine
│   ├── seed/
│   │   └── corpus.ts            # 20 patient records (P-01 to P-20)
│   └── voice/
│       └── audio.ts             # Web Speech API, global mute
├── public/
│   └── media/
│       ├── videos/              # Attract loop, boot sequence, architecture
│       └── mascot/              # Mascot pose PNGs
├── package.json
├── tsconfig.json
├── next.config.ts
└── postcss.config.mjs
```

---

## 4. Pages & Routes

### `GET /` — Landing Page
**File:** `app/page.tsx` (28KB)  
**Purpose:** Project showcase for hackathon judges  
**Sections:**
1. Hero with tagline
2. Five core invariants
3. System architecture overview
4. Technical differentiators
5. "Under the Hood" architecture section (with embedded video)
6. "The Five Screens" product interface map
7. Footer

**Polish applied:** Stripped AI-generated aesthetics (glowing borders, neon gradients). Replaced with editorial layout, monospace numbering, clean SVG icons. Video preserved in 16:9 aspect ratio.

---

### `GET /intake` — Patient Intake Kiosk
**File:** `app/intake/page.tsx` (37KB)  
**Purpose:** Bilingual (EN/HI) patient-facing intake form  
**Steps (in order):**
1. `WelcomeStep` — Language selection + attract video
2. `CompanionStep` — "Is someone with you?"
3. `HumanOfferStep` — "Would you prefer a person?"
4. `ConsentStep` — Listening + health record permissions
5. `BasicsStep` — Name, age, sex, chief complaint
6. `TreeStep` — Symptom screening questions
7. `PainStep` — Pain scale (0-10 slider with face indicators)
8. `ReadbackStep` — Summary confirmation before submission
9. `TokenStep` — Queue token issued (3-digit number)
10. `HumanLaneStep` — Redirect to human staff
11. `RedFlagInterrupt` — Emergency alert (modal overlay)

**Key features:**
- Voice input via Web Speech API (`useVoice` hook)
- Boot splash video on first mount
- Sticky header with step counter and language toggle
- Framer Motion page transitions
- Static `Mascot` component in key steps

**Polish applied:**
- Removed 3D WebGL `MascotScene` overlay (was overlapping video)
- Fixed video aspect ratio to 16:9
- Replaced all `var(--bg-raised)`, `var(--line)`, `var(--focus)` with explicit Tailwind classes
- Redesigned all form inputs (text fields, sliders, buttons, checkboxes)
- Added mascot framing containers (`bg-white/[0.02] border border-white/10 rounded-2xl`)
- Polished `TokenStep`, `HumanLaneStep`, `RedFlagInterrupt` with consistent aesthetic

---

### `GET /board` — Clinician Triage Board
**File:** `app/board/page.tsx`  
**Purpose:** Real-time patient queue sorted by acuity band  
**Components used:** `QueueCard`, `BandChip`, `CadenceStrip`  
**Features:**
- SSE subscription for live updates (`api.subscribe()`)
- Patients sorted by `BAND_RANK` (RED > YELLOW > GREEN)
- Compact mode auto-activates during surge (>25 patients)
- Surge banner with forbidden-relaxation display
- Click-through to individual patient cards

---

### `GET /card/[id]` — Patient Clinical Card
**File:** `app/card/[id]/page.tsx`  
**Purpose:** Per-patient clinical detail view (nurse-facing)  
**Components used:** All clinical components  
**Sections:**
1. Patient header (ID, name, age, chief complaint)
2. Acuity band with conformal set
3. Vital signs grid (`VitalChip` × 9)
4. Cadence timers (`CadenceStrip`)
5. AI explanation (3 channels: `ExplanationChannels`)
6. Red flag banner (if applicable)
7. Override dialog (`OverrideDialog`)
8. Abstention card (for P-15)

**Polish applied:** Stripped glowing AI effects. Converted to hyper-dense Bloomberg-style clinical layout with strict semantic colors.

---

### `GET /control` — Judge Control Panel
**File:** `app/control/page.tsx`  
**Purpose:** Simulation control workstation for judges/researchers  

**Layout:** 12-column responsive grid
- **Left column (8 cols):** Cost Ratio R hero control + Live Census
- **Right column (4 cols):** Simulation Status, Clock, Surge, Voice

**Sections:**
1. **Cost Ratio R** — Primary hero control with slider, preset markers (Aggressive/District/Tertiary), live `p*` calculation, session statistics strip (Crossed Up / Crossed Down / Session Total)
2. **System Constraint** — Annotated info block explaining Invariant 1
3. **Live Census** — Patient token grid with colored status stripes
4. **Simulation Status** — Engine status, patient count, arrival rate, R, clock speed
5. **Simulation Clock** — Segmented speed controls (1×/10×/30×/60×/180×)
6. **Surge Simulation** — Activate/deactivate 3× arrival rate
7. **Voice Controls** — Synthetic STT injection + audio mute

**Polish applied:** Replaced flat developer dashboard with control-room aesthetic. Added `backdrop-blur-md` header, simulation online indicator, multi-column grid, segmented toggle controls.

---

### `GET /audit` — Audit Ledger
**File:** `app/audit/page.tsx`  
**Purpose:** Cryptographic audit trail of all override decisions  
**Features:**
- Hash-chain validation (green/red indicator)
- Segmented filter controls (All / Overrides / Downward / Escalations)
- Expandable record rows showing all 16 override fields
- Factors block with directional indicators
- JSON export button
- Model card header (version, calibration, R, p*)

**Polish applied:** Replaced CSS variables with explicit Tailwind. Added JSON-viewer aesthetic to expanded records (blue keys, quoted values, italicized nulls). Chevron rotation on expand.

---

### `GET /hall` — Showcase Page
**File:** `app/hall/page.tsx`  
**Purpose:** Additional showcase/demo page

---

## 5. Design System

### Color Palette

| Token | Value | Usage |
|-------|-------|-------|
| Background | `#0A0D14` | Page background |
| Surface | `#11141D` | Card/panel background |
| Surface raised | `bg-white/[0.02]` | Subtle elevation |
| Border | `border-white/10` | Default borders |
| Border hover | `border-white/20` | Hover state |
| Primary text | `text-white` or `text-white/90` | Headings |
| Secondary text | `text-white/50` | Labels, hints |
| Tertiary text | `text-white/30` – `text-white/40` | Metadata |
| Accent | `#58A6FF` | Interactive elements, links |
| Red (acuity) | `text-red-500` / `border-red-500/30` | RED band |
| Amber (acuity) | `text-amber-500` / `border-amber-500/30` | YELLOW band |
| Green (acuity) | `text-emerald-500` / `border-emerald-500/30` | GREEN band |
| Purple | `text-purple-500` / `border-purple-500/30` | ABSTAINED |
| Status green | `text-emerald-400` | "Online", "Running" |

### Typography

- **Font:** Inter (system), fallback to system sans-serif
- **Monospace:** `font-mono` for values, IDs, hashes, R values
- **Section labels:** `text-[11px] font-bold tracking-widest uppercase text-white/40`
- **Data values:** `tabular-nums` for all numbers
- **Page titles:** `text-[13px] font-bold tracking-widest uppercase`

### Component Patterns

- **Cards:** `rounded-xl border border-white/10 bg-[#11141D] shadow-sm`
- **Buttons (primary):** `bg-[#58A6FF] text-[#0A0D14] hover:bg-[#3b8fdc]`
- **Buttons (ghost):** `border border-white/10 bg-[#0A0D14] hover:bg-white/[0.02]`
- **Segmented controls:** `flex bg-[#0A0D14] border border-white/5 rounded-lg p-1`
- **Status pills:** `px-2 py-1 rounded-md border border-white/10 bg-white/[0.02]`
- **Headers:** `backdrop-blur-md sticky top-0 z-40 border-b border-white/10`

---

## 6. UI/UX Polish Summary

### What Was Done (in chronological order)

| Phase | Page | Changes |
|-------|------|---------|
| 1 | `/card/[id]` | Stripped neon/glow effects. Bloomberg-style clinical density. Redesigned `AbstentionCard`, `VitalChip`, `CadenceStrip`, `ConfidenceBand`. |
| 2 | `/` (landing) | Redesigned Sections 5-7. Replaced emojis with SVG icons. Clean technical index. Editorial layout. |
| 3 | `/intake` | Fixed 3D model / video overlap. Forced 16:9 video. Redesigned all step components (`WelcomeStep` through `RedFlagInterrupt`). Replaced CSS vars with Tailwind. |
| 4 | `/control` | Full redesign from flat list to multi-column control room. Added simulation status panel, segmented clock controls, annotated system constraint block. |
| 5 | `/audit` | Redesigned header, model card, filters, record rows. Added JSON-viewer aesthetic. Hash chain validation pill. |

### Design Principles Applied

1. **Clinical clarity > visual decoration** — Every pixel serves an information purpose
2. **No AI-generated look** — No neon, no glow, no purple gradients, no glassmorphism
3. **Semantic colors only** — Red/Amber/Green/Purple used ONLY when the underlying state requires it
4. **Technical terms preserved** — R, p*, Invariant 1, STT, conformal set all remain visible
5. **Information density** — Bloomberg/Epic-level density without clutter

---

## 7. API Contract & Mock Adapter

### The API Contract

The single source of truth is [`lib/api/types.ts`](lib/api/types.ts) (376 lines). It defines:

#### Core Types
- `Band` — `'RED' | 'YELLOW' | 'GREEN'`
- `AgeStratum` — 6 strata (neonate through geriatric)
- `Measurement` — vital sign reading with validity, source, and de-escalation authority
- `Cadence` — re-score/re-measure/ceiling timers
- `Encounter` — full patient record (30+ fields)
- `ScoreResponse` — model output including band, probability, conformal set, explanation
- `OverrideRecord` — 16-field hash-chained audit record
- `SurgeState` — surge configuration and refusals

#### The `MediPilotApi` Interface

```typescript
interface MediPilotApi {
  getConfig(): Promise<SiteConfig>;
  getCensus(): Promise<Encounter[]>;
  getEncounter(id: string): Promise<Encounter>;
  score(id: string): Promise<ScoreResponse>;
  getRechecks(): Promise<RecheckTask[]>;
  decide(input: DecisionInput): Promise<OverrideRecord>;
  getSurge(): Promise<SurgeState>;
  setSurge(active: boolean): Promise<SurgeState>;
  getAudit(since?: string): Promise<OverrideRecord[]>;
  setR(R: number): Promise<RControlResponse>;
  setClockSpeed(speed: number): Promise<{ simTime: string; speed: number }>;
  subscribe(handler: (e: StreamEvent) => void): () => void;
}
```

### The Mock Adapter

[`lib/api/adapters/mock.ts`](lib/api/adapters/mock.ts) (23KB) implements the full `MediPilotApi` interface in-browser:

- **20 seeded patients** from `lib/seed/corpus.ts`
- **Simulated clock** with configurable speed (1× to 180×)
- **Automatic re-scoring** on cadence timers
- **Ceiling-based escalation** (YELLOW → RED after 1 hour)
- **Surge mode** — injects 10 filler patients, stretches cadences
- **R control** — recalculates `p*`, re-bins patients, tracks moved.up/moved.down
- **SSE simulation** via `subscribe()` with synthetic events
- **Override recording** with SHA-256 hash chain
- **Abstention handling** for P-15 (YELLOW floor, Invariant 5)

---

## 8. Backend Integration Guide

### Step 1: Create the Live Adapter

Create `lib/api/adapters/live.ts` implementing the same `MediPilotApi` interface:

```typescript
// lib/api/adapters/live.ts
import type { MediPilotApi } from '../types';

const BASE = process.env.NEXT_PUBLIC_API_BASE ?? 'http://localhost:8000';

export function createLiveAdapter(): MediPilotApi {
  return {
    async getConfig() {
      const res = await fetch(`${BASE}/api/config`);
      return res.json();
    },

    async getCensus() {
      const res = await fetch(`${BASE}/api/census`);
      return res.json();
    },

    async getEncounter(id: string) {
      const res = await fetch(`${BASE}/api/encounters/${id}`);
      return res.json();
    },

    async score(id: string) {
      const res = await fetch(`${BASE}/api/encounters/${id}/score`, { method: 'POST' });
      return res.json();
    },

    async getRechecks() {
      const res = await fetch(`${BASE}/api/rechecks`);
      return res.json();
    },

    async decide(input) {
      const res = await fetch(`${BASE}/api/decide`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(input),
      });
      return res.json();
    },

    async getSurge() {
      const res = await fetch(`${BASE}/api/surge`);
      return res.json();
    },

    async setSurge(active: boolean) {
      const res = await fetch(`${BASE}/api/surge`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ active }),
      });
      return res.json();
    },

    async getAudit(since?: string) {
      const url = since ? `${BASE}/api/audit?since=${since}` : `${BASE}/api/audit`;
      const res = await fetch(url);
      return res.json();
    },

    async setR(R: number) {
      const res = await fetch(`${BASE}/api/r`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ R }),
      });
      return res.json();
    },

    async setClockSpeed(speed: number) {
      const res = await fetch(`${BASE}/api/clock`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ speed }),
      });
      return res.json();
    },

    subscribe(handler) {
      const es = new EventSource(`${BASE}/api/stream`);
      es.onmessage = (e) => handler(JSON.parse(e.data));
      return () => es.close();
    },
  };
}
```

### Step 2: Update the Client Selector

```typescript
// lib/api/client.ts
import type { MediPilotApi } from './types';
import { createMockAdapter } from './adapters/mock';
import { createLiveAdapter } from './adapters/live';

const SOURCE = process.env.NEXT_PUBLIC_MP_SOURCE ?? 'mock';

function createApi(): MediPilotApi {
  if (SOURCE === 'live') {
    return createLiveAdapter();
  }
  return createMockAdapter();
}

export const api: MediPilotApi = createApi();
```

### Step 3: Set Environment Variables

```env
# .env.local
NEXT_PUBLIC_MP_SOURCE=live
NEXT_PUBLIC_API_BASE=http://localhost:8000
```

### Backend API Endpoints Required

| Method | Endpoint | Request Body | Response Type | Notes |
|--------|----------|-------------|---------------|-------|
| `GET` | `/api/config` | — | `SiteConfig` | Model version, R bounds, cadence table |
| `GET` | `/api/census` | — | `Encounter[]` | All waiting patients, sorted |
| `GET` | `/api/encounters/:id` | — | `Encounter` | Single patient detail |
| `POST` | `/api/encounters/:id/score` | — | `ScoreResponse` | Trigger model scoring |
| `GET` | `/api/rechecks` | — | `RecheckTask[]` | Pending recheck tasks |
| `POST` | `/api/decide` | `DecisionInput` | `OverrideRecord` | Accept or override band |
| `GET` | `/api/surge` | — | `SurgeState` | Current surge state |
| `PUT` | `/api/surge` | `{ active: boolean }` | `SurgeState` | Toggle surge |
| `GET` | `/api/audit` | `?since=ISO` (optional) | `OverrideRecord[]` | Audit trail |
| `PUT` | `/api/r` | `{ R: number }` | `RControlResponse` | Set cost ratio |
| `PUT` | `/api/clock` | `{ speed: number }` | `{ simTime, speed }` | Set simulation clock |
| `GET` | `/api/stream` | — | SSE `StreamEvent` | Server-Sent Events |

### Critical Backend Invariants

The backend MUST enforce these invariants (the frontend assumes them):

1. **Invariant 1 (Escalate-only):** `moved.down` is structurally 0. The system may never lower a band below `humanAssignedBand`. Only a human `decide()` call can de-escalate.

2. **Invariant 2 (Input transparency):** Every `ScoreResponse` includes `inputsUsed` — the list of fields that contributed to the score.

3. **Invariant 3 (Age stratum always present):** If age is unknown, infer the widest-safety stratum and set `ageStratumInferred: true`.

4. **Invariant 4 (Measurement freshness):** `validity` must be computed server-side. `expired` readings are rendered as MISSING.

5. **Invariant 5 (Abstention floor):** When the model abstains, `effectiveBand` must be at least YELLOW, never GREEN.

### SSE Stream Events

The backend should emit these events via Server-Sent Events:

```typescript
type StreamEvent =
  | { type: 'rescore'; encounterId: string; band: Band; simTime: string }
  | { type: 'escalation'; encounterId: string; from: Band; to: Band; cause: 'MODEL' | 'CEILING' | 'RED_FLAG'; auditId: string }
  | { type: 'breach'; encounterId: string; kind: BreachKind; bandChanged: boolean }
  | { type: 'recheckDue'; encounterId: string; owner: RecheckOwner }
  | { type: 'surge'; active: boolean; multiplier: number };
// NOTE: there is deliberately no 'deescalation' event.
```

---

## 9. Key Technical Decisions

| Decision | Rationale |
|----------|-----------|
| **Mock-first architecture** | Frontend and backend can be developed independently. The mock adapter is comprehensive enough to demo the full system. |
| **Single adapter interface** | Switching from mock to live backend requires zero UI code changes — just swap the environment variable. |
| **CSS vars → Tailwind migration** | Original codebase used CSS custom properties (`var(--bg-raised)`, etc.). Migrated to explicit Tailwind utility classes for tighter control and consistent dark theme. |
| **No `lucide-react` dependency** | Icon library not installed. All icons are inline SVGs to keep the bundle minimal. |
| **Removed 3D WebGL from intake** | The `MascotScene` (Three.js canvas) was overlapping the attract video. Replaced with static `Mascot` (image) component. 3D is still available in `/hall`. |
| **Motion (Framer Motion)** | Used for page transitions in intake flow and layout animations in the census grid. |
| **Bilingual support** | Intake supports English and Hindi via a simple `t(lang, en, hi)` helper. No i18n library — intentionally lightweight. |
| **Hash chain in audit** | Override records are SHA-256 hash-chained. The frontend validates the chain and shows a green/red indicator. Backend must maintain the chain. |

---

## 10. Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `NEXT_PUBLIC_MP_SOURCE` | `mock` | Set to `live` to use the HTTP adapter |
| `NEXT_PUBLIC_API_BASE` | `http://localhost:8000` | Backend API base URL (only used when `MP_SOURCE=live`) |

---

## 11. Build & Deploy

### Local Development

```bash
cd frontend
npm install
npm run dev
# → http://localhost:3000
```

### Production Build

```bash
npm run build
npm start
```

### Build Output (verified)

```
Route (app)
┌ ○ /              (Static)
├ ○ /_not-found     (Static)
├ ○ /audit          (Static)
├ ○ /board          (Static)
├ ƒ /card/[id]      (Dynamic, server-rendered)
├ ○ /control        (Static)
├ ○ /hall           (Static)
└ ○ /intake         (Static)
```

All pages compile with zero TypeScript errors and zero warnings.

### Deployment on Vercel

If the GitHub repo contains the full project (not just `frontend/`):
- Set **Root Directory** to `frontend` in Vercel project settings
- No other configuration needed

---

## Appendix: Files Modified During Polish

| File | Size | What Changed |
|------|------|-------------|
| `app/page.tsx` | 28KB | Sections 5-7 redesigned (architecture, five screens, footer) |
| `app/intake/page.tsx` | 37KB | All 12 step components polished. Header, forms, buttons, mascot framing. CSS vars replaced. |
| `app/card/[id]/page.tsx` | — | Clinical layout densified. Glowing effects stripped. |
| `app/control/page.tsx` | — | Full redesign to multi-column control room. Added simulation status panel. |
| `app/audit/page.tsx` | — | Redesigned to JSON-viewer aesthetic. Segmented filters. Hash chain pill. |
| `components/clinical/AbstentionCard.tsx` | 3.3KB | Stripped neon, clean card styling |
| `components/clinical/VitalChip.tsx` | 4.6KB | Bloomberg-style vital display |
| `components/clinical/CadenceStrip.tsx` | 3.7KB | Clean timer strip |
| `components/clinical/ConfidenceBand.tsx` | 2.8KB | Conformal set display |
