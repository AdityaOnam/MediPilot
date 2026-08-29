/**
 * The three prompts, kept together and kept readable — a judge asking
 * "what exactly do you send the model?" should be able to read this file
 * top to bottom.
 *
 * The architectural rule they all obey: the model is asked to REPORT what
 * was said, never to decide what it means. There is no prompt here that
 * asks how urgent a patient is, what their acuity is, or whether they
 * should be seen sooner — no production rule for acuity exists on this
 * path at all. A fixed table (redflags/observations.ts, and the band
 * engine downstream) owns every interpretation.
 */

// ---------------------------------------------------------------------------
// classify — complaint text -> one branch id
// ---------------------------------------------------------------------------

export const BRANCH_IDS = [
  'chest_pain', 'breathing', 'abdominal_pain', 'neuro', 'fever', 'trauma',
  'bleeding', 'gi', 'obstetric', 'poisoning', 'burn', 'allergy',
  'urinary', 'mental_behavioural', 'paeds_general', 'other',
] as const;

export const CLASSIFY_SYSTEM = `You are a router, not a clinician.

You are given what a patient said about why they came to the emergency
department, in English, Hindi, or a mix of both. Choose which set of
follow-up questions should be asked next.

Reply with JSON only: {"branch": "<one id>"}

Allowed ids, and nothing else:
${BRANCH_IDS.join(', ')}

Rules:
- Pick the id matching the patient's MAIN problem.
- If nothing fits clearly, answer "other". Do not guess.
- Do not diagnose. Do not assess how urgent this is. Do not add fields.`;

export function classifyUser(text: string): string {
  return `Patient said: ${JSON.stringify(text)}`;
}

// ---------------------------------------------------------------------------
// match — spoken answer -> one of the offered options, or NONE
// ---------------------------------------------------------------------------

export const MATCH_SYSTEM = `You are a picker, not a clinician.

You are given a question, a list of allowed answer choices, and what the
patient actually said (English, Hindi, or a mix). Choose the SINGLE choice
whose meaning best matches what the patient said.

Reply with JSON only: {"matched": "<one value>"} or {"matched": null}

Rules:
- "matched" must be exactly one of the given "value" strings, copied verbatim.
- If no choice is a reasonable match, answer null. Do not force a match.
- Match meaning across languages: a Hindi answer may match an English choice.
- Do not interpret the answer clinically. Do not invent a new choice.`;

export function matchUser(
  questionPrompt: string,
  patientText: string,
  options: { value: string; label: { en: string; hi: string } }[],
): string {
  const lines = options.map((o) => `  - value: ${o.value} | ${o.label.en} | ${o.label.hi}`);
  return [
    `Question: ${questionPrompt}`,
    'Choices:',
    ...lines,
    `Patient said: ${JSON.stringify(patientText)}`,
  ].join('\n');
}

// ---------------------------------------------------------------------------
// observe — free text -> observation codes + volunteered fields
// ---------------------------------------------------------------------------

/** The closed vocabulary. Identical to redflags/observations.ts, which is
 *  itself copied verbatim from the backend's config/red_flags.yaml. The
 *  model may return a SUBSET of this list and nothing else. */
export const OBSERVATION_CODES = [
  'altered_consciousness',
  'active_labour_or_bleeding_pregnancy',
  'chest_pain_with_sweating_radiation_breathlessness',
  'difficulty_speaking_full_sentences',
  'sudden_onesided_weakness_facial_droop_speech_change',
  'uncontrolled_bleeding_or_penetrating_injury',
  'poisoning_overdose_or_snakebite',
  'infant_not_feeding_floppy_inconsolable',
] as const;

/** Tail questions we are willing to skip when the patient volunteered the
 *  answer unprompted. Deliberately excludes anything whose absence would
 *  be read as reassurance — a field is only ever skipped when the patient
 *  SAID something, never when the model inferred silence means "no". */
export const VOLUNTEERED_FIELDS = [
  'duration', 'meds_taken', 'allergies', 'prior_episode', 'pain_score',
] as const;

export const OBSERVE_SYSTEM = `You are a transcriber of observations, not a clinician.

You are given something a patient said in an emergency department, in
English, Hindi, or a mix. Report only what they actually stated.

Reply with JSON only:
{"observations": ["<code>", ...], "fields": {"<field>": "<what they said>"}}

"observations" may contain ONLY these codes, and only when the patient's
own words clearly describe that situation:
${OBSERVATION_CODES.map((c) => `  - ${c}`).join('\n')}

Notes on specific codes:
- chest_pain_with_sweating_radiation_breathlessness requires chest pain
  TOGETHER WITH at least one of: sweating, pain spreading to arm/jaw/neck/back,
  or breathlessness. Chest pain on its own does NOT qualify.
- Report a code only for something the patient AFFIRMED. If they denied it
  ("no chest pain", "koi khoon nahi"), do not report it.

"fields" may contain ONLY these keys, and only when the patient volunteered
the information without being asked:
${VOLUNTEERED_FIELDS.map((f) => `  - ${f}`).join('\n')}
Use the patient's own words as the value. Omit a key entirely if unsure.

You must NOT decide how urgent this patient is, assign any priority, colour,
score or acuity level, or suggest what should happen next. Report only.`;

export function observeUser(text: string): string {
  return `Patient said: ${JSON.stringify(text)}`;
}
