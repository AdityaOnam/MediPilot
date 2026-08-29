import type {
  MediPilotApi, Encounter, ScoreResponse, SurgeState, RecheckTask,
  OverrideRecord, RControlResponse, SiteConfig, DecisionInput,
  StreamEvent, Band, Factor, Explanation, AgeStratum, VitalCode, MeasurementSource,
  IntakeSubmission, IntakeResponse, StructureResponse, TranscriptionResponse, TreeState,
  Disposition,
} from '../types';
import { BAND_RANK } from '../types';
import { CORPUS } from '../../seed/corpus';
import { scanRedFlags } from '../../clinical/redFlags';
import { CADENCE_TABLE, SURGE_CADENCE_TABLE } from '../../clinical/safeWait';
import { generateSurgeFillers } from '../../seed/surgeFillers';
import { computeRisk } from '../../clinical/riskEngine';
import { normaliseVitalCode, bandForStratum, requiredVitals, VITALS } from '../../clinical/vitals';
import { resolveStratum } from '../../clinical/ageBands';

/**
 * Mock adapter — the full demo running offline.
 *
 * Notable P1 additions:
 *  - simNowMs advances continuously against a `clockSpeed` multiplier
 *  - tick() promotes Yellow → Red when its ceiling is exceeded, WITHOUT any
 *    vital having changed. That is the invariant this whole model exists for.
 *  - subscribe() emits `escalation` and `breach` events as they happen.
 */

interface State {
  encounters: Encounter[];
  R: number;
  clockSpeed: number;       // sim seconds per real second
  simEpochMs: number;       // real time when speed was last set
  simBaseMs: number;        // sim time at that moment
  surgeActive: boolean;
  audit: OverrideRecord[];  // newest at index 0
  auditHead: string | null; // most-recent row's hash
  handlers: Set<(e: StreamEvent) => void>;
  tickTimer: ReturnType<typeof setInterval> | null;
}

/**
 * djb2 — dependency-free deterministic hash. Real deployments swap for
 * SHA-256 in the backend; the frontend just displays what it receives.
 * Hex output, chained by prevHash so tampering with any row breaks the tail.
 */
function djb2Hex(s: string): string {
  let h = 5381;
  for (let i = 0; i < s.length; i++) h = ((h * 33) ^ s.charCodeAt(i)) >>> 0;
  return h.toString(16).padStart(8, '0');
}

/** Stable JSON of the 16 legal fields for hashing. */
function canonical(r: OverrideRecord): string {
  const {
    patientId, timestampUtc, clinicianId, clinicianRole,
    systemBand, clinicianBand, direction, reasonCode, reasonText,
    score, confidence, factorsShown, inputsHash,
    modelVersion, calibrationVersion, consentState, outcomeRef,
  } = r;
  return JSON.stringify({
    patientId, timestampUtc, clinicianId, clinicianRole,
    systemBand, clinicianBand, direction, reasonCode, reasonText,
    score, confidence, factorsShown, inputsHash,
    modelVersion, calibrationVersion, consentState, outcomeRef,
  });
}

// ---------------------------------------------------------------------------
// Persistence
// ---------------------------------------------------------------------------

/**
 * The board has to survive a page reload.
 *
 * Everything here used to live in module scope only, so a patient who
 * finished intake vanished the moment anyone refreshed /board — and in dev
 * a hot-module reload was enough to lose them. That is the opposite of the
 * requirement: an encounter leaves the queue when a nurse dispositions it
 * and at no other time.
 *
 * Only encounters that did NOT come from the seed corpus are written, plus
 * a per-id patch of the mutable fields for corpus patients. Persisting the
 * whole array would freeze the seed data, so editing corpus.ts would stop
 * having any visible effect until someone cleared their browser storage.
 */
const STORE_KEY = 'medipilot.board.v1';

/** The fields a nurse or the counter can change. Everything else is seed. */
interface EncounterPatch {
  currentBand: Band | null;
  humanAssignedBand: Band | null;
  measurements: Encounter['measurements'];
  state: Encounter['state'];
  awaitingVitals?: boolean;
  requiredVitals?: VitalCode[];
  disposition?: Disposition | null;
  dispositionAt?: string | null;
  dispositionBy?: string | null;
  dispositionNote?: string | null;
}

interface PersistedShape {
  version: 1;
  /** Encounters created through intake, stored whole. */
  created: Encounter[];
  /** Mutations applied to seed-corpus encounters, keyed by id. */
  patches: Record<string, EncounterPatch>;
}

const isBrowser = typeof window !== 'undefined' && typeof localStorage !== 'undefined';

function patchOf(e: Encounter): EncounterPatch {
  return {
    currentBand: e.currentBand,
    humanAssignedBand: e.humanAssignedBand,
    measurements: e.measurements,
    state: e.state,
    awaitingVitals: e.awaitingVitals,
    requiredVitals: e.requiredVitals,
    disposition: e.disposition ?? null,
    dispositionAt: e.dispositionAt ?? null,
    dispositionBy: e.dispositionBy ?? null,
    dispositionNote: e.dispositionNote ?? null,
  };
}

const CORPUS_IDS = new Set(CORPUS.map(e => e.encounterId));

function persist(): void {
  if (!isBrowser) return;
  try {
    const payload: PersistedShape = { version: 1, created: [], patches: {} };
    for (const e of state.encounters) {
      if (CORPUS_IDS.has(e.encounterId)) {
        // Only store a patch when something actually diverged from seed,
        // so an untouched demo writes nothing and stays fully re-seedable.
        const seed = CORPUS.find(c => c.encounterId === e.encounterId)!;
        const changed =
          e.currentBand !== seed.currentBand ||
          e.humanAssignedBand !== seed.humanAssignedBand ||
          e.state !== seed.state ||
          e.measurements.length !== seed.measurements.length ||
          !!e.disposition;
        if (changed) payload.patches[e.encounterId] = patchOf(e);
      } else {
        payload.created.push(e);
      }
    }
    localStorage.setItem(STORE_KEY, JSON.stringify(payload));
  } catch {
    // A full or disabled localStorage must never break the board. The
    // in-memory state is still correct for this tab.
  }
}

function hydrate(): Encounter[] {
  const base = CORPUS.map(e => ({ ...e, cadence: { ...e.cadence } }));
  if (!isBrowser) return base;
  try {
    const raw = localStorage.getItem(STORE_KEY);
    if (!raw) return base;
    const saved = JSON.parse(raw) as PersistedShape;
    if (saved.version !== 1) return base;

    for (const e of base) {
      const p = saved.patches?.[e.encounterId];
      if (p) Object.assign(e, p);
    }
    for (const created of saved.created ?? []) {
      base.push({ ...created, cadence: { ...created.cadence } });
    }
    return base;
  } catch {
    return base;
  }
}

const state: State = {
  encounters: hydrate(),
  R: 500,
  clockSpeed: 1,
  simEpochMs: Date.now(),
  simBaseMs: Date.now(),
  surgeActive: false,
  audit: [],
  auditHead: null,
  handlers: new Set(),
  tickTimer: null,
};

/**
 * Per-record model probability. Not part of the wire type — sits inside the
 * mock so R changes can meaningfully reshuffle the board. Chosen so the
 * defaults at R=500 (p*=0.002) reproduce each record's authored band, and
 * moving R up/down produces the interesting migrations §14 asks for.
 */
const PROBABILITY: Record<string, number> = {
  'P-01': 0.95,   'P-02': 0.0003, 'P-03': 0.008,  'P-04': 0.010,
  'P-05': 0.006,  'P-06': 0.007,  'P-07': 0.011,  'P-08': 0.009,
  'P-09': 0.0008, 'P-10': 0.008,  'P-11': 0.012,  'P-12': 0.010,
  'P-13': 0.008,  'P-14': 0.010,  'P-15': 0,      'P-16': 0.85,
  'P-17': 0.0009, 'P-18': 0.90,   'P-19': 0.011,  'P-20': 0.0008,
};

/**
 * The optimiser's band from a probability + threshold.
 * RED at 10× p*, YELLOW at p*. Everything below is GREEN.
 */
function bandFromProbability(p: number, pStar: number): Band {
  if (p >= 10 * pStar) return 'RED';
  if (p >= pStar) return 'YELLOW';
  return 'GREEN';
}

/**
 * The floor for I-1 escalate-only enforcement.
 * If a human has set the band, that's the floor. Otherwise the system's own
 * previous recommendation is the floor — the optimiser cannot reverse itself
 * just because R moved.
 */
function floorBand(e: Encounter): Band | null {
  return e.humanAssignedBand ?? e.currentBand;
}

function simNowMs(): number {
  return state.simBaseMs + (Date.now() - state.simEpochMs) * state.clockSpeed;
}

function emit(event: StreamEvent) {
  for (const h of state.handlers) h(event);
}

/**
 * Advance the world by one tick. Recompute breach state and escalate any
 * Yellow whose ceiling has passed. This is the whole point of P1:
 * a card can go RED without a single vital moving.
 */
function tick() {
  const now = simNowMs();
  for (const e of state.encounters) {
    if (e.state !== 'waiting') continue;

    const ceilingPassed = new Date(e.cadence.ceilingBreachesAt).getTime() < now;
    const remeasurePassed = new Date(e.cadence.nextRemeasureAt).getTime() < now;

    if (ceilingPassed && !e.cadence.breached) {
      e.cadence.breached = true;
      e.cadence.breachKind = 'CEILING_EXCEEDED';

      // Yellow whose ceiling is exceeded escalates on time alone.
      if (e.currentBand === 'YELLOW') {
        const from = e.currentBand;
        e.currentBand = 'RED';
        // Cadence table also flips to Red timings.
        Object.assign(e.cadence, {
          rescoreSec: CADENCE_TABLE.RED.rescoreSec,
          remeasureSec: CADENCE_TABLE.RED.remeasureSec,
          ceilingSec: CADENCE_TABLE.RED.ceilingSec,
          nextRescoreAt: new Date(now + CADENCE_TABLE.RED.rescoreSec * 1000).toISOString(),
          nextRemeasureAt: new Date(now + CADENCE_TABLE.RED.remeasureSec * 1000).toISOString(),
        });
        emit({
          type: 'escalation',
          encounterId: e.encounterId,
          from,
          to: 'RED',
          cause: 'CEILING',
          auditId: `audit-esc-${e.encounterId}-${now}`,
        });
      } else if (e.currentBand === 'GREEN') {
        const from = e.currentBand;
        e.currentBand = 'YELLOW';
        const cadenceTable = state.surgeActive ? SURGE_CADENCE_TABLE : CADENCE_TABLE;
        Object.assign(e.cadence, {
          rescoreSec: cadenceTable.YELLOW.rescoreSec,
          remeasureSec: cadenceTable.YELLOW.remeasureSec,
          ceilingSec: cadenceTable.YELLOW.ceilingSec,
          nextRescoreAt: new Date(now + cadenceTable.YELLOW.rescoreSec * 1000).toISOString(),
          nextRemeasureAt: new Date(now + cadenceTable.YELLOW.remeasureSec * 1000).toISOString(),
        });
        emit({
          type: 'escalation',
          encounterId: e.encounterId,
          from,
          to: 'YELLOW',
          cause: 'CEILING',
          auditId: `audit-esc-${e.encounterId}-${now}`,
        });
      } else {
        emit({
          type: 'breach',
          encounterId: e.encounterId,
          kind: 'CEILING_EXCEEDED',
          bandChanged: false,
        });
      }
    } else if (remeasurePassed && !e.cadence.breached) {
      e.cadence.breached = true;
      e.cadence.breachKind = 'REMEASURE_MISSED';
      emit({
        type: 'breach',
        encounterId: e.encounterId,
        kind: 'REMEASURE_MISSED',
        bandChanged: false,
      });
    }
  }
}

function ensureTicker() {
  if (state.tickTimer !== null) return;
  state.tickTimer = setInterval(() => {
    tick();
    // Silent rescore heartbeat — a quiet stream makes the board look dead.
    const alive = state.encounters.find(e => e.state === 'waiting' && e.currentBand);
    if (alive && alive.currentBand) {
      emit({ type: 'rescore', encounterId: alive.encounterId, band: alive.currentBand, simTime: new Date(simNowMs()).toISOString() });
    }
  }, 1000);
}

function findEnc(id: string): Encounter {
  const e = state.encounters.find(p => p.encounterId === id);
  if (!e) throw new Error(`Encounter ${id} not found`);
  return e;
}

/**
 * Case-aware explanation. Each of the 20 records exists to make ONE thing
 * visible; the generic explanation would waste that. Ambiguity (P-07),
 * pulse-ox bias (P-08), geriatric context (P-04/06), stoic disagreement (P-19)
 * and inferred stratum (P-16) each get factors that a nurse would actually
 * see. Everything else falls back to a reasonable default.
 */
function generateExplanation(enc: Encounter): Explanation {
  const id = enc.encounterId;
  const c: Explanation = {
    channel1: [],
    channel2: { considered: ['Blood pressure', 'Pulse oximetry', 'Respiratory rate', 'Temperature'], discounts: [] },
    channel3: {
      narrative: enc.chiefComplaint ? [{ phrase: enc.chiefComplaint.slice(0, 80), triggered: 'complaint-match' }] : [],
      timeline: [],
    },
  };

  if (id === 'P-07') {
    c.channel1 = [
      { label: 'Epigastric pain, atypical radiation', direction: 'supports', magnitude: 0.55, source: 'text' },
      { label: 'HR 84 slightly elevated for age', direction: 'supports', magnitude: 0.35, source: 'gbdt' },
      { label: 'SpO₂ 97% and afebrile', direction: 'opposes', magnitude: 0.40, source: 'gbdt' },
    ];
    c.channel3.narrative.push({ phrase: 'nausea, could be gastritis or inferior MI', triggered: 'atypical-mi-pattern' });
    return c;
  }

  if (id === 'P-08') {
    c.channel1 = [
      { label: 'RR 26, tachypnoeic', direction: 'supports', magnitude: 0.60, source: 'gbdt' },
      { label: 'Distressed appearance on triage', direction: 'supports', magnitude: 0.45, source: 'text' },
      { label: 'SpO₂ 96% (device — no de-escalation authority)', direction: 'opposes', magnitude: 0.10, source: 'rule' },
    ];
    return c;
  }

  if (id === 'P-04') {
    c.channel1 = [
      { label: 'Temp 38.5°C — high for geriatric stratum', direction: 'supports', magnitude: 0.60, source: 'gbdt' },
      { label: 'GCS 13 — mild reduction from baseline', direction: 'supports', magnitude: 0.55, source: 'gbdt' },
      { label: 'HR 78 unremarkable', direction: 'opposes', magnitude: 0.30, source: 'gbdt' },
    ];
    c.channel2.discounts.push({
      factor: 'geriatric-stratum',
      appliesTo: 'reassuring-only',
      label: 'Geriatric stratum — reassuring self-report weighted less',
    });
    return c;
  }

  if (id === 'P-06') {
    c.channel1 = [
      { label: 'Elderly with acute confusion + hypotension', direction: 'supports', magnitude: 0.65, source: 'gbdt' },
      { label: 'RR 22, SpO₂ 93%', direction: 'supports', magnitude: 0.45, source: 'gbdt' },
      { label: 'Afebrile', direction: 'opposes', magnitude: 0.35, source: 'gbdt' },
    ];
    c.channel2.discounts.push({
      factor: 'geriatric-stratum',
      appliesTo: 'reassuring-only',
      label: 'Geriatric — atypical sepsis presentation upweighted',
    });
    return c;
  }

  if (id === 'P-13') {
    c.channel1 = [
      { label: 'Abdominal distension on exam', direction: 'supports', magnitude: 0.50, source: 'gbdt' },
      { label: 'Vitals broadly unremarkable', direction: 'opposes', magnitude: 0.30, source: 'gbdt' },
    ];
    c.channel2.discounts.push({
      factor: 'communication-barrier',
      appliesTo: 'reassuring-only',
      label: 'Communication barrier — reassuring answers cannot be verified',
    });
    return c;
  }

  if (id === 'P-19') {
    c.channel1 = [
      { label: 'HR 118, SBP 178 — physiology alarming', direction: 'supports', magnitude: 0.70, source: 'gbdt' },
      { label: 'Diaphoretic on exam', direction: 'supports', magnitude: 0.50, source: 'text' },
      { label: 'Patient reports pain 2/10', direction: 'opposes', magnitude: 0.10, source: 'text' },
    ];
    c.channel2.discounts.push({
      factor: 'stoic-flag',
      appliesTo: 'reassuring-only',
      label: 'Stoic-presentation flag set — self-report of low pain weighted down; physiology unchanged',
    });
    return c;
  }

  if (id === 'P-16') {
    c.channel1 = [
      { label: 'GCS 6, SpO₂ 88%, HR 56', direction: 'supports', magnitude: 0.90, source: 'rule' },
      { label: 'SBP 84 — hypotensive', direction: 'supports', magnitude: 0.75, source: 'gbdt' },
      { label: 'No known allergy or history', direction: 'opposes', magnitude: 0.05, source: 'history' },
    ];
    c.channel2.discounts.push({
      factor: 'non-assisted',
      appliesTo: 'reassuring-only',
      label: 'Non-assisted intake — no corroboration of self-report available',
    });
    return c;
  }

  if (id === 'P-01') {
    c.channel1 = [
      { label: 'Chest pain radiating to left arm', direction: 'supports', magnitude: 0.85, source: 'rule' },
      { label: 'Diaphoresis + HR 112', direction: 'supports', magnitude: 0.60, source: 'gbdt' },
      { label: 'Afebrile, GCS 15', direction: 'opposes', magnitude: 0.15, source: 'gbdt' },
    ];
    return c;
  }

  if (id === 'P-05') {
    c.channel1 = [
      { label: 'Mild chest discomfort at rest', direction: 'supports', magnitude: 0.50, source: 'text' },
      { label: 'HR 88, SBP 134', direction: 'supports', magnitude: 0.35, source: 'gbdt' },
      { label: 'Patient describes as "probably acidity"', direction: 'opposes', magnitude: 0.25, source: 'text' },
    ];
    return c;
  }

  // Fallback
  const supports = enc.measurements.slice(0, 2).map((m): Factor => ({
    label: `${m.code} ${m.value ?? '—'} ${m.unit}`,
    direction: 'supports',
    magnitude: 0.5,
    source: 'gbdt',
  }));
  c.channel1 = [
    ...supports,
    { label: 'No fever documented', direction: 'opposes', magnitude: 0.3, source: 'gbdt' },
  ];
  return c;
}

/**
 * Score a patient who arrived through /intake.
 *
 * The seeded records below are driven by a hand-authored PROBABILITY table
 * so the demo board is reproducible. Intake patients have no entry there,
 * and the lookup's `?? 0` fallback meant every real intake scored GREEN
 * regardless of what the patient said — a chest-pain-with-sweating red
 * flag included. These go through the deterministic risk engine instead.
 */
function generateIntakeScore(enc: Encounter): ScoreResponse {
  const pStar = 1 / (1 + state.R);
  const risk = computeRisk({
    ageStratum: enc.ageStratum,
    ageStratumInferred: enc.ageStratumInferred,
    redFlagCodes: enc.redFlagCodes ?? [],
    painScore: enc.painScore ?? null,
    measurements: enc.measurements,
    branch: enc.intakeBranch ?? null,
    humanAssignedBand: enc.humanAssignedBand,
  });

  // The conformal set widens exactly where the evidence is thin: a patient
  // still walking to the counter has no vitals, so the set spans the bands
  // those vitals would have separated.
  const conformalSet: Band[] =
    risk.band === 'RED' ? ['RED']
    : risk.confidence === 'low' ? ['GREEN', 'YELLOW', 'RED']
    : risk.band === 'YELLOW' ? ['YELLOW', 'RED']
    : ['GREEN', 'YELLOW'];

  return {
    encounterId: enc.encounterId,
    serverTime: new Date().toISOString(),
    simTime: new Date(simNowMs()).toISOString(),
    abstained: false,
    effectiveBand: risk.band,
    band: risk.band,
    probability: risk.probability,
    conformalSet,
    coverage: 0.9,
    confidence: risk.confidence,
    confidenceReducedBy: risk.confidenceReducedBy.length > 0 ? risk.confidenceReducedBy : undefined,
    inputsUsed: risk.inputsUsed,
    redFlags: risk.redFlags.length > 0 ? risk.redFlags : undefined,
    explanation: {
      channel1: risk.factors.slice(0, 3),
      channel2: {
        considered: risk.missingVitals.length > 0
          ? [`Awaiting at counter: ${risk.missingVitals.join(', ')}`]
          : ['All required vitals recorded'],
        discounts: [],
      },
      channel3: { narrative: [], timeline: [] },
    },
    suggestsReview: risk.missingVitals.length > 0,
    suggestsReviewReason: risk.missingVitals.length > 0
      ? `Scored without ${risk.missingVitals.join(', ')} — provisional until the counter records them.`
      : undefined,
    thresholdUsed: pStar,
    costRatioR: state.R,
    modelVersion: 'medipilot-v0.3-demo',
    calibrationVersion: 'site-aiims-2024Q4',
    auditId: `audit-${enc.encounterId}-${Date.now()}`,
  };
}

/**
 * Store one reading, normalising the code and computing everything that is
 * derived from it. Replaces the previous inline push, which stored the
 * caller's raw code (the dialog sent 'hr', 'bp_sys', 'temp_c') and left
 * `unit` empty for everything but temperature and `bandForStratum` unset
 * entirely — so no reading a nurse entered by hand was ever banded against
 * the patient's age stratum.
 *
 * A reading whose code is not one of the nine known vitals is still stored
 * and still rendered. It simply carries no band, and the risk engine skips
 * it: scoring a field the model has never seen would be worse than not
 * scoring it.
 */
function applyReading(
  e: Encounter,
  rawCode: string,
  value: number,
  source: string,
  takenAt: string,
  unitOverride?: string,
): void {
  const canonical = normaliseVitalCode(rawCode);
  const code = (canonical ?? rawCode.trim().toLowerCase().replace(/\s+/g, '_')) as VitalCode;
  const unit = unitOverride ?? (canonical ? VITALS[canonical].unit : '');
  const band = canonical ? bandForStratum(canonical, value, e.ageStratum) : undefined;

  // One current reading per code — the previous one is history, and the
  // card shows the latest. Superseded values stay out of the array so a
  // stale number can never be mistaken for a second sensor agreeing.
  const existing = e.measurements.findIndex(m => m.code === code);
  const reading = {
    code,
    value,
    unit,
    takenAt,
    source: source as MeasurementSource,
    validity: 'fresh' as const,
    bandForStratum: band,
  };
  if (existing >= 0) e.measurements[existing] = reading;
  else e.measurements.push(reading);
}

/**
 * Close out a counter visit: clear what is still owed, reset the
 * re-measure clock, and re-score.
 *
 * The re-score is escalate-only. Fresh vitals may raise a band; they may
 * never lower one, so a patient who came in on a red flag stays RED even
 * if every number now reads normal. Only a nurse override moves a band
 * down, and that goes through decide() with its 16-field record.
 */
function finishVitalVisit(e: Encounter): void {
  const now = simNowMs();

  const measured = new Set(
    e.measurements
      .filter(m => m.value !== null)
      .map(m => normaliseVitalCode(m.code))
      .filter((c): c is VitalCode => !!c),
  );
  const stillOwed = (e.requiredVitals ?? []).filter(c => !measured.has(c));
  e.requiredVitals = stillOwed;
  e.awaitingVitals = stillOwed.length > 0;

  if (e.intakeBranch !== undefined) {
    const risk = computeRisk({
      ageStratum: e.ageStratum,
      ageStratumInferred: e.ageStratumInferred,
      redFlagCodes: e.redFlagCodes ?? [],
      painScore: e.painScore ?? null,
      measurements: e.measurements,
      branch: e.intakeBranch ?? null,
      humanAssignedBand: e.humanAssignedBand,
    });

    const prev = e.currentBand ?? 'GREEN';
    if (BAND_RANK[risk.band] > BAND_RANK[prev]) {
      e.currentBand = risk.band;
      emit({
        type: 'escalation',
        encounterId: e.encounterId,
        from: prev,
        to: risk.band,
        cause: 'MODEL',
        auditId: `audit-${e.encounterId}-${Date.now()}`,
      });
    }
  }

  const table = state.surgeActive ? SURGE_CADENCE_TABLE : CADENCE_TABLE;
  const c = table[e.currentBand ?? 'GREEN'];
  e.cadence.rescoreSec = c.rescoreSec;
  e.cadence.remeasureSec = c.remeasureSec;
  e.cadence.ceilingSec = c.ceilingSec;
  e.cadence.nextRemeasureAt = new Date(now + c.remeasureSec * 1000).toISOString();
  e.cadence.nextRescoreAt = new Date(now + c.rescoreSec * 1000).toISOString();
  // The ceiling has to move with the band too. Leaving it at the value set
  // when the patient was GREEN would let an escalated RED keep a two-hour
  // wait ceiling — under-reporting the exact breach the ceiling exists to
  // surface. RED's ceilingSec is 0, so a RED breaches immediately by
  // design: there is no acceptable wait.
  e.cadence.ceilingBreachesAt = new Date(now + c.ceilingSec * 1000).toISOString();
  e.cadence.breached = false;
  e.cadence.breachKind = undefined;
  e.lastScoredAt = new Date(now).toISOString();
}

function generateScore(enc: Encounter): ScoreResponse {
  // Anything that came through intake carries a branch field; seeded
  // corpus records never do.
  if (enc.intakeBranch !== undefined) return generateIntakeScore(enc);

  const isAbstained = enc.encounterId === 'P-15';
  const band = enc.currentBand ?? 'YELLOW';
  const redFlags = enc.chiefComplaint ? scanRedFlags(enc.chiefComplaint) : [];
  const pStar = 1 / (1 + state.R);

  // Per-record tuning — makes the demonstration records demonstrate the
  // thing they were built to show.
  const conformalSet: Band[] =
    enc.encounterId === 'P-07' ? ['YELLOW', 'RED']            // wide → ambiguous
    : enc.encounterId === 'P-11' ? ['YELLOW', 'RED']          // zero history widens
    : band === 'RED' ? ['RED']
    : band === 'YELLOW' ? ['YELLOW', 'RED']
    : ['GREEN', 'YELLOW'];

  const confidence: 'high' | 'moderate' | 'low' =
    enc.encounterId === 'P-07' ? 'low'
    : enc.encounterId === 'P-11' ? 'low'
    : enc.encounterId === 'P-16' ? 'low'
    : enc.encounterId === 'P-09' ? 'low'   // stale vitals
    : enc.encounterId === 'P-10' ? 'low'   // sensor loss
    : band === 'RED' ? 'high' : 'moderate';

  const reducers: ScoreResponse['confidenceReducedBy'] = [];
  if (enc.ageStratumInferred) reducers.push('inferred-stratum');
  if (enc.encounterId === 'P-09') reducers.push('stale-reading');
  if (enc.encounterId === 'P-10') { reducers.push('sensor-disagreement'); reducers.push('missing-field'); }
  if (enc.encounterId === 'P-11') reducers.push('missing-field');
  if (enc.encounterId === 'P-15') reducers.push('out-of-distribution');

  return {
    encounterId: enc.encounterId,
    serverTime: new Date().toISOString(),
    simTime: new Date(simNowMs()).toISOString(),
    abstained: isAbstained,
    abstentionReason: isAbstained ? 'OUT_OF_DISTRIBUTION' : undefined,
    effectiveBand: isAbstained ? 'YELLOW' : band,      // Invariant 5
    band: isAbstained ? undefined : band,
    probability: isAbstained ? undefined : band === 'RED' ? 0.85 : band === 'YELLOW' ? 0.45 : 0.08,
    conformalSet: isAbstained ? undefined : conformalSet,
    coverage: 0.9,
    confidence: isAbstained ? undefined : confidence,
    confidenceReducedBy: reducers.length > 0 ? reducers : undefined,
    inputsUsed: isAbstained ? undefined : enc.measurements.map(m => m.code),
    redFlags: redFlags.length > 0 ? redFlags : undefined,
    explanation: isAbstained ? undefined : generateExplanation(enc),
    suggestsReview: false,
    thresholdUsed: pStar,
    costRatioR: state.R,
    modelVersion: 'medipilot-v0.3-demo',
    calibrationVersion: 'site-aiims-2024Q4',
    auditId: `audit-${enc.encounterId}-${Date.now()}`,
  };
}

// -- mock question-tree session state (see treeStart above) ---------------
let mockTreeSeq = 0;
const mockTreeSessions: Record<string, { stratum: AgeStratum; index: number; answers: Record<string, string> }> = {};

function mockTreeState(
  sessionId: string,
  qs: { id: string; label: { en: string; hi: string }; kind: string; options?: { value: string; label: { en: string; hi: string } }[] }[],
  index: number,
  answers: Record<string, string>,
): TreeState {
  const q = qs[index];
  const kindMap: Record<string, TreeState['question'] extends null ? never : 'free_text' | 'yes_no' | 'numeric_0_10'> = {
    text: 'free_text', yesno: 'yes_no', number: 'numeric_0_10', options: 'free_text',
  } as never;
  return {
    sessionId,
    question: q
      ? {
          nodeId: q.id,
          prompt: q.label.en,
          promptHi: q.label.hi,
          kind: (kindMap as Record<string, 'free_text' | 'yes_no' | 'numeric_0_10'>)[q.kind] ?? 'free_text',
          options: q.options ?? [],
        }
      : null,
    complete: index >= qs.length,
    stoppedForRedFlag: false,
    redFlagObservations: [],
    progress: { i: Math.min(index + 1, qs.length), n: qs.length },
    chiefComplaint: answers['chief-complaint'] ?? null,
    symptoms: [],
    accepted: true,
  };
}

export function createMockAdapter(): MediPilotApi {
  ensureTicker();

  return {
    // The real question tree lives in Python and is driven server-side
    // (see backend/orchestrator/tree_session.py). The mock cannot
    // reproduce it — branch selection needs the LLM structurer and the
    // red-flag table. Rather than fake a second tree that would drift
    // from the real one, the mock walks the static frontend tree in
    // lib/intake/questionTree.ts, which is what the kiosk falls back to
    // when the backend is unreachable.
    // The real tree lives in Python; the mock has no equivalent to expose.
    // Return an empty structure so the panel shows nothing rather than a
    // fabricated tree that would misrepresent the system.
    async treeStructure() {
      return { opening: [], tails: { adult: [], paediatric: [], geriatric: [] }, categories: [] };
    },

    async treeStart(input: { ageYears?: number; medicalInfoConsent: boolean; language: string }): Promise<TreeState> {
      const { questionsFor } = await import('../../intake/questionTree');
      const { resolveStratum } = await import('../../clinical/ageBands');
      const stratum = resolveStratum(input.ageYears ?? null).stratum;
      const qs = questionsFor(stratum);
      mockTreeSessions[`mock-${++mockTreeSeq}`] = { stratum, index: 0, answers: {} };
      const sessionId = `mock-${mockTreeSeq}`;
      return mockTreeState(sessionId, qs, 0, {});
    },

    async treeAnswer(sessionId: string, text: string): Promise<TreeState> {
      const { questionsFor } = await import('../../intake/questionTree');
      const s = mockTreeSessions[sessionId];
      if (!s) throw new Error(`unknown mock tree session: ${sessionId}`);
      const qs = questionsFor(s.stratum);
      const current = qs[s.index];
      if (current) s.answers[current.id] = text;
      s.index += 1;
      return mockTreeState(sessionId, qs, s.index, s.answers);
    },

    async treeAnswers(sessionId: string): Promise<Record<string, string>> {
      return mockTreeSessions[sessionId]?.answers ?? {};
    },

    // Mock never simulates the LLM matcher: unless one of the option
    // labels appears verbatim in the patient text, we return no match, so
    // the "please choose one below" hint shows just like the live path
    // would when Groq is unavailable.
    async matchOption(input) {
      const spoken = input.patientText.toLowerCase();
      const hit = input.options.find(o =>
        spoken.includes(o.label.en.toLowerCase()) || spoken.includes(o.label.hi.toLowerCase())
      );
      return { matched: hit?.value ?? null, source: 'mock', reason: hit ? 'label_in_text' : 'no_hit' };
    },

    async getConfig(): Promise<SiteConfig> {
      return {
        costRatioR: state.R,
        rBounds: { min: 10, max: 1000 },
        cadences: {
          RED: CADENCE_TABLE.RED,
          YELLOW: CADENCE_TABLE.YELLOW,
          GREEN: CADENCE_TABLE.GREEN,
          ABSTAINED: CADENCE_TABLE.ABSTAINED,
        },
        strata: [
          { stratum: 'neonate', minDays: 0, maxDays: 27 },
          { stratum: 'infant', minDays: 28, maxDays: 364 },
          { stratum: 'child', minDays: 365, maxDays: 4379 },
          { stratum: 'adolescent', minDays: 4380, maxDays: 6569 },
          { stratum: 'adult', minDays: 6570, maxDays: 23724 },
          { stratum: 'geriatric', minDays: 23725, maxDays: 999999 },
        ],
        modelVersion: 'medipilot-v0.3-demo',
        calibrationVersion: 'site-aiims-2024Q4',
      };
    },

    async getCensus(): Promise<Encounter[]> {
      // Return a deep-enough copy so React sees new references.
      return state.encounters
        .filter(e => e.state === 'waiting' || e.state === 'in-assessment')
        .map(e => ({ ...e, cadence: { ...e.cadence } }));
    },

    async getEncounter(id: string): Promise<Encounter> {
      const e = findEnc(id);
      return { ...e, cadence: { ...e.cadence } };
    },

    async score(id: string): Promise<ScoreResponse> {
      return generateScore(findEnc(id));
    },

    async getRechecks(): Promise<RecheckTask[]> {
      return state.encounters
        .filter(e => e.cadence.breached)
        .map(e => ({
          encounterId: e.encounterId,
          owner: 'station' as const,
          trust: 'full' as const,
          dueAt: e.cadence.nextRemeasureAt,
          canCloseBands: ['RED', 'YELLOW', 'GREEN'] as Band[],
        }));
    },

    async decide(input: DecisionInput): Promise<OverrideRecord> {
      const enc = findEnc(input.encounterId);
      const systemBand = enc.currentBand ?? 'YELLOW';
      const clinicianBand = input.band ?? systemBand;

      // Invariant 1 in the adapter: never lower the human-assigned floor
      // through a decision path.
      if (input.action === 'override' && input.band) {
        enc.currentBand = input.band;
        enc.humanAssignedBand = input.band;
      }
      if (input.action === 'accept' && input.band) {
        // Accepting pins the band as human-assigned, so a later re-score
        // cannot quietly drift it back down.
        enc.humanAssignedBand = input.band;
      }
      persist();

      const inputsHash = djb2Hex(JSON.stringify(enc.measurements.map(m => [m.code, m.value, m.takenAt])));
      const factorsShown = input.factorsShown ?? generateExplanation(enc).channel1;
      const scoreSnap = input.scoreAtDecision ?? { probability: 0.5, confidence: 'moderate' as const };

      const draft: OverrideRecord = {
        patientId: input.encounterId,
        timestampUtc: new Date().toISOString(),
        clinicianId: input.clinicianId,
        clinicianRole: input.clinicianRole,
        systemBand,
        clinicianBand,
        direction: BAND_RANK[clinicianBand] > BAND_RANK[systemBand] ? 'escalation' : 'de-escalation',
        reasonCode: input.reasonCode ?? 'clinical-finding-on-exam',
        reasonText: input.reasonText ?? '',
        score: scoreSnap.probability,
        confidence: scoreSnap.confidence,
        factorsShown,
        inputsHash,
        modelVersion: 'medipilot-v0.3-demo',
        calibrationVersion: 'site-aiims-2024Q4',
        consentState: enc.medicalInfoConsent ? 'full' : 'observation-only',
        outcomeRef: null,
      };

      const prevHash = state.auditHead;
      const hash = djb2Hex((prevHash ?? '') + canonical(draft));
      const record: OverrideRecord = { ...draft, prevHash, hash };
      state.audit.unshift(record);
      state.auditHead = hash;
      return record;
    },

    async getSurge(): Promise<SurgeState> {
      return {
        active: state.surgeActive,
        multiplier: state.surgeActive ? 3 : 1,
        stretched: state.surgeActive
          ? [
              { band: 'YELLOW', fromSec: 1800, toSec: 2700 },
              { band: 'GREEN', fromSec: 3600, toSec: 5400 },
            ]
          : [],
        refusals: state.surgeActive
          ? ['Will not lower any re-measurement below Red cadence', 'Will not disable OOD abstention']
          : [],
      };
    },

    async setSurge(active: boolean): Promise<SurgeState> {
      if (state.surgeActive === active) return this.getSurge();
      state.surgeActive = active;

      if (active) {
        // Inject fillers
        const fillers = generateSurgeFillers();
        state.encounters.push(...fillers);
      } else {
        // Remove fillers
        state.encounters = state.encounters.filter(e => !e.encounterId.startsWith('F-'));
      }

      // Adjust cadences
      const cadenceTable = active ? SURGE_CADENCE_TABLE : CADENCE_TABLE;
      const now = simNowMs();

      for (const e of state.encounters) {
        if (e.state !== 'waiting' || !e.currentBand) continue;

        const c = cadenceTable[e.currentBand === 'RED' ? 'RED' : e.currentBand === 'YELLOW' ? 'YELLOW' : e.currentBand === 'GREEN' ? 'GREEN' : 'ABSTAINED'];
        
        // Retain existing nextRescoreAt etc, just stretch the remeasure and ceiling
        // Note: For simplicity, we just recalculate based on the current age
        const arrivalMs = new Date(e.arrivedAt).getTime();
        e.cadence.remeasureSec = c.remeasureSec;
        e.cadence.ceilingSec = c.ceilingSec;
        e.cadence.ceilingBreachesAt = new Date(arrivalMs + c.ceilingSec * 1000).toISOString();
      }

      emit({ type: 'surge', active, multiplier: active ? 3 : 1 });
      return this.getSurge();
    },

    async getAudit(): Promise<OverrideRecord[]> {
      return [...state.audit];
    },

    async setR(R: number): Promise<RControlResponse> {
      state.R = R;
      const pStar = 1 / (1 + R);

      let up = 0;
      let down = 0;   // must stay zero — the invariant

      for (const e of state.encounters) {
        if (e.encounterId === 'P-15') continue;  // abstained never migrated by R
        if (e.state !== 'waiting') continue;

        const p = PROBABILITY[e.encounterId] ?? 0;
        const raw = bandFromProbability(p, pStar);
        const floor = floorBand(e) ?? 'GREEN';

        // I-1 in the optimiser: never fall below the floor.
        const next: Band = BAND_RANK[raw] > BAND_RANK[floor] ? raw : floor;
        const prev = e.currentBand ?? 'GREEN';

        if (BAND_RANK[next] > BAND_RANK[prev]) up++;
        if (BAND_RANK[next] < BAND_RANK[prev]) down++;  // structurally impossible

        if (next !== prev) {
          e.currentBand = next;
          // Cadence timings follow the band.
          const c = CADENCE_TABLE[next];
          const now = simNowMs();
          Object.assign(e.cadence, {
            rescoreSec: c.rescoreSec,
            remeasureSec: c.remeasureSec,
            ceilingSec: c.ceilingSec,
            nextRescoreAt: new Date(now + c.rescoreSec * 1000).toISOString(),
            nextRemeasureAt: new Date(now + c.remeasureSec * 1000).toISOString(),
            ceilingBreachesAt: new Date(now + c.ceilingSec * 1000).toISOString(),
            breached: false,
            breachKind: undefined,
          });
        }
      }

      const census = state.encounters
        .filter(e => e.state === 'waiting')
        .map(e => ({ ...e, cadence: { ...e.cadence } }))
        .sort((a, b) => BAND_RANK[b.currentBand ?? 'GREEN'] - BAND_RANK[a.currentBand ?? 'GREEN']);

      return {
        R,
        pStar,
        moved: { up, down },
        note: down === 0
          ? 'De-escalation is not available to the optimiser.'
          : 'INVARIANT LEAK — see mock.setR().',
        census,
      };
    },

    async setClockSpeed(speed: number): Promise<{ simTime: string; speed: number }> {
      // Freeze current sim clock, then re-anchor to new speed.
      state.simBaseMs = simNowMs();
      state.simEpochMs = Date.now();
      state.clockSpeed = speed;
      return { simTime: new Date(state.simBaseMs).toISOString(), speed };
    },

    async submitIntake(data: IntakeSubmission): Promise<IntakeResponse> {
      // Ids and tokens must not collide with anything already on the board,
      // including patients restored from a previous session.
      const usedIds = new Set(state.encounters.map(e => e.encounterId));
      let n = state.encounters.length + 1;
      while (usedIds.has(`P-${n}`)) n++;
      const id = `P-${n}`;

      const usedTokens = new Set(state.encounters.map(e => e.token));
      let tokenNum = 200 + state.encounters.length;
      while (usedTokens.has(String(tokenNum))) tokenNum++;
      const token = String(tokenNum);

      const now = new Date(simNowMs()).toISOString();
      const { stratum, inferred } = resolveStratum(data.ageYears ?? null);
      const flagged = data.redFlagsFired.length > 0;

      // What this presentation owes the counter before it can be scored on
      // anything but the patient's own words.
      const owed = requiredVitals({
        branch: data.branch ?? null,
        redFlagCount: data.redFlagsFired.length,
        ageStratum: stratum,
      });

      // The band the patient enters the board with, from the same engine
      // that will re-score them once the counter reports back. With no
      // measurements yet this is words-only — hence awaitingVitals.
      const risk = computeRisk({
        ageStratum: stratum,
        ageStratumInferred: inferred,
        redFlagCodes: data.redFlagsFired,
        painScore: data.painScore ?? null,
        measurements: [],
        branch: data.branch ?? null,
      });

      const cadence = CADENCE_TABLE[risk.band];
      const counter = flagged ? 'Triage Bay' : `Counter ${(state.encounters.length % 4) + 1}`;

      const newEncounter: Encounter = {
        encounterId: id,
        token,
        displayName: data.displayName,
        ageYears: data.ageYears ?? null,
        ageStratum: stratum,
        ageStratumInferred: inferred,
        sex: (data.sex as Encounter['sex']) ?? null,
        chiefComplaint: data.chiefComplaint,
        arrivedAt: now,
        arrivalMode: (data.arrivalMode as Encounter['arrivalMode']) ?? 'walk-in',
        humanAssignedBand: flagged ? 'RED' : null,
        currentBand: risk.band,
        measurements: [],
        cadence: {
          rescoreSec: cadence.rescoreSec,
          remeasureSec: cadence.remeasureSec,
          ceilingSec: cadence.ceilingSec,
          nextRescoreAt: new Date(simNowMs() + cadence.rescoreSec * 1000).toISOString(),
          nextRemeasureAt: new Date(simNowMs() + cadence.remeasureSec * 1000).toISOString(),
          ceilingBreachesAt: new Date(simNowMs() + cadence.ceilingSec * 1000).toISOString(),
          breached: false,
        },
        hasPriorRecord: false,
        assisted: data.assisted,
        humanAssistanceRequested: data.humanAssistanceRequested,
        medicalInfoConsent: data.medicalInfoConsent,
        state: 'waiting',
        lastScoredAt: now,

        intakeBranch: data.branch ?? null,
        redFlagCodes: data.redFlagsFired,
        painScore: data.painScore ?? null,
        requiredVitals: owed,
        awaitingVitals: owed.length > 0,
        counter,
        disposition: null,
      };

      state.encounters.push(newEncounter);
      persist();

      return {
        encounterId: id,
        token,
        counter,
        // Mirror the live contract: a red-flag intake never enters as GREEN.
        currentBand: risk.band,
        humanAssignedBand: flagged ? 'RED' : undefined,
        needsImmediateNurse: flagged,
        redFlagsFired: data.redFlagsFired,
        requiredVitals: owed,
      };
    },

    async structureText(text: string, language: string): Promise<StructureResponse> {
      const { scanRedFlags } = await import('@/lib/clinical/redFlags');
      const redFlags = scanRedFlags(text);
      return {
        observations: redFlags.flatMap(f => f.matchedObservations ?? []),
        redFlags,
        structuredFields: {
          chiefComplaint: text,
          onsetMinutes: null,
          // Null, not an invented band. The mock mirrors the live contract:
          // only a number the patient stated themselves belongs here.
          selfReportedSeverity: null,
          symptoms: redFlags.flatMap(f => f.matchedObservations ?? []),
          medications: [],
          pregnancyStatus: null,
          relevantHistory: [],
        },
        extraction: {
          status: 'ok',
          structurer: 'MockAdapter (client-side regex, NOT an LLM)',
          unrecognizedTerms: [],
        },
      };
    },

    async addMeasurement(encounterId: string, measurement: { code: string; value: number; source: string; takenAt: string }): Promise<Encounter> {
      const e = findEnc(encounterId);
      applyReading(e, measurement.code, measurement.value, measurement.source, measurement.takenAt);
      finishVitalVisit(e);
      persist();
      return { ...e, cadence: { ...e.cadence } };
    },

    async recordVitals(input: {
      encounterId: string;
      source: string;
      readings: { code: string; value: number; unit?: string }[];
    }): Promise<Encounter> {
      const e = findEnc(input.encounterId);
      const takenAt = new Date(simNowMs()).toISOString();

      for (const r of input.readings) {
        if (!Number.isFinite(r.value)) continue;
        applyReading(e, r.code, r.value, input.source, takenAt, r.unit);
      }

      finishVitalVisit(e);
      persist();
      return { ...e, cadence: { ...e.cadence } };
    },

    async setDisposition(input: {
      encounterId: string;
      disposition: Disposition;
      note?: string;
      clinicianId: string;
    }): Promise<Encounter> {
      const e = findEnc(input.encounterId);
      e.disposition = input.disposition;
      e.dispositionAt = new Date(simNowMs()).toISOString();
      e.dispositionBy = input.clinicianId;
      e.dispositionNote = input.note ?? null;
      // 'departed' is what removes them from the board's waiting list.
      e.state = 'departed';
      e.awaitingVitals = false;
      e.cadence.breached = false;
      e.cadence.breachKind = undefined;
      persist();
      return { ...e, cadence: { ...e.cadence } };
    },

    async transcribe(audio: Blob): Promise<TranscriptionResponse> {
      // Simulate network delay
      await new Promise(r => setTimeout(r, 1500));
      return {
        text: "This is a mock transcription from the frontend adapter.",
        language: 'en',
        languageConfidence: null,
        codeMixed: false,
        asrReliability: {
          no_speech: false,
          low_confidence: false,
          possible_hallucination: false,
          unsupported_language: false,
        },
        backend: 'mock',
      };
    },

    subscribe(handler: (e: StreamEvent) => void): () => void {
      state.handlers.add(handler);
      return () => {
        state.handlers.delete(handler);
      };
    },
  };
}
