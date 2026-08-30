import type { SessionState } from './types';
import { getQuestion } from './index';
import { STR, t } from '../strings';
import type { IntakeAnswer } from '@/lib/api/types';

/**
 * Turn a finished session into the record the nurse card renders.
 *
 * Built HERE, at submit time, rather than reconstructed on the nurse side,
 * because only this module knows the tree � and because the prompt has to
 * be captured as it was actually put to the patient. See the note on
 * IntakeAnswer in lib/api/types.ts.
 *
 * Order matters: the plan order is the order the patient was asked in, and
 * a nurse reading the card is reading a conversation, not a field dump.
 */
export function buildTranscript(s: SessionState): IntakeAnswer[] {
  const out: IntakeAnswer[] = [];

  if (s.chiefComplaint) {
    out.push({
      id: 'chief_complaint',
      question: t(s.lang, STR.openingQ),
      answer: s.chiefComplaint,
    });
  }

  // Walk the plan, not Object.keys(answers): the plan preserves the order
  // the questions were actually asked in, including branch splices.
  const seen = new Set<string>(['chief_complaint']);
  for (const id of s.plan) {
    if (seen.has(id)) continue;
    seen.add(id);
    const value = s.answers[id];
    if (value === undefined || value === '') continue;
    const q = getQuestion(id);
    out.push({ id, question: q ? t(s.lang, q.prompt) : id, answer: value });
  }

  // Anything answered but not in the plan (a question spliced then pruned,
  // or an observed field) still belongs on the record.
  for (const [id, value] of Object.entries(s.answers)) {
    if (id.startsWith('__') || seen.has(id) || !value) continue;
    seen.add(id);
    const q = getQuestion(id);
    out.push({ id, question: q ? t(s.lang, q.prompt) : id, answer: value });
  }

  if (s.painScore !== null) {
    out.push({ id: 'pain_score', question: t(s.lang, STR.painQ), answer: String(s.painScore) });
  }

  return out;
}
