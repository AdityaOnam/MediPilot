/** The shape both question sources agree on: the static frontend tree in
 *  questionTree.ts and the real backend tree served by
 *  backend/orchestrator/tree_session.py. */
export interface MatchableOption {
  value: string;
  label: { en: string; hi: string };
}

/**
 * Matches a spoken answer against the current question's closed answer set
 * (yes/no or multiple-choice options) so voice input can auto-advance the
 * kiosk the same way tapping a button does.
 *
 * This is a keyword/token-overlap matcher, not a semantic embedding model —
 * it is the fast, dependency-free placeholder until the Kaggle bake-off
 * (eval/kaggle/) picks a small local embedding model for this job. It is
 * good enough for short, closed-set phrases ("just now", "a few hours ago")
 * where the vocabulary is small and known in advance; it will not generalize
 * to open-ended rephrasing the way an embedding match would. Swap the body
 * of `scoreOption` for an embedding-similarity call when that lands, without
 * changing the threshold contract below.
 */

export interface MatchResult<T> {
  match: T | null;
  confidence: number; // 0..1
}

/** Below this, the spoken answer is treated as "not one of the options" —
 * the caller falls back to the LLM structurer instead of guessing. Picked
 * empirically against the option sets in questionTree.ts (short 1-4 word
 * labels); revisit once real spoken-answer audio is collected. */
export const MATCH_CONFIDENCE_THRESHOLD = 0.5;

// Ported from intake/question_tree.py's _YES_KEYWORDS/_NO_KEYWORDS
// (backend, Python) so the frontend's own yes/no reading matches the same
// vocabulary the backend tree already validates against — not a fresh
// translation, the same bilingual word list.
const NO_WORDS = [
  'no', 'nope', 'nah', 'not really', 'dont think so', 'never',
  'nahi', 'nahin', 'bilkul nahi', 'non',
  'नहीं', 'नही',
];
const YES_WORDS = [
  'yes', 'yeah', 'yep', 'yup', 'sure', 'definitely', 'correct',
  'haan', 'han', 'ha', 'bilkul',
  'हाँ', 'हां',
];

function normalize(text: string): string {
  return (text || '')
    .trim()
    .toLowerCase()
    .replace(/'/g, '')
    .replace(/[.,!?;:()[\]"“”‘’…—–।॥]+/g, ' ')
    .replace(/\s+/g, ' ')
    .trim();
}

function containsWord(text: string, phrase: string): boolean {
  return new RegExp(`(?:^|\\s)${phrase.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')}(?:\\s|$)`).test(text);
}

export function matchYesNo(transcript: string): MatchResult<'yes' | 'no'> {
  const normalized = normalize(transcript);
  if (!normalized) return { match: null, confidence: 0 };
  // Negation checked first, same as the backend parser: "not really" must
  // never read as yes just because it contains no "no" token boundary trick.
  if (NO_WORDS.some(w => containsWord(normalized, w))) return { match: 'no', confidence: 1 };
  if (YES_WORDS.some(w => containsWord(normalized, w))) return { match: 'yes', confidence: 1 };
  return { match: null, confidence: 0 };
}

function tokenize(text: string): Set<string> {
  return new Set(normalize(text).split(' ').filter(Boolean));
}

/** Jaccard token overlap between the transcript and one label. Symmetric,
 * cheap, and works reasonably for short phrases -- "a few hours ago" vs
 * "few hours ago" scores high; unrelated phrases score near 0. */
function jaccard(a: Set<string>, b: Set<string>): number {
  if (a.size === 0 || b.size === 0) return 0;
  let intersection = 0;
  for (const tok of a) if (b.has(tok)) intersection++;
  const union = a.size + b.size - intersection;
  return union === 0 ? 0 : intersection / union;
}

export function matchOption(
  transcript: string,
  options: MatchableOption[],
): MatchResult<MatchableOption> {
  if (!options.length) return { match: null, confidence: 0 };

  const spoken = tokenize(transcript);
  if (spoken.size === 0) return { match: null, confidence: 0 };

  let best: MatchableOption | null = null;
  let bestScore = 0;
  for (const option of options) {
    const enScore = jaccard(spoken, tokenize(option.label.en));
    const hiScore = jaccard(spoken, tokenize(option.label.hi));
    // The raw value slug ("hours", "mild") is also a legitimate thing a
    // patient might just say verbatim.
    const valueScore = jaccard(spoken, tokenize(option.value.replace(/[-_]/g, ' ')));
    const score = Math.max(enScore, hiScore, valueScore);
    if (score > bestScore) {
      bestScore = score;
      best = option;
    }
  }
  return { match: best, confidence: bestScore };
}
