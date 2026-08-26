import type {
  MediPilotApi, Encounter, ScoreResponse, SurgeState, RecheckTask,
  OverrideRecord, RControlResponse, SiteConfig, DecisionInput,
  StreamEvent, Band, Factor, Explanation,
} from '../types';
import { BAND_RANK } from '../types';
import { CORPUS } from '../../seed/corpus';
import { scanRedFlags } from '../../clinical/redFlags';
import { CADENCE_TABLE, SURGE_CADENCE_TABLE } from '../../clinical/safeWait';
import { generateSurgeFillers } from '../../seed/surgeFillers';

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

const state: State = {
  encounters: CORPUS.map(e => ({ ...e, cadence: { ...e.cadence } })),
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

function generateScore(enc: Encounter): ScoreResponse {
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

export function createMockAdapter(): MediPilotApi {
  ensureTicker();

  return {
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
      const id = `P-${state.encounters.length + 1}`;
      const token = `${200 + state.encounters.length}`;
      const now = new Date(simNowMs()).toISOString();
      const newEncounter = {
        id,
        token,
        displayName: data.displayName,
        ageYears: data.ageYears,
        ageStratum: data.ageYears ? 'adult' as AgeStratum : 'adult' as AgeStratum,
        ageStratumInferred: !data.ageYears,
        sex: data.sex,
        chiefComplaint: data.chiefComplaint,
        arrivedAt: now,
        state: 'waiting' as const,
        currentBand: 'GREEN' as Band,
        humanAssignedBand: undefined,
        measurements: [],
        cadence: {
          rescoreSec: 300,
          remeasureSec: 3600,
          ceilingSec: 7200,
          nextRescoreAt: now,
          nextRemeasureAt: now,
          ceilingBreachesAt: now,
          breached: false,
        },
        redFlagObservations: data.redFlagsFired,
        reliabilityFlags: {},
      };
      state.encounters.push(newEncounter);
      
      const res: IntakeResponse = {
        encounterId: id,
        token,
        currentBand: 'GREEN',
        humanAssignedBand: undefined,
      };
      return res;
    },

    async structureText(text: string, language: string): Promise<StructureResponse> {
      const { scanRedFlags } = await import('@/lib/clinical/redFlags');
      const redFlags = scanRedFlags(text);
      return {
        observations: redFlags.length > 0 ? ['mock_observation_1'] : [],
        redFlags,
        structuredFields: {
          chiefComplaint: text,
          onsetMinutes: null,
          severity: redFlags.length > 0 ? 'severe' : 'moderate',
        }
      };
    },

    async addMeasurement(encounterId: string, measurement: { code: string; value: number; source: string; takenAt: string }): Promise<Encounter> {
      const e = state.encounters.find(x => x.id === encounterId);
      if (!e) throw new Error('Not found');
      
      const valStr = String(measurement.value);
      e.measurements.push({
        code: measurement.code,
        value: valStr,
        unit: measurement.code === 'TEMP_C' ? '°C' : '',
        takenAt: measurement.takenAt,
        source: measurement.source,
        validity: 'fresh'
      });
      
      const now = simNowMs();
      if (e.cadence) {
        e.cadence.nextRemeasureAt = new Date(now + e.cadence.remeasureSec * 1000).toISOString();
      }
      return e;
    },

    async transcribe(audio: Blob): Promise<{ text: string }> {
      // Simulate network delay
      await new Promise(r => setTimeout(r, 1500));
      return { text: "This is a mock transcription from the frontend adapter." };
    },

    subscribe(handler: (e: StreamEvent) => void): () => void {
      state.handlers.add(handler);
      return () => {
        state.handlers.delete(handler);
      };
    },
  };
}
