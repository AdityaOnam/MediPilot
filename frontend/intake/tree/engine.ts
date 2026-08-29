import type { BranchId, OpeningStepId, Question, SessionState } from './types';
import { buildPlan, getQuestion, resolveStratum } from './index';
import { localClassify } from './localClassify';
import { detectRedFlagsLocal } from '../redflags/detect';
import { redFlagByObservation } from '../redflags/observations';

/**
 * Pure state transitions. No React, no network, no timers — everything
 * here is a (state) -> state function so it can be unit-tested without a
 * mic. Network-dependent branch classification and red-flag confirmation
 * (the Groq tiers) are layered on top in session.ts, which calls these
 * reducers with whatever the API returned.
 */

export function setLang(s: SessionState, lang: 'en' | 'hi'): SessionState {
  return { ...s, lang };
}

export function goTo(s: SessionState, step: OpeningStepId): SessionState {
  return { ...s, step };
}

/**
 * Flow order: welcome -> consent -> companion -> human-offer -> basics ->
 * conversation. Consent moved up to screen 2 (immediately after language)
 * so voice can start as early as it legitimately can — the mic must never
 * listen before "let MediPilot listen" has been granted, so nothing
 * before this screen can be voice-driven, and everything from Companion
 * onward now can be.
 */
export function setConsent(s: SessionState, consent: { listen: boolean; records: boolean }): SessionState {
  if (!consent.listen) return { ...s, consent, step: 'human-lane' };
  return { ...s, consent, step: 'companion' };
}

export function setCompanion(s: SessionState, assisted: boolean): SessionState {
  return { ...s, assisted, step: 'human-offer' };
}

export function setHumanOffer(s: SessionState, wantsHuman: boolean): SessionState {
  if (wantsHuman) return { ...s, wantsHuman, step: 'human-lane' };
  return { ...s, wantsHuman, step: 'basics' };
}

export function setBasics(s: SessionState, ageYears: number | null, sex: SessionState['sex']): SessionState {
  const stratum = resolveStratum(ageYears);
  const answers = { ...s.answers, __stratum: stratum, __sex: sex ?? undefined } as SessionState['answers'];
  return { ...s, ageYears, sex, stratum, answers, step: 'conversation' };
}

/** Q0 answered. Picks a branch (offline first; session.ts may later
 *  overwrite `branch` with a Groq classification and rebuild the plan),
 *  sets the plan, and enters the branch/tail walk. */
export function setChiefComplaintAndBranch(s: SessionState, text: string, branchOverride?: BranchId | null): SessionState {
  const isPaediatric = s.stratum === 'neonate' || s.stratum === 'infant' || s.stratum === 'child';
  const local = branchOverride ?? localClassify(text);
  // A non-specific complaint in a paediatric patient routes to the
  // paeds_general branch regardless of what the lexicon matched — see
  // paedsGeneral.ts's header comment.
  const branch: BranchId = isPaediatric && !local ? 'paeds_general' : (local ?? 'other');

  const answers = { ...s.answers, chief_complaint: text };
  const plan = buildPlan(branch, answers);
  const redFlags = mergeRedFlags(s.redFlags, detectRedFlagsLocal(text));

  const next: SessionState = {
    ...s,
    chiefComplaint: text,
    branch,
    plan,
    cursor: 0,
    answers,
    redFlags,
  };
  return redFlags.length > 0 ? triggerNurseCall(next) : next;
}

export function currentQuestion(s: SessionState): Question | null {
  if (s.cursor >= s.plan.length) return null;
  return getQuestion(s.plan[s.cursor]) ?? null;
}

/** Records one answer, scans it for red flags, drops any later plan items
 *  the answer already covered (skip-what's-known — full field extraction
 *  lands in B6 via /api/intake/observe; this covers the fields the tree
 *  itself can already infer from the current question). */
export function submitAnswer(s: SessionState, text: string): SessionState {
  const q = currentQuestion(s);
  if (!q) return s;

  const answers = { ...s.answers, [q.id]: text };
  let redFlags = mergeRedFlags(s.redFlags, detectRedFlagsLocal(text));

  // A yes/no answer to a question tagged with `observes` carries the flag
  // directly — text-scanning alone would miss it, since the literal answer
  // is the word "yes" or "no" and never contains "sweating" or
  // "breathless". `observeOn` says WHICH answer is the alarming one:
  // "are you sweating?" fires on yes, "can you speak in full sentences?"
  // fires on no. Choice questions are deliberately not covered here — not
  // every option on cp_radiation is alarming ("stays in the chest" is
  // reassuring), so per-option meaning is left to the Groq observer.
  const alarming = q.observeOn ?? 'yes';
  if (q.kind === 'yes_no' && text === alarming && q.observes?.length) {
    redFlags = mergeObservationCodes(redFlags, q.observes);
  }

  let next: SessionState = { ...s, answers, redFlags };

  // A nurse-now case that is not one of the eight codes (self-harm risk).
  // Routes the patient to a person WITHOUT fabricating a red flag.
  if (q.kind === 'yes_no' && q.urgentOn && text === q.urgentOn) {
    next = triggerNurseCall({ ...next, urgentWithoutCode: true });
    return next;
  }

  if (redFlags.length > 0) return triggerNurseCall(next);

  next = advance(next);
  return next;
}

function advance(s: SessionState): SessionState {
  const nextCursor = s.cursor + 1;
  if (nextCursor >= s.plan.length) {
    return { ...s, cursor: nextCursor, step: 'pain' };
  }
  return { ...s, cursor: nextCursor };
}

/**
 * Steps back one answer so a wrong one can be corrected.
 *
 * Voice input gets things wrong, and until this existed there was no way
 * back: Conversation only offered a Back button on the opening question,
 * so a mis-heard answer to any branch question was final. Readback's "Fix
 * something" jumped to the conversation step with the cursor still parked
 * past the end of the plan, which rendered a blank screen.
 *
 * What it does NOT undo, deliberately:
 *
 *  - A fired red flag. Once the tree has called a nurse, a correction at
 *    the kiosk must not un-call them. That decision belongs to the person
 *    who arrives, and every other downward move in this system is locked
 *    the same way.
 *  - Plan items already pruned by skipKnownFields. They were dropped
 *    because the patient volunteered the answer elsewhere, which going
 *    back one question does not retract.
 */
export function goBackOne(s: SessionState): SessionState {
  // From the readback, step back onto the pain question.
  if (s.step === 'readback') {
    const answers = { ...s.answers };
    delete answers.pain_score;
    return { ...s, step: 'pain', painScore: null, answers, readbackConfirmed: false };
  }

  // From the pain screen, back onto the last question of the plan.
  if (s.step === 'pain') {
    if (s.plan.length === 0) return { ...s, step: 'conversation' };
    const lastId = s.plan[s.plan.length - 1];
    const answers = { ...s.answers };
    delete answers[lastId];
    return { ...s, step: 'conversation', cursor: s.plan.length - 1, answers };
  }

  if (s.step !== 'conversation') return s;

  // Mid-plan: drop the previous answer and re-ask it.
  if (s.cursor > 0) {
    const prevId = s.plan[s.cursor - 1];
    const answers = { ...s.answers };
    delete answers[prevId];
    return { ...s, cursor: s.cursor - 1, answers };
  }

  // At the first branch question: the only thing behind it is Q0, so
  // clear the complaint and the plan it produced and ask again.
  const answers = { ...s.answers };
  delete answers.chief_complaint;
  return { ...s, chiefComplaint: '', branch: null, plan: [], cursor: 0, answers };
}

/** True when goBackOne has somewhere to go. The nurse-call screen is a
 *  terminal state and never offers it. */
export function canGoBack(s: SessionState): boolean {
  if (s.needsImmediateNurse) return false;
  if (s.step === 'readback' || s.step === 'pain') return true;
  if (s.step !== 'conversation') return false;
  return s.cursor > 0 || !!s.chiefComplaint;
}

/** Drops question ids from the remaining plan whose answer the patient
 *  already volunteered — called once observe() (local or remote) returns
 *  a field map. Never removes the question currently on screen. */
export function skipKnownFields(s: SessionState, known: Record<string, string>): SessionState {
  const answers = { ...s.answers, ...known };
  const plan = s.plan.filter((id, idx) => idx <= s.cursor || !(id in known));
  return { ...s, answers, plan };
}

/**
 * Replaces the branch chosen by the offline classifier once the Groq pass
 * comes back with something better. Only applies before the patient has
 * answered anything in the branch — re-planning under someone mid-way
 * through would yank a question off the screen they were reading.
 */
export function refineBranch(s: SessionState, branchId: BranchId): SessionState {
  if (s.cursor !== 0 || s.branch === branchId) return s;
  return { ...s, branch: branchId, plan: buildPlan(branchId, s.answers), cursor: 0 };
}

/** Applies a tier-B observe result: red-flag codes (which can trigger the
 *  nurse call) and volunteered fields (which prune the remaining plan). */
export function applyObserved(
  s: SessionState,
  codes: string[],
  fields: Record<string, string>,
): SessionState {
  let next = Object.keys(fields).length ? skipKnownFields(s, fields) : s;
  for (const code of codes) next = addRedFlagByCode(next, code);
  return next;
}

export function setPainScore(s: SessionState, score: number): SessionState {
  return { ...s, painScore: score, answers: { ...s.answers, pain_score: String(score) }, step: 'readback' };
}

export function confirmReadback(s: SessionState): SessionState {
  return { ...s, readbackConfirmed: true };
}

export function issueToken(
  s: SessionState,
  token: string,
  counter: string | null,
  requiredVitals: string[] = [],
): SessionState {
  return { ...s, token, counter, requiredVitals, submitting: false, step: 'token' };
}

function mergeRedFlags(existing: SessionState['redFlags'], found: ReturnType<typeof detectRedFlagsLocal>): SessionState['redFlags'] {
  if (found.length === 0) return existing;
  const seen = new Set(existing.map((f) => f.code));
  const additions = found
    .filter((f) => !seen.has(f.observation))
    .map((f) => ({ code: f.observation, description: f.description }));
  return additions.length ? [...existing, ...additions] : existing;
}

function mergeObservationCodes(existing: SessionState['redFlags'], codes: string[]): SessionState['redFlags'] {
  const seen = new Set(existing.map((f) => f.code));
  const additions = codes
    .map((c) => redFlagByObservation(c))
    .filter((def): def is NonNullable<typeof def> => !!def && !seen.has(def.observation))
    .map((def) => ({ code: def.observation, description: def.description }));
  return additions.length ? [...existing, ...additions] : existing;
}

/** Every clinical question stops immediately (Part 4, step 1). The patient
 *  is not walked through the rest of a form once a flag has fired. */
function triggerNurseCall(s: SessionState): SessionState {
  if (s.needsImmediateNurse) return s; // already triggered
  return { ...s, needsImmediateNurse: true, nurseCalledAt: new Date().toISOString() };
}

/**
 * Records that the patient spoke in short fragments with frequent pauses.
 *
 * Deliberately NOT a red flag and NOT an escalation — it is noisy (a
 * nervous patient stammers) and it is an ASR-derived signal, so it goes
 * on the record for the nurse to weigh and nothing more. It rides along
 * in symptomAnswers so it reaches the card without pretending to be one
 * of the eight codes.
 */
export function noteSpeechEffort(s: SessionState): SessionState {
  if (s.answers.observed_speech_effort) return s;
  return {
    ...s,
    answers: {
      ...s.answers,
      observed_speech_effort: 'short phrases with frequent pauses (observed during intake)',
    },
  };
}

/** Adds a red flag code by string, for callers holding only the code
 *  (e.g. the Groq observer's response) rather than a full RedFlagDef. */
export function addRedFlagByCode(s: SessionState, code: string): SessionState {
  const def = redFlagByObservation(code);
  if (!def) return s;
  const seen = new Set(s.redFlags.map((f) => f.code));
  if (seen.has(code)) return s;
  const next: SessionState = { ...s, redFlags: [...s.redFlags, { code: def.observation, description: def.description }] };
  return triggerNurseCall(next);
}
