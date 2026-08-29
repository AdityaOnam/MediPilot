import type { Branch, BranchId, Question, SessionAnswers } from './types';
import { CHEST_PAIN_BRANCH } from './branches/chestPain';
import { BREATHING_BRANCH } from './branches/breathing';
import { ABDOMINAL_BRANCH } from './branches/abdominal';
import { NEURO_BRANCH } from './branches/neuro';
import { FEVER_BRANCH } from './branches/fever';
import { TRAUMA_BRANCH } from './branches/trauma';
import { BLEEDING_BRANCH } from './branches/bleeding';
import { GI_BRANCH } from './branches/gi';
import { OBSTETRIC_BRANCH } from './branches/obstetric';
import { POISONING_BRANCH } from './branches/poisoning';
import { BURN_BRANCH } from './branches/burn';
import { ALLERGY_BRANCH } from './branches/allergy';
import { URINARY_BRANCH } from './branches/urinary';
import { MENTAL_BRANCH } from './branches/mental';
import { PAEDS_GENERAL_BRANCH } from './branches/paedsGeneral';
import { OTHER_BRANCH } from './branches/other';
import { TAIL_QUESTIONS } from './tail';

const BRANCHES: Record<BranchId, Branch> = {
  chest_pain: CHEST_PAIN_BRANCH,
  breathing: BREATHING_BRANCH,
  abdominal_pain: ABDOMINAL_BRANCH,
  neuro: NEURO_BRANCH,
  fever: FEVER_BRANCH,
  trauma: TRAUMA_BRANCH,
  bleeding: BLEEDING_BRANCH,
  gi: GI_BRANCH,
  obstetric: OBSTETRIC_BRANCH,
  poisoning: POISONING_BRANCH,
  burn: BURN_BRANCH,
  allergy: ALLERGY_BRANCH,
  urinary: URINARY_BRANCH,
  mental_behavioural: MENTAL_BRANCH,
  paeds_general: PAEDS_GENERAL_BRANCH,
  other: OTHER_BRANCH,
};

export function getBranch(id: BranchId): Branch {
  return BRANCHES[id];
}

/** Every question in every branch, plus the tail, indexed by id — the
 *  single lookup engine.ts and the components need to render "the
 *  question on screen right now" from a plan of bare ids. */
const ALL_QUESTIONS: Record<string, Question> = {};
for (const branch of Object.values(BRANCHES)) {
  for (const q of branch.questions) ALL_QUESTIONS[q.id] = q;
}
for (const q of TAIL_QUESTIONS) ALL_QUESTIONS[q.id] = q;

export function getQuestion(id: string): Question | undefined {
  return ALL_QUESTIONS[id];
}

/**
 * Builds the ordered plan of question ids for a branch: the branch's own
 * questions, then every tail question whose `askIf` passes (or which has
 * none). Re-evaluated whenever the branch is first chosen — askIf gates
 * read from the session's answers-so-far, so age/sex gates are already
 * resolved by the time this runs (Basics is always answered first).
 */
export function buildPlan(branchId: BranchId, answers: SessionAnswers): string[] {
  const branch = getBranch(branchId);
  const branchQuestionIds = branch.questions
    .filter((q) => !q.askIf || q.askIf(answers))
    .map((q) => q.id);
  const tailIds = TAIL_QUESTIONS
    .filter((q) => !q.askIf || q.askIf(answers))
    .map((q) => q.id);
  return [...branchQuestionIds, ...tailIds];
}

export { TAIL_QUESTIONS } from './tail';
export { resolveStratum, PAEDIATRIC_STRATA } from './ageStratum';
export * from './types';
