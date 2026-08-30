import { NextResponse } from 'next/server';
import { matchLocal, matchNumber, matchScale, ACCEPT_THRESHOLD } from '@/intake/match/local';
import { detectRedFlagsLocal } from '@/intake/redflags/detect';
import { localClassify } from '@/intake/tree/localClassify';
import { getBranch } from '@/intake/tree';
import type { Question, SessionState } from '@/intake/tree/types';
import { INITIAL_SESSION } from '@/intake/tree/types';
import { submitAnswer, goBackOne, canGoBack } from '@/intake/tree/engine';
import { validateBranch, validateMatch, validateObserve } from '@/intake/server/validate';
import { groqConfigured, intakeOffline } from '@/intake/server/groq';
import { answerModeFor, buildSpokenPrompt } from '@/intake/voice/answerMode';
import { computeRisk } from '@/lib/clinical/riskEngine';
import { normaliseVitalCode } from '@/lib/clinical/vitals';

/**
 * Fixture check for the offline layers — the matcher (tiers 0/1), the
 * red-flag phrase table, and the branch classifier. Stands in for a real
 * test runner, which the project does not have installed yet; hit
 * GET /api/intake/selftest in dev and every row is reported pass/fail.
 *
 * Development only: returns 404 in production so it cannot ship as a
 * public endpoint.
 */

const cp = getBranch('chest_pain');
const q = (id: string) => cp.questions.find((x) => x.id === id) as Question;

const YES_NO: Question = { id: 'yn', kind: 'yes_no', prompt: { en: '', hi: '' } };
const SCALE: Question = { id: 'sc', kind: 'scale_0_10', prompt: { en: '', hi: '' } };

const MATCH_CASES: [Question, string, string | null][] = [
  // tier 0 — yes/no, both languages + romanised
  [YES_NO, 'yes', 'yes'], [YES_NO, 'yeah', 'yes'], [YES_NO, 'haan', 'yes'],
  [YES_NO, 'हां', 'yes'], [YES_NO, 'ji haan', 'yes'], [YES_NO, 'bilkul', 'yes'],
  [YES_NO, 'no', 'no'], [YES_NO, 'nahi', 'no'], [YES_NO, 'नहीं', 'no'],
  [YES_NO, 'not really', 'no'], [YES_NO, 'nope', 'no'],
  // negation must beat affirmation
  [YES_NO, 'no not really', 'no'],
  // tier 0 — scale
  [SCALE, '7', '7'], [SCALE, 'seven', '7'], [SCALE, 'saat', '7'],
  [SCALE, 'सात', '7'], [SCALE, 'about a seven', '7'], [SCALE, '१०', '10'],
  [SCALE, 'ten out of ten', '10'], [SCALE, 'zero', '0'],
  // tier 1 — onset choices via labels
  [q('cp_onset'), 'just now', 'just_now'],
  [q('cp_onset'), 'abhi', 'just_now'],
  [q('cp_onset'), 'right now', 'just_now'],
  [q('cp_onset'), 'within the last hour', 'within_hour'],
  [q('cp_onset'), 'an hour ago', 'within_hour'],
  [q('cp_onset'), 'एक घंटे पहले', 'within_hour'],
  [q('cp_onset'), 'earlier today', 'today'],
  [q('cp_onset'), 'this morning', 'today'],
  [q('cp_onset'), 'a few days ago', 'days'],
  [q('cp_onset'), 'kai din', 'days'],
  // tier 1 — quality, including an ASR near-miss
  [q('cp_quality'), 'pressure or heaviness', 'pressure'],
  [q('cp_quality'), 'heavy', 'pressure'],
  [q('cp_quality'), 'someone sitting on my chest', 'pressure'],
  [q('cp_quality'), 'sharp stabbing', 'sharp'],
  [q('cp_quality'), 'burning', 'burning'],
  [q('cp_quality'), 'jalan', 'burning'],
  [q('cp_quality'), 'a tight band across the chest', 'tight_band'],
  [q('cp_quality'), 'squeezing', 'tight_band'],
  // tier 1 — radiation
  [q('cp_radiation'), 'left arm', 'left_arm'],
  [q('cp_radiation'), 'jaw or neck', 'jaw_neck'],
  [q('cp_radiation'), 'back', 'back'],
  [q('cp_radiation'), 'stays in the chest', 'stays_chest'],
];

const REDFLAG_CASES: [string, string[]][] = [
  ['I have chest pain since this morning', []],
  ['chest pain and I am sweating a lot', ['chest_pain_with_sweating_radiation_breathlessness']],
  ['seene mein dard hai aur paseena aa raha hai', []], // romanised — expected gap, see notes
  ['सीने में दर्द और पसीना', ['chest_pain_with_sweating_radiation_breathlessness']],
  ['he is not responding to me', ['altered_consciousness']],
  ['snake bit me', ['poisoning_overdose_or_snakebite']],
  ['the baby is not feeding and floppy', ['infant_not_feeding_floppy_inconsolable']],
  ['bleeding heavily from the leg', ['uncontrolled_bleeding_or_penetrating_injury']],
  ['I have a mild headache', []],
  ['no chest pain at all', []],
];

const CLASSIFY_CASES: [string, string | null][] = [
  ['I have chest pain since this morning', 'chest_pain'],
  ['पेट में दर्द हो रहा है', 'abdominal_pain'],
  ['saans lene mein takleef', 'breathing'],
  ['सांस लेने में तकलीफ है', 'breathing'],
  ['bukhar hai teen din se', 'fever'],
  ['I fell down the stairs', 'trauma'],
  ['ulti ho rahi hai', 'gi'],
  ['my head hurts a bit', null],
];

/**
 * Adversarial fixtures for the validators. These are the guarantee that a
 * hallucinated or hostile model response cannot reach the tree — the
 * prompt asks for a closed vocabulary, validate.ts is what enforces it.
 */
const VALIDATOR_CASES: { name: string; got: unknown; expected: unknown }[] = (() => {
  const allowed = ['left_arm', 'jaw_neck', 'back', 'stays_chest'];
  return [
    // branch
    { name: 'branch: valid', got: validateBranch({ branch: 'chest_pain' }), expected: 'chest_pain' },
    { name: 'branch: invented', got: validateBranch({ branch: 'cardiac_arrest' }), expected: 'other' },
    { name: 'branch: missing', got: validateBranch({}), expected: 'other' },
    { name: 'branch: null body', got: validateBranch(null), expected: 'other' },
    { name: 'branch: array', got: validateBranch(['chest_pain']), expected: 'other' },
    { name: 'branch: wrong type', got: validateBranch({ branch: 3 }), expected: 'other' },
    // match
    { name: 'match: valid', got: validateMatch({ matched: 'left_arm' }, allowed), expected: 'left_arm' },
    { name: 'match: not offered', got: validateMatch({ matched: 'right_arm' }, allowed), expected: null },
    { name: 'match: explicit null', got: validateMatch({ matched: null }, allowed), expected: null },
    { name: 'match: prose', got: validateMatch({ matched: 'the left arm, probably' }, allowed), expected: null },
    { name: 'match: empty allowed', got: validateMatch({ matched: 'left_arm' }, []), expected: null },
    // observe — the safety-critical one
    {
      name: 'observe: valid subset',
      got: validateObserve({ observations: ['altered_consciousness'], fields: {} }),
      expected: { redFlags: ['altered_consciousness'], fields: {} },
    },
    {
      name: 'observe: invented code dropped',
      got: validateObserve({ observations: ['altered_consciousness', 'patient_is_dying'], fields: {} }),
      expected: { redFlags: ['altered_consciousness'], fields: {} },
    },
    {
      name: 'observe: acuity key ignored',
      got: validateObserve({ observations: [], band: 'RED', acuity: 1, priority: 'urgent', fields: {} }),
      expected: { redFlags: [], fields: {} },
    },
    {
      name: 'observe: unknown field dropped',
      got: validateObserve({ observations: [], fields: { diagnosis: 'MI', allergies: 'penicillin' } }),
      expected: { redFlags: [], fields: { allergies: 'penicillin' } },
    },
    {
      name: 'observe: empty field value not treated as an answer',
      got: validateObserve({ observations: [], fields: { allergies: '   ' } }),
      expected: { redFlags: [], fields: {} },
    },
    {
      name: 'observe: duplicate codes collapsed',
      got: validateObserve({ observations: ['poisoning_overdose_or_snakebite', 'poisoning_overdose_or_snakebite'], fields: {} }),
      expected: { redFlags: ['poisoning_overdose_or_snakebite'], fields: {} },
    },
    { name: 'observe: garbage', got: validateObserve('not json'), expected: { redFlags: [], fields: {} } },
    { name: 'observe: null', got: validateObserve(null), expected: { redFlags: [], fields: {} } },
  ];
})();

/**
 * Regression fixtures for `observeOn`. Five questions in the tree are
 * phrased positively — "can you speak in full sentences?", "is the child
 * feeding normally?" — so NO is the alarming answer. Firing on the wrong
 * one fails in the worst possible direction: a patient answering
 * truthfully would SUPPRESS the alert instead of raising it. These pin
 * every inverted question in both directions.
 */
const INVERSION_CASES: { q: string; answer: 'yes' | 'no'; expectFlag: boolean }[] = [
  // inverted (observeOn: 'no')
  { q: 'br_speak_sentences', answer: 'no', expectFlag: true },
  { q: 'br_speak_sentences', answer: 'yes', expectFlag: false },
  { q: 'bl_stopping', answer: 'no', expectFlag: true },
  { q: 'bl_stopping', answer: 'yes', expectFlag: false },
  { q: 'pg_feeding', answer: 'no', expectFlag: true },
  { q: 'pg_feeding', answer: 'yes', expectFlag: false },
  { q: 'pg_alert', answer: 'no', expectFlag: true },
  { q: 'pg_alert', answer: 'yes', expectFlag: false },
  { q: 'pg_consolable', answer: 'no', expectFlag: true },
  { q: 'pg_consolable', answer: 'yes', expectFlag: false },
  { q: 'nr_alert', answer: 'no', expectFlag: true },
  { q: 'nr_alert', answer: 'yes', expectFlag: false },
  { q: 'fv_alert', answer: 'no', expectFlag: true },
  { q: 'other_alert', answer: 'no', expectFlag: true },
  { q: 'other_breathing', answer: 'no', expectFlag: true },
  // normal (observeOn defaults to 'yes')
  { q: 'cp_sweating', answer: 'yes', expectFlag: true },
  { q: 'cp_sweating', answer: 'no', expectFlag: false },
  { q: 'tr_bleeding_uncontrolled', answer: 'yes', expectFlag: true },
  { q: 'tr_bleeding_uncontrolled', answer: 'no', expectFlag: false },
  { q: 'ob_contractions', answer: 'yes', expectFlag: true },
  { q: 'po_confirm', answer: 'yes', expectFlag: true },
  { q: 'al_swelling_face', answer: 'yes', expectFlag: true },
  { q: 'pg_breathing_effort', answer: 'yes', expectFlag: true },
];

/** Every branch must be able to raise at least one of the eight codes —
 *  a branch a patient can walk end to end without any path to a nurse is
 *  a hole in the safety net. */
const ALL_BRANCH_IDS = [
  'chest_pain', 'breathing', 'abdominal_pain', 'neuro', 'fever', 'trauma',
  'bleeding', 'gi', 'obstetric', 'poisoning', 'burn', 'allergy',
  'urinary', 'mental_behavioural', 'paeds_general', 'other',
] as const;

function runInversion(questionId: string, answer: 'yes' | 'no') {
  // Drive the real reducer: seed a session sitting on this question.
  const base: SessionState = {
    ...INITIAL_SESSION,
    stratum: 'adult',
    chiefComplaint: 'seeded',
    branch: 'other',
    plan: [questionId, 'pain_score'],
    cursor: 0,
    answers: { __stratum: 'adult' },
  };
  const next = submitAnswer(base, answer);
  return next.redFlags.length > 0 || next.needsImmediateNurse;
}

// ---------------------------------------------------------------------------
// Risk engine — the band an intake patient enters the board with
// ---------------------------------------------------------------------------

type RiskCase = {
  name: string;
  input: Parameters<typeof computeRisk>[0];
  expect: 'RED' | 'YELLOW' | 'GREEN';
};

const RISK_CASES: RiskCase[] = [
  // Red flags are terminal regardless of everything else.
  {
    name: 'red flag alone → RED',
    input: { ageStratum: 'adult', redFlagCodes: ['chest_pain_with_sweating_radiation_breathlessness'] },
    expect: 'RED',
  },
  {
    name: 'red flag survives entirely normal vitals (escalate-only)',
    input: {
      ageStratum: 'adult',
      redFlagCodes: ['altered_consciousness'],
      measurements: [
        { code: 'HR', value: 72, unit: 'bpm', takenAt: new Date().toISOString(), source: 'station', validity: 'fresh' },
        { code: 'SPO2', value: 99, unit: '%', takenAt: new Date().toISOString(), source: 'station', validity: 'fresh' },
      ],
    },
    expect: 'RED',
  },
  // A critical vital far outside range is RED on its own.
  {
    name: 'SpO2 88 in an adult → RED',
    input: {
      ageStratum: 'adult',
      measurements: [{ code: 'SPO2', value: 88, unit: '%', takenAt: new Date().toISOString(), source: 'station', validity: 'fresh' }],
    },
    expect: 'RED',
  },
  // The stratum case: 130 bpm is normal for a toddler, tachycardic for an adult.
  {
    name: 'HR 130 in a child → GREEN (normal for stratum)',
    input: {
      ageStratum: 'child',
      measurements: [{ code: 'HR', value: 130, unit: 'bpm', takenAt: new Date().toISOString(), source: 'station', validity: 'fresh' }],
    },
    expect: 'GREEN',
  },
  // The YELLOW/RED line for a vital: outside normal is YELLOW, past the
  // explicit critical bound is RED. 130 is tachycardic, 165 is a resus number.
  {
    name: 'HR 130 in an adult → YELLOW (abnormal, not critical)',
    input: {
      ageStratum: 'adult',
      measurements: [{ code: 'HR', value: 130, unit: 'bpm', takenAt: new Date().toISOString(), source: 'station', validity: 'fresh' }],
    },
    expect: 'YELLOW',
  },
  {
    name: 'HR 165 in an adult → RED (past critical bound)',
    input: {
      ageStratum: 'adult',
      measurements: [{ code: 'HR', value: 165, unit: 'bpm', takenAt: new Date().toISOString(), source: 'station', validity: 'fresh' }],
    },
    expect: 'RED',
  },
  {
    name: 'HR 165 in an infant → GREEN (normal for stratum)',
    input: {
      ageStratum: 'infant',
      measurements: [{ code: 'HR', value: 165, unit: 'bpm', takenAt: new Date().toISOString(), source: 'station', validity: 'fresh' }],
    },
    // The infant YELLOW floor still applies — this asserts the HR itself
    // contributed nothing, not that the patient is GREEN.
    expect: 'YELLOW',
  },
  {
    name: 'SpO2 94 in an adult → YELLOW (low, above the critical 92)',
    input: {
      ageStratum: 'adult',
      measurements: [{ code: 'SPO2', value: 94, unit: '%', takenAt: new Date().toISOString(), source: 'station', validity: 'fresh' }],
    },
    expect: 'YELLOW',
  },
  {
    name: 'severe self-reported pain → YELLOW',
    input: { ageStratum: 'adult', painScore: 9 },
    expect: 'YELLOW',
  },
  {
    name: 'low pain does not de-escalate below GREEN, and never below a floor',
    input: { ageStratum: 'adult', painScore: 1, humanAssignedBand: 'YELLOW' },
    expect: 'YELLOW',
  },
  {
    name: 'infant floors at YELLOW even with nothing reported',
    input: { ageStratum: 'infant' },
    expect: 'YELLOW',
  },
  {
    name: 'nothing reported, adult → GREEN',
    input: { ageStratum: 'adult' },
    expect: 'GREEN',
  },
  // An expired reading is MISSING, not a reassuring number (Invariant 4).
  {
    name: 'expired deranged reading does not band the patient',
    input: {
      ageStratum: 'adult',
      measurements: [{ code: 'SPO2', value: 80, unit: '%', takenAt: new Date(0).toISOString(), source: 'station', validity: 'expired' }],
    },
    expect: 'GREEN',
  },
  // A nurse-invented field must never move a band.
  {
    name: 'unknown custom vital is recorded but never scored',
    input: {
      ageStratum: 'adult',
      measurements: [{ code: 'peak_flow' as never, value: 1, unit: '', takenAt: new Date().toISOString(), source: 'nurse', validity: 'fresh' }],
    },
    expect: 'GREEN',
  },
];

// ---------------------------------------------------------------------------
// Vital code normalisation — the bug that silently unbanded hand-entered
// readings, because the dialog posted 'bp_sys' and every lookup wanted 'SBP'.
// ---------------------------------------------------------------------------

const VITAL_CODE_CASES: [string, string | null][] = [
  ['hr', 'HR'], ['HR', 'HR'], ['Heart Rate', 'HR'], ['pulse', 'HR'],
  ['bp_sys', 'SBP'], ['systolic', 'SBP'], ['SBP', 'SBP'],
  ['bp_dia', 'DBP'], ['temp_c', 'TEMP'], ['Temperature', 'TEMP'],
  ['spo2', 'SPO2'], ['O2 Sat', 'SPO2'], ['pain_score', 'PAIN'],
  ['blood sugar', 'RBS'], ['glucose', 'RBS'], ['gcs', 'GCS'],
  ['peak flow', null], ['urine output', null], ['', null],
];

// ---------------------------------------------------------------------------
// Spoken numbers — age by voice, English and Hindi
// ---------------------------------------------------------------------------

/** [what was said, what it should resolve to] against range [0,120]. */
const NUMBER_CASES: [string, string | null][] = [
  // Digits, either script, bare or inside a sentence.
  ['72', '72'],
  ['७२', '72'],
  ['I am 72', '72'],
  ['72 years old', '72'],
  ['मैं ७२ साल का हूं', '72'],
  ['5', '5'],
  ['0', '0'],

  // English words, including the compound forms that used to fail.
  ['seventy two', '72'],
  ['seventy-two', '72'],
  ['thirty five', '35'],
  ['forty', '40'],
  ['fourty five', '45'],
  ['nineteen', '19'],
  ['eight', '8'],
  ['a hundred', '100'],
  ["I'm seventy two years old", '72'],

  // Hindi — irregular past twenty, which is exactly what broke.
  ['बहत्तर', '72'],
  ['पचास', '50'],
  ['इक्कीस', '21'],            // must not read as the एक inside it
  // Romanised Hindi that is NOT an English word stays available in English
  // mode — "I am bahattar" is an ordinary code-mixed sentence here.
  ['bahattar', '72'],
  ['pachas', '50'],
  ['ikkis', '21'],
  ['saat', '7'],
  ['I am bahattar years old', '72'],
  ['अस्सी', '80'],
  ['नब्बे', '90'],
  ['सैंतालीस', '47'],
  ['बहत्तर साल', '72'],
  ['मेरी उम्र चालीस है', '40'],

  // Out of range is a mis-hear, not an answer.
  ['300', null],
  ['999', null],
  ['minus five', null],

  // Nothing numeric at all. "do" is romanised Hindi for 2 and "no" for 9 —
  // neither may fire in English mode, or an ordinary sentence becomes an age.
  ['I do not know', null],
  ['no idea, sorry', null],
  ['do you need my age', null],
  ['', null],
];

/** Hindi mode: romanised forms become available, Devanagari still works. */
const NUMBER_CASES_HI: [string, string | null][] = [
  ['bahattar', '72'],
  ['pachas', '50'],
  ['ikkis', '21'],
  ['sattar saal', '70'],
  ['बहत्तर', '72'],
  ['७२', '72'],
  ['do', '2'],
  ['mujhe nahi pata', null],
];

/** A scale question must stay narrow — 72 is not a pain score. */
const SCALE_CASES: [string, string | null][] = [
  ['7', '7'],
  ['seven', '7'],
  ['सात', '7'],
  ['10', '10'],
  ['zero', '0'],
  ['72', null],
  ['no idea', null],
];

// ---------------------------------------------------------------------------
// Going back — a wrong voice answer has to be correctable
// ---------------------------------------------------------------------------

function seedConversation(): SessionState {
  let s: SessionState = {
    ...INITIAL_SESSION,
    step: 'conversation',
    stratum: 'adult',
    ageYears: 40,
  };
  s = { ...s, chiefComplaint: 'chest pain', branch: 'chest_pain', cursor: 0 };
  const plan = getBranch('chest_pain').questions.slice(0, 3).map((x) => x.id);
  return { ...s, plan, answers: { chief_complaint: 'chest pain' } };
}

const BACK_CASES: { name: string; run: () => boolean }[] = [
  {
    name: 'mid-plan: steps back one and forgets that answer',
    run: () => {
      const seed = seedConversation();
      const answered = { ...seed, cursor: 2, answers: { ...seed.answers, [seed.plan[1]]: 'pressure' } };
      const back = goBackOne(answered);
      return back.cursor === 1 && !(seed.plan[1] in back.answers);
    },
  },
  {
    name: 'first branch question: falls back to the opening question',
    run: () => {
      const seed = seedConversation();
      const back = goBackOne(seed);
      return back.chiefComplaint === '' && back.plan.length === 0 && !('chief_complaint' in back.answers);
    },
  },
  {
    name: 'from pain: lands on the last planned question, not a blank screen',
    run: () => {
      const seed = seedConversation();
      const atPain = { ...seed, step: 'pain' as const, cursor: seed.plan.length };
      const back = goBackOne(atPain);
      return back.step === 'conversation' && back.cursor === seed.plan.length - 1;
    },
  },
  {
    name: 'from readback: returns to pain and clears the score',
    run: () => {
      const seed = { ...seedConversation(), step: 'readback' as const, painScore: 7,
        answers: { pain_score: '7' } };
      const back = goBackOne(seed);
      return back.step === 'pain' && back.painScore === null && !('pain_score' in back.answers);
    },
  },
  {
    name: 'a fired red flag is NOT undone by going back',
    run: () => {
      const seed = seedConversation();
      const flagged = {
        ...seed, cursor: 2, needsImmediateNurse: true,
        redFlags: [{ code: 'altered_consciousness', description: { en: 'x', hi: 'x' } }],
      };
      const back = goBackOne(flagged);
      return back.needsImmediateNurse === true && back.redFlags.length === 1;
    },
  },
  {
    name: 'canGoBack is false on the nurse-call screen',
    run: () => !canGoBack({ ...seedConversation(), cursor: 2, needsImmediateNurse: true }),
  },
  {
    name: 'canGoBack is true once a complaint has been given',
    run: () => canGoBack(seedConversation()),
  },
];

// ---------------------------------------------------------------------------
// Answer-mode classification and the spoken prompt it drives
// ---------------------------------------------------------------------------

const MODE_CASES: [Question['kind'], string][] = [
  ['number', 'numeric'],
  ['scale_0_10', 'numeric'],
  ['yes_no', 'binary'],
  ['choice', 'choice'],
  ['free_text', 'open'],
];

const PROMPT_CASES: { name: string; got: string; must: string }[] = (() => {
  const numQ: Question = { id: 'n', kind: 'number', prompt: { en: 'How old are you?', hi: 'x' }, numberRange: [0, 120] };
  const scaleQ: Question = { id: 's', kind: 'scale_0_10', prompt: { en: 'How bad?', hi: 'x' } };
  const ynQ: Question = { id: 'y', kind: 'yes_no', prompt: { en: 'Sweating?', hi: 'x' } };
  const freeQ: Question = { id: 'f', kind: 'free_text', prompt: { en: 'Tell me.', hi: 'x' } };
  return [
    { name: 'number asks for a number and states its range',
      got: buildSpokenPrompt(numQ, 'en'), must: 'Say a number between 0 and 120.' },
    { name: 'scale states the 0-10 range',
      got: buildSpokenPrompt(scaleQ, 'en'), must: 'Say a number between 0 and 10.' },
    { name: 'binary offers yes or no',
      got: buildSpokenPrompt(ynQ, 'en'), must: 'Yes, or no?' },
    { name: 'free text gets no suffix',
      got: buildSpokenPrompt(freeQ, 'en'), must: 'Tell me.' },
    { name: 'numeric suffix is translated',
      got: buildSpokenPrompt(scaleQ, 'hi'), must: 'के बीच कोई संख्या बोलें' },
  ];
})();

export async function GET() {
  if (process.env.NODE_ENV === 'production') {
    return new NextResponse('Not found', { status: 404 });
  }

  const back = BACK_CASES.map((c) => {
    let pass = false;
    try { pass = c.run(); } catch { pass = false; }
    return { name: c.name, pass };
  });

  const modes = MODE_CASES.map(([kind, expected]) => {
    const got = answerModeFor(kind);
    return { kind, expected, got, pass: got === expected };
  });

  const prompts = PROMPT_CASES.map((c) => ({
    name: c.name, got: c.got, pass: c.got.includes(c.must),
  }));

  const numbers = NUMBER_CASES.map(([said, expected]) => {
    const got = matchNumber(said, [0, 120]).value;
    return { said, expected, got, pass: got === expected };
  });

  const numbersHi = NUMBER_CASES_HI.map(([said, expected]) => {
    const got = matchNumber(said, [0, 120], 'hi').value;
    return { said, expected, got, pass: got === expected };
  });

  const scales = SCALE_CASES.map(([said, expected]) => {
    const r = matchScale(said);
    const got = r.confidence >= ACCEPT_THRESHOLD ? r.value : null;
    return { said, expected, got, pass: got === expected };
  });

  const risk = RISK_CASES.map((c) => {
    const got = computeRisk(c.input).band;
    return { name: c.name, expected: c.expect, got, pass: got === c.expect };
  });

  const vitalCodes = VITAL_CODE_CASES.map(([raw, expected]) => {
    const got = normaliseVitalCode(raw);
    return { raw, expected, got, pass: got === expected };
  });

  const inversions = INVERSION_CASES.map((c) => {
    const fired = runInversion(c.q, c.answer);
    return { ...c, fired, pass: fired === c.expectFlag };
  });

  const coverage = ALL_BRANCH_IDS.map((id) => {
    const qs = getBranch(id).questions;
    const hasFlagPath = qs.some((q) => (q.observes?.length ?? 0) > 0 || !!q.urgentOn);
    return { branch: id, questions: qs.length, hasFlagPath, pass: hasFlagPath && qs.length >= 3 };
  });

  const validators = VALIDATOR_CASES.map((c) => ({
    ...c,
    pass: JSON.stringify(c.got) === JSON.stringify(c.expected),
  }));

  const match = MATCH_CASES.map(([question, said, expected]) => {
    const r = matchLocal(said, question);
    const got = r.confidence >= ACCEPT_THRESHOLD ? r.value : null;
    return { said, expected, got, confidence: Number(r.confidence.toFixed(2)), pass: got === expected };
  });

  const redflags = REDFLAG_CASES.map(([said, expected]) => {
    const got = detectRedFlagsLocal(said).map((f) => f.observation).sort();
    return { said, expected: [...expected].sort(), got, pass: JSON.stringify(got) === JSON.stringify([...expected].sort()) };
  });

  const classify = CLASSIFY_CASES.map(([said, expected]) => {
    const got = localClassify(said);
    return { said, expected, got, pass: got === expected };
  });

  const summarise = (rows: { pass: boolean }[]) => ({
    total: rows.length,
    passed: rows.filter((r) => r.pass).length,
    rate: Number((rows.filter((r) => r.pass).length / rows.length).toFixed(3)),
  });

  return NextResponse.json({
    match: { ...summarise(match), failures: match.filter((r) => !r.pass) },
    redflags: { ...summarise(redflags), failures: redflags.filter((r) => !r.pass) },
    classify: { ...summarise(classify), failures: classify.filter((r) => !r.pass) },
    validators: { ...summarise(validators), failures: validators.filter((r) => !r.pass) },
    inversions: { ...summarise(inversions), failures: inversions.filter((r) => !r.pass) },
    coverage: { ...summarise(coverage), failures: coverage.filter((r) => !r.pass) },
    risk: { ...summarise(risk), failures: risk.filter((r) => !r.pass) },
    vitalCodes: { ...summarise(vitalCodes), failures: vitalCodes.filter((r) => !r.pass) },
    numbers: { ...summarise(numbers), failures: numbers.filter((r) => !r.pass) },
    numbersHi: { ...summarise(numbersHi), failures: numbersHi.filter((r) => !r.pass) },
    back: { ...summarise(back), failures: back.filter((r) => !r.pass) },
    modes: { ...summarise(modes), failures: modes.filter((r) => !r.pass) },
    prompts: { ...summarise(prompts), failures: prompts.filter((r) => !r.pass) },
    scales: { ...summarise(scales), failures: scales.filter((r) => !r.pass) },
    groq: { configured: groqConfigured(), offlineSwitch: intakeOffline() },
  });
}
