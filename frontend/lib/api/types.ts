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

  // -- Intake → counter → board handoff ------------------------------------

  /** Which intake tree branch routed this complaint. Drives which vitals
   *  the counter is asked to capture. Null for corpus-seeded patients. */
  intakeBranch?: string | null;
  /** The ObservationCodes intake fired, kept so a re-score can reproduce
   *  the RED without re-reading the free text. */
  redFlagCodes?: string[];
  /** 0-10 as the patient stated it during intake. Never inferred. */
  painScore?: number | null;
  /** Vitals this presentation owes before it can be scored on more than
   *  words. Empty once every one of them has a fresh reading. */
  requiredVitals?: VitalCode[];
  /** True between "token issued" and "counter recorded the vitals". The
   *  patient is ON the board throughout — they are physically in the
   *  department — but the board marks the score as provisional. */
  awaitingVitals?: boolean;
  /** Which counter the patient was sent to for those vitals. */
  counter?: string | null;

  // -- Departure -----------------------------------------------------------

  /** Set when a nurse closes the encounter. Until this exists the patient
   *  stays on the board across reloads — that is the whole point: a
   *  patient may only leave the queue because a human said so. */
  disposition?: Disposition | null;
  dispositionAt?: string | null;
  dispositionBy?: string | null;
  dispositionNote?: string | null;
}

/** How an encounter left the queue. `left-without-being-seen` is recorded
 *  as explicitly as a discharge — an untracked disappearance is the thing
 *  a triage board exists to make impossible. */
export type Disposition =
  | 'discharged-home'
  | 'admitted'
  | 'referred-out'
  | 'left-without-being-seen'
  | 'treatment-complete';

export const DISPOSITIONS: { value: Disposition; label: string; hint: string }[] = [
  { value: 'treatment-complete',      label: 'Treatment complete', hint: 'Seen and treated in the department' },
  { value: 'discharged-home',         label: 'Discharged home',    hint: 'Sent home after assessment' },
  { value: 'admitted',                label: 'Admitted',           hint: 'Moved to a ward or ICU bed' },
  { value: 'referred-out',            label: 'Referred out',       hint: 'Transferred to another facility' },
  { value: 'left-without-being-seen', label: 'Left without being seen', hint: 'Patient departed before assessment' },
];

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
  /** RF-01..RF-08 from the backend's fixed table (intake/red_flags.py).
   *  Absent when the flag came from the client-side scanner. */
  ruleId?: string;
  /** The ObservationCodes that actually matched the rule. */
  matchedObservations?: string[];
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
  /** Intake tree branch, so the counter knows which vitals to capture. */
  branch?: string | null;
  /** 0-10 as stated by the patient on the pain screen. */
  painScore?: number | null;
}

export interface IntakeResponse {
  encounterId: string;
  token: string;
  /** Where the patient physically goes ("Counter 3", "Triage Bay"). A
   *  token says they are queued; this says where to stand. */
  counter?: string;
  currentBand: Band;
  humanAssignedBand?: Band;
  /** True when intake fired a red-flag rule mid-conversation. The kiosk
   *  must skip the queue screen and jump straight to "a nurse is coming to
   *  you now" with the token, because the fixed table (intake/red_flags.py)
   *  has already established this is a nurse-now case. */
  needsImmediateNurse?: boolean;
  /** RF-01..RF-08 identifiers that fired, in order of appearance. */
  redFlagsFired?: string[];
  /** Vitals the counter must capture for this presentation. The kiosk
   *  renders these as icons on the token screen so the patient knows what
   *  is about to happen to them before it happens. Empty means the
   *  complaint needs no measurement and the patient just waits. */
  requiredVitals?: VitalCode[];
}

export interface StructureResponse {
  /** ObservationCodes the structurer (M06) extracted, from a closed vocabulary. */
  observations: string[];
  /** Verdicts from the deterministic table (M07), never from the model. */
  redFlags: RedFlag[];
  structuredFields: {
    chiefComplaint: string;
    onsetMinutes: number | null;
    /** The 0-10 number the patient stated themselves, or null if they gave none.
     *  This replaced a `severity: string` the backend used to invent
     *  ("severe" whenever anything was extracted) — M06 asserting acuity,
     *  which Invariant 2 forbids. Never estimated from descriptive language. */
    selfReportedSeverity: number | null;
    symptoms: string[];
    medications: string[];
    pregnancyStatus: boolean | null;
    relevantHistory: string[];
  };
  extraction: {
    status: 'ok' | 'malformed' | 'empty_input' | 'error';
    /** Which extractor actually ran. "RuleBasedStructurer" means the
     *  deterministic keyword fallback, NOT an LLM — surfaced so the demo
     *  never claims LLM extraction it did not perform. */
    structurer: string;
    unrecognizedTerms: string[];
  };
}

/** POST /v1/speech/transcribe. `text` is the transcript in the language
 *  spoken — never translated. The rest is ASR-observable metadata only and
 *  carries no clinical meaning. */
export interface TranscriptionResponse {
  text: string;
  language: string | null;
  languageConfidence: number | null;
  codeMixed: boolean;
  asrReliability: {
    no_speech: boolean;
    low_confidence: boolean;
    possible_hallucination: boolean;
    unsupported_language: boolean;
  };
  backend: string;
}

/**
 * One node of the REAL backend question tree (intake/question_tree.py),
 * served turn-by-turn over /v1/intake/tree/*. Unlike the static frontend
 * tree in lib/intake/questionTree.ts, which question arrives next is
 * decided server-side — it depends on what the LLM structurer extracted,
 * what the patient already volunteered, and whether the red-flag table
 * has fired. See backend/orchestrator/tree_session.py.
 */
export interface TreeQuestion {
  nodeId: string;
  prompt: string;
  /** Null for most nodes today — the backend tree's ~140 clinical prompts
   *  are not yet translated. Callers must fall back to `prompt`. */
  promptHi: string | null;
  kind: 'free_text' | 'yes_no' | 'numeric_0_10';
  options: { value: string; label: { en: string; hi: string } }[];
}

export interface TreeState {
  sessionId: string;
  question: TreeQuestion | null;
  complete: boolean;
  /** The tree truncated itself because red_flags.py confirmed a
   *  time-critical presentation — route to a nurse, stop asking. */
  stoppedForRedFlag: boolean;
  redFlagObservations: string[];
  progress: { i: number; n: number };
  chiefComplaint: string | null;
  symptoms: string[];
  /** A snapshot of the plan as it currently stands: the ordered questions,
   *  each labelled as already-answered, the one being asked now, or
   *  upcoming. The list grows when a branch splices in and truncates when
   *  the red-flag table fires -- both are correct outcomes to show. */
  plan?: {
    nodeId: string;
    prompt: string;
    promptHi: string | null;
    kind: 'free_text' | 'yes_no' | 'numeric_0_10';
    status: 'done' | 'current' | 'upcoming';
  }[];
  /** Which ComplaintCategory the chief complaint routed to, once known. */
  branch?: string | null;
  stratum?: string | null;
  /** False when a yes/no or 0-10 answer could not be parsed: the SAME
   *  question is repeated and nothing was recorded. Not an error. */
  accepted?: boolean;
  note?: string;
}

/** One node of the tree structure, with its conditional follow-ups. */
export interface TreeStructureNode {
  nodeId: string;
  prompt: string;
  promptHi: string | null;
  kind: 'free_text' | 'yes_no' | 'numeric_0_10';
  requiresConsent: boolean;
  impliesSymptom: string | null;
  followUpTriggers: string[];
  followUps: TreeStructureNode[];
}

/** The whole decision tree, session-independent — every category and its
 *  question block. Powers the "All branches" view of the tree panel,
 *  which is what actually shows the routing; a single patient's linear
 *  plan does not. */
export interface TreeStructure {
  opening: TreeStructureNode[];
  tails: {
    adult: TreeStructureNode[];
    paediatric: TreeStructureNode[];
    geriatric: TreeStructureNode[];
  };
  categories: {
    name: string;
    symptomCodes: string[];
    keywordSample: string[];
    questions: TreeStructureNode[];
  }[];
}

export interface MediPilotApi {
  getConfig(): Promise<SiteConfig>;
  treeStructure(): Promise<TreeStructure>;
  treeStart(input: { ageYears?: number; medicalInfoConsent: boolean; language: string }): Promise<TreeState>;
  treeAnswer(sessionId: string, text: string): Promise<TreeState>;
  treeAnswers(sessionId: string): Promise<Record<string, string>>;
  /** LLM-assisted fallback for option questions when the local Jaccard
   *  matcher couldn't decide. Never called on every keystroke -- only
   *  when the local score is below its threshold. */
  matchOption(input: {
    questionPrompt: string;
    patientText: string;
    options: { value: string; label: { en: string; hi: string } }[];
  }): Promise<{ matched: string | null; source: string; reason: string }>;
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
  /** Record several readings as ONE counter visit. Distinct from looping
   *  addMeasurement: the re-score and the cadence reset happen once, after
   *  the whole set lands, so a patient never transiently scores against a
   *  half-entered set of vitals. */
  recordVitals(input: {
    encounterId: string;
    source: string;
    readings: { code: string; value: number; unit?: string }[];
  }): Promise<Encounter>;
  /** Close an encounter. The ONLY way a patient leaves the board. */
  setDisposition(input: {
    encounterId: string;
    disposition: Disposition;
    note?: string;
    clinicianId: string;
  }): Promise<Encounter>;
  transcribe(audio: Blob): Promise<TranscriptionResponse>;
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
