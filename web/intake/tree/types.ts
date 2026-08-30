/**
 * The shape every question, branch and session in the tree agrees on.
 * Nothing here has behaviour — engine.ts owns the state transitions,
 * this file only owns the data shape they transition over.
 */

export type Lang = 'en' | 'hi';

export type AnswerKind = 'free_text' | 'yes_no' | 'choice' | 'scale_0_10' | 'number';

export type AgeStratum = 'neonate' | 'infant' | 'child' | 'adolescent' | 'adult' | 'geriatric';

export type BranchId =
  | 'chest_pain'
  | 'breathing'
  | 'abdominal_pain'
  | 'neuro'
  | 'fever'
  | 'trauma'
  | 'bleeding'
  | 'gi'
  | 'obstetric'
  | 'poisoning'
  | 'burn'
  | 'allergy'
  | 'urinary'
  | 'mental_behavioural'
  | 'paeds_general'
  | 'other';

export interface Bilingual {
  en: string;
  hi: string;
}

export interface Option {
  value: string;
  label: Bilingual;
}

/**
 * One node in the tree. `synonyms` is the highest-leverage field here: every
 * extra spoken form an option carries is one more answer that resolves in
 * the local matcher (match/local.ts) without ever reaching Groq. Keyed by
 * option `value`.
 */
export interface Question {
  id: string;
  kind: AnswerKind;
  prompt: Bilingual;
  /** A shorter, plain-language version read aloud instead of `prompt`
   *  when the two should differ (consent screens, mainly). Falls back
   *  to `prompt` when absent. */
  spoken?: Bilingual;
  options?: Option[];
  synonyms?: Record<string, string[]>;
  /** Overrides the AnswerKind-default silence window (voice/vad.ts). */
  silenceMs?: number;
  /** `number` questions only: the plausible answer range, inclusive.
   *  Anything outside it is treated as a recognition error and rejected
   *  rather than accepted — an age of 300 would resolve the wrong age
   *  stratum, and every vital threshold downstream depends on it.
   *  Defaults to [0, 120]. */
  numberRange?: [number, number];
  /** Gate: only ask this question if the predicate holds against the
   *  session collected so far. Used for stratum gates, sex gates, and
   *  skip-if-already-known. */
  askIf?: (s: SessionAnswers) => boolean;
  /**
   * Red-flag observation codes a yes/no answer to THIS question
   * establishes directly. Needed because the literal answer is the word
   * "yes" or "no" and contains none of the phrases the tier A text scan
   * looks for — "are you sweating?" / "yes" must still fire RF-03.
   */
  observes?: string[];
  /**
   * WHICH answer is the alarming one. Defaults to 'yes', but a question
   * phrased positively inverts it: "Can you speak in full sentences?" and
   * "Is the child feeding normally?" are red flags when the answer is NO.
   *
   * Getting this backwards fails in the worst possible direction — a
   * patient answering truthfully would suppress the alert rather than
   * raise it — so it is explicit on every inverted question rather than
   * inferred from the wording.
   */
  observeOn?: 'yes' | 'no';
  /**
   * Calls a nurse on this answer without claiming one of the eight
   * physiological codes. For situations that genuinely need a person now
   * but are not in config/red_flags.yaml — self-harm risk being the one
   * that matters. We route the patient to a human rather than inventing a
   * clinical code the band engine does not recognise.
   */
  urgentOn?: 'yes' | 'no';
}

export interface Branch {
  id: BranchId;
  label: Bilingual;
  questions: Question[];
}

/** Everything answered so far, keyed by question id. Free text and
 *  transcribed values are stored as strings; scale/number as numeric
 *  strings — the tree never needs typed values, only display and match. */
export type SessionAnswers = Record<string, string> & {
  /** Not a question id — populated once age is known, read by every
   *  downstream askIf gate. Absent until Basics is answered. */
  __stratum?: AgeStratum;
  __sex?: 'M' | 'F' | 'O';
};

export type OpeningStepId =
  | 'welcome'
  | 'companion'
  | 'human-offer'
  | 'consent'
  | 'basics'
  | 'conversation'
  | 'pain'
  | 'readback'
  | 'token'
  | 'human-lane';

export interface RedFlagObservation {
  code: string;
  description: Bilingual;
}

export interface SessionState {
  lang: Lang;
  step: OpeningStepId;

  assisted: boolean | null;
  wantsHuman: boolean | null;
  consent: { listen: boolean; records: boolean };
  ageYears: number | null;
  sex: 'M' | 'F' | 'O' | null;
  stratum: AgeStratum | null;

  branch: BranchId | null;
  /** The ordered list of question ids still to ask, in the current
   *  branch + tail. Consumed from the front as questions are answered. */
  plan: string[];
  /** Index into `plan` of the question on screen right now. */
  cursor: number;
  answers: SessionAnswers;

  chiefComplaint: string;
  painScore: number | null;

  redFlags: RedFlagObservation[];
  /** Set the moment a red flag fires — every clinical question stops and
   *  NurseCall takes over regardless of what `step`/`plan` say. */
  needsImmediateNurse: boolean;
  nurseCalledAt: string | null;
  /** True when the nurse call came from an `urgentOn` question rather than
   *  a red-flag code. Submitted as a human-assistance request, NOT as a
   *  fabricated red flag — the band engine keys off the eight codes and
   *  must not be handed one we cannot substantiate. */
  urgentWithoutCode: boolean;

  readbackConfirmed: boolean;
  token: string | null;
  counter: string | null;
  /** VitalCodes the counter will measure, echoed back by submitIntake so
   *  the token screen can tell the patient what is about to happen. */
  requiredVitals: string[];
  submitting: boolean;
  submitError: string | null;
}

export const INITIAL_SESSION: SessionState = {
  lang: 'en',
  step: 'welcome',
  assisted: null,
  wantsHuman: null,
  consent: { listen: true, records: true },
  ageYears: null,
  sex: null,
  stratum: null,
  branch: null,
  plan: [],
  cursor: 0,
  answers: {},
  chiefComplaint: '',
  painScore: null,
  redFlags: [],
  needsImmediateNurse: false,
  nurseCalledAt: null,
  urgentWithoutCode: false,
  readbackConfirmed: false,
  token: null,
  counter: null,
  requiredVitals: [],
  submitting: false,
  submitError: null,
};
