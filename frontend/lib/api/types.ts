/**
 * MediPilot API contract — v0.2
 *
 * Shared verbatim with the backend team. See BACKEND_INTEGRATION_LOG.md.
 * Corrected against the R2 system plan: two clocks, six age strata, the
 * measurement tuple, the Yellow abstention floor, and the 16-field override
 * record.
 *
 * Nothing in the app talks to the backend except through `lib/api/client.ts`.
 */

// ---------------------------------------------------------------------------
// Bands and strata
// ---------------------------------------------------------------------------

/** AIIMS Triage Protocol, three tiers. Chosen over a 5-level scale: see plan §03. */
export type Band = 'RED' | 'YELLOW' | 'GREEN';

/** Higher is more urgent. Used for the escalate-only comparison. */
export const BAND_RANK: Record<Band, number> = { RED: 3, YELLOW: 2, GREEN: 1 };

export type AgeStratum =
  | 'neonate'      // < 28 d
  | 'infant'       // 28 d – 1 y
  | 'child'        // 1 – 12 y
  | 'adolescent'   // 12 – 18 y
  | 'adult'        // 18 – 65 y
  | 'geriatric';   // 65 y +

// ---------------------------------------------------------------------------
// Measurements — Invariant 4: freshness is part of the value
// ---------------------------------------------------------------------------

/**
 * `discounted` past 2x the band's re-measure cadence, `expired` past 3x.
 * The renderer shows an expired measurement as MISSING, never as a stale number.
 */
export type Validity = 'fresh' | 'discounted' | 'expired';

/** Who produced the reading. Drives how much the board trusts it. */
export type MeasurementSource =
  | 'station'    // instrumented bay, timestamped at source
  | 'device'
  | 'nurse'
  | 'attendant'
  | 'family'     // partial trust — cannot close a Yellow or Red recheck
  | 'patient';   // signal only — can escalate, never satisfies a recheck

export type VitalCode =
  | 'HR' | 'SBP' | 'DBP' | 'RR' | 'SPO2' | 'TEMP' | 'GCS' | 'RBS' | 'PAIN';

export interface Measurement {
  code: VitalCode;
  value: number | null;
  unit: string;
  takenAt: string;            // ISO-8601 UTC
  source: MeasurementSource;
  validity: Validity;
  /** Computed against the resolved stratum — never against an adult default. */
  bandForStratum?: 'below' | 'low' | 'normal' | 'high' | 'above';
  /**
   * False where a normal reading carries no downward authority — the pulse
   * oximetry bias case. Absence of the flag is not permission.
   */
  deEscalationAuthority?: boolean;
}

// ---------------------------------------------------------------------------
// The two clocks plus the ceiling — system plan §8
// ---------------------------------------------------------------------------

export type BreachKind =
  | 'REMEASURE_MISSED'
  | 'CEILING_EXCEEDED'
  | 'UNMET_REVIEW';

/**
 * Re-scoring is the model running again (cheap, never rationed).
 * Re-measurement is a human taking fresh vitals (scarce, rationed by band).
 * The ceiling is a third, independent trigger: time in queue alone forces
 * action regardless of whether any number moved.
 */
export interface Cadence {
  rescoreSec: number;         // RED 60, others 300
  remeasureSec: number;       // RED 300, YELLOW 1800, GREEN 3600
  ceilingSec: number;         // RED 0, YELLOW 3600, GREEN 7200, abstained 900
  nextRescoreAt: string;
  nextRemeasureAt: string;
  ceilingBreachesAt: string;
  breached: boolean;
  breachKind?: BreachKind;
}

export type RecheckOwner = 'station' | 'nurse' | 'attendant' | 'family' | 'patient';
export type RecheckTrust = 'full' | 'partial' | 'signal-only';

export interface RecheckTask {
  encounterId: string;
  owner: RecheckOwner;
  trust: RecheckTrust;
  dueAt: string;
  /** Family may close Green only. Patient self-report closes nothing. */
  canCloseBands: Band[];
}

// ---------------------------------------------------------------------------
// Reliability — system plan §7, asymmetric by construction
// ---------------------------------------------------------------------------

export type ReliabilityFactor =
  | 'geriatric-stratum'
  | 'communication-barrier'
  | 'health-literacy'
  | 'stoic-flag'           // clinician-set, one tap. Never model-guessed.
  | 'non-assisted'
  | 'analgesia-given';

/**
 * A discount lowers the evidential weight of a REASSURING answer. It never
 * lowers the weight of an alarming one. "No chest pain" from a low-reliability
 * context is weak evidence of absence; "chest pain" is full-strength evidence
 * of presence. `appliesTo` is a constant to make that unmissable in review.
 */
export interface ReliabilityDiscount {
  factor: ReliabilityFactor;
  appliesTo: 'reassuring-only';
  label: string;            // rendered verbatim in explanation channel 2
}

// ---------------------------------------------------------------------------
// Encounter
// ---------------------------------------------------------------------------

export interface Encounter {
  encounterId: string;      // P-01 … P-20
  token: string;            // the only identifier shown on public displays
  displayName: string | null;
  ageYears: number | null;
  ageStratum: AgeStratum;             // Invariant 3 — always present
  ageStratumInferred: boolean;        // true => widest-safety, confidence pinned down
  sex: 'M' | 'F' | 'O' | null;
  chiefComplaint: string | null;
  arrivedAt: string;
  arrivalMode: 'walk-in' | 'ambulance' | 'referral' | 'brought-by-bystander';

  /** The floor for Invariant 1. The system may never recommend below this. */
  humanAssignedBand: Band | null;
  currentBand: Band | null;

  measurements: Measurement[];
  cadence: Cadence;

  hasPriorRecord: boolean;
  assisted: boolean;                  // "is anyone with you?" — intake step 1
  humanAssistanceRequested: boolean;  // intake step 2, offered BEFORE proceeding alone
  medicalInfoConsent: boolean;        // intake step 3. false => observation-only, no penalty

  state: 'waiting' | 'in-assessment' | 'in-treatment' | 'departed';
  lastScoredAt: string | null;
}

// ---------------------------------------------------------------------------
// Scoring
// ---------------------------------------------------------------------------

export type AbstentionReason =
  | 'CONFORMAL_SET_TOO_WIDE'
  | 'OUT_OF_DISTRIBUTION'
  | 'MISSING_CRITICAL_FIELDS';

export type ConfidenceReducer =
  | 'missing-field'
  | 'stale-reading'
  | 'inferred-stratum'
  | 'sensor-disagreement'
  | 'out-of-distribution';

export interface Factor {
  label: string;
  direction: 'supports' | 'opposes';
  magnitude: number;                 // ordering only — never rendered as a percentage
  source: 'gbdt' | 'trend' | 'text' | 'history' | 'rule';
}

/**
 * A red flag maps an extracted observation to RED through a fixed table.
 * The LLM reports what was said; it does not decide what it means.
 * `lockedDownward` is always true: no later model output may lower this.
 */
export interface RedFlag {
  observation: string;
  mapsTo: 'RED';
  lockedDownward: true;
}

export interface TimelineEvent {
  at: string;
  kind: 'band-change' | 'alarm' | 'stale-reading' | 'missed-recheck' | 'override';
  detail: string;
}

/** System plan §12 — three channels, absorbable in seconds. */
export interface Explanation {
  /** Two strongest contributors plus exactly one arguing the other way. */
  channel1: Factor[];
  /** What was considered and did not move it, plus every discount BY NAME. */
  channel2: { considered: string[]; discounts: ReliabilityDiscount[] };
  /** Narrative contribution kept separate from the timeline. */
  channel3: { narrative: { phrase: string; triggered: string }[]; timeline: TimelineEvent[] };
}

export interface ScoreResponse {
  encounterId: string;
  serverTime: string;
  simTime: string;                   // the backend owns the simulated clock

  abstained: boolean;
  abstentionReason?: AbstentionReason;
  /** Invariant 5 — YELLOW floor when abstained. Never GREEN. */
  effectiveBand: Band;

  band?: Band;
  probability?: number;
  conformalSet?: Band[];             // width IS the message
  coverage?: number;
  confidence?: 'high' | 'moderate' | 'low';
  confidenceReducedBy?: ConfidenceReducer[];
  inputsUsed?: string[];             // Invariant 2 — a score names its inputs

  redFlags?: RedFlag[];
  explanation?: Explanation;

  /** Invariant 1 — model believes lower but will not say lower. */
  suggestsReview?: boolean;
  suggestsReviewReason?: string;

  thresholdUsed: number;             // p* = 1 / (1 + R)
  costRatioR: number;
  modelVersion: string;
  calibrationVersion: string;
  auditId: string;
}

// ---------------------------------------------------------------------------
// Override record — all 16 fields, system plan §13. Rendered verbatim.
// ---------------------------------------------------------------------------

export type OverrideDirection = 'escalation' | 'de-escalation' | 'same-band-override';

export interface OverrideRecord {
  patientId: string;
  timestampUtc: string;
  clinicianId: string;
  clinicianRole: string;
  systemBand: Band;
  clinicianBand: Band;
  direction: OverrideDirection;
  reasonCode: string;
  reasonText: string;
  score: number;
  confidence: 'high' | 'moderate' | 'low';
  /** The card AS DISPLAYED — not a recomputation. Establishes what they were told. */
  factorsShown: Factor[];
  inputsHash: string;
  modelVersion: string;
  calibrationVersion: string;
  consentState: string;
  outcomeRef: string | null;         // back-filled when known

  /**
   * Hash-chain envelope. Not part of the 16 legal fields — they wrap it.
   * Every row: hash = H(prevHash || canonical(record)). See BACKEND_INTEGRATION §8.
   */
  hash?: string;
  prevHash?: string | null;
}

/** Structured reason codes offered in the override dialog. Site-configurable. */
export const OVERRIDE_REASON_CODES: {
  code: string;
  label: string;
  escalationOnly?: boolean;
  deescalationOnly?: boolean;
}[] = [
  { code: 'clinical-finding-on-exam',       label: 'Clinical finding on examination' },
  { code: 'deteriorating-vital-trend',      label: 'Deteriorating vital trend', escalationOnly: true },
  { code: 'red-flag-symptom-reported',      label: 'Red-flag symptom reported after intake', escalationOnly: true },
  { code: 'suspected-serious-diagnosis',    label: 'Suspected serious diagnosis', escalationOnly: true },
  { code: 'known-comorbidity',              label: 'Known comorbidity changes risk' },
  { code: 'protocol-mandated-escalation',   label: 'Protocol-mandated escalation (AIIMS-ATP)', escalationOnly: true },
  { code: 'resolution-on-reassessment',     label: 'Resolution on nurse re-assessment', deescalationOnly: true },
  { code: 'symptom-resolved-benign-cause',  label: 'Symptom resolved / benign cause established', deescalationOnly: true },
  { code: 'model-context-mismatch',         label: 'Model context mismatch (site or population)' },
  { code: 'other-with-note',                label: 'Other — see free-text note' },
];

// ---------------------------------------------------------------------------
// Surge — system plan §11
// ---------------------------------------------------------------------------

export interface SurgeState {
  active: boolean;
  multiplier: number;
  /** Red re-measurement is the one cadence surge never touches. */
  stretched: { band: Band; fromSec: number; toSec: number }[];
  /** Rendered on the board so the refusals are visible, not merely claimed. */
  refusals: string[];
}

// ---------------------------------------------------------------------------
// The R control — a graded submission-gate item, system plan §02
// ---------------------------------------------------------------------------

export interface RControlResponse {
  R: number;
  pStar: number;
  /** `down` is structurally zero. If it is ever non-zero, Invariant 1 is leaking. */
  moved: { up: number; down: number };
  note: string;
  census: Encounter[];
}

// ---------------------------------------------------------------------------
// The interface every adapter implements
// ---------------------------------------------------------------------------

export interface IntakeSubmission {
  displayName: string;
  ageYears?: number;
  sex?: string;
  chiefComplaint: string;
  arrivalMode: string;
  assisted: boolean;
  humanAssistanceRequested: boolean;
  medicalInfoConsent: boolean;
  listeningConsent: boolean;
  language: string;
  symptomAnswers: Record<string, string>;
  redFlagsFired: string[];
}

export interface IntakeResponse {
  encounterId: string;
  token: string;
  currentBand: Band;
  humanAssignedBand?: Band;
}

export interface StructureResponse {
  observations: string[];
  redFlags: RedFlag[];
  structuredFields: {
    chiefComplaint: string;
    onsetMinutes: number | null;
    severity: string;
  };
}

export interface MediPilotApi {
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
  submitIntake(data: IntakeSubmission): Promise<IntakeResponse>;
  structureText(text: string, language: string): Promise<StructureResponse>;
  addMeasurement(encounterId: string, measurement: { code: string; value: number; source: string; takenAt: string }): Promise<Encounter>;
  transcribe(audio: Blob): Promise<{ text: string }>;
}

export interface SiteConfig {
  costRatioR: number;
  rBounds: { min: number; max: number };
  cadences: Record<Band | 'ABSTAINED', Omit<Cadence, 'nextRescoreAt' | 'nextRemeasureAt' | 'ceilingBreachesAt' | 'breached' | 'breachKind'>>;
  strata: { stratum: AgeStratum; minDays: number; maxDays: number }[];
  modelVersion: string;
  calibrationVersion: string;
}

export interface DecisionInput {
  encounterId: string;
  action: 'accept' | 'override';
  band?: Band;
  reasonCode?: string;
  reasonText?: string;
  clinicianId: string;
  clinicianRole: string;
  /**
   * The card AS DISPLAYED. Passed from the frontend so `factorsShown` records
   * what the clinician was actually told, not what the backend can recompute.
   */
  factorsShown?: Factor[];
  /** Preview snapshot: score & confidence at the moment of decision. */
  scoreAtDecision?: { probability: number; confidence: 'high' | 'moderate' | 'low' };
}

export type StreamEvent =
  | { type: 'rescore'; encounterId: string; band: Band; simTime: string }
  | { type: 'escalation'; encounterId: string; from: Band; to: Band; cause: 'MODEL' | 'CEILING' | 'RED_FLAG'; auditId: string }
  | { type: 'breach'; encounterId: string; kind: BreachKind; bandChanged: boolean }
  | { type: 'recheckDue'; encounterId: string; owner: RecheckOwner }
  | { type: 'surge'; active: boolean; multiplier: number };
// NOTE: there is deliberately no 'deescalation' event. Downward movement
// reaches the frontend only as a human decision. See Invariant 1.
