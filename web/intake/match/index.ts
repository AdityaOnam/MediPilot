import type { Lang, Question } from '../tree/types';
import { ACCEPT_THRESHOLD, matchLocal } from './local';
import { matchRemote } from './remote';

export { ACCEPT_THRESHOLD, matchLocal, matchYesNo, matchScale, matchNumber, matchOption } from './local';
export type { LocalMatch } from './local';

export interface MatchVerdict {
  /** The option value (or the free text) to submit, or null for NONE. */
  value: string | null;
  confidence: number;
  /** 0 = exact lexicon, 1 = local similarity, 2 = Groq picker. */
  tier: 0 | 1 | 2;
}

/**
 * Runs the tiers in order and stops at the first that clears the bar.
 * Groq is never consulted for free text, for yes/no, or for a scale —
 * only for a `choice` question whose local score fell short.
 */
export async function matchAnswer(
  transcript: string,
  question: Question,
  signal?: AbortSignal,
  lang: Lang = 'en',
): Promise<MatchVerdict> {
  const local = matchLocal(transcript, question, lang);
  if (local.value !== null && local.confidence >= ACCEPT_THRESHOLD) {
    return { value: local.value, confidence: local.confidence, tier: local.tier };
  }

  if (question.kind !== 'choice') {
    return { value: null, confidence: local.confidence, tier: local.tier };
  }

  const remote = await matchRemote(transcript, question, signal);
  return remote
    ? { value: remote, confidence: 0.9, tier: 2 }
    : { value: null, confidence: local.confidence, tier: 2 };
}
