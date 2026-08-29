/**
 * Devanagari-aware normalisation. Deliberately does NOT strip non-ASCII —
 * the Hindi labels and the Hindi half of every synonym list have to
 * survive this, so only punctuation (including the danda) is removed.
 */
const PUNCT = /[.,!?;:()[\]"“”‘’…—–/\\|]+/g;

export function normalize(text: string): string {
  return (text || '')
    .trim()
    .toLowerCase()
    .replace(/['’]/g, '')
    .replace(/[।॥]/g, ' ')
    .replace(PUNCT, ' ')
    .replace(/\s+/g, ' ')
    .trim();
}

export function tokens(text: string): string[] {
  const n = normalize(text);
  return n ? n.split(' ').filter(Boolean) : [];
}

export function tokenSet(text: string): Set<string> {
  return new Set(tokens(text));
}

/** Whole-word containment, so "no" does not match inside "normal". */
export function containsWord(haystackNormalized: string, phrase: string): boolean {
  const p = normalize(phrase);
  if (!p) return false;
  const escaped = p.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
  return new RegExp(`(?:^|\\s)${escaped}(?:\\s|$)`).test(haystackNormalized);
}

/** Levenshtein, capped — only used to rescue ASR near-misses on short
 *  option labels ("tight band" heard as "tight bend"), never as a primary
 *  similarity signal. */
export function levenshtein(a: string, b: string): number {
  if (a === b) return 0;
  if (!a.length) return b.length;
  if (!b.length) return a.length;

  let prev = Array.from({ length: b.length + 1 }, (_, i) => i);
  let curr = new Array<number>(b.length + 1);

  for (let i = 1; i <= a.length; i++) {
    curr[0] = i;
    for (let j = 1; j <= b.length; j++) {
      const cost = a[i - 1] === b[j - 1] ? 0 : 1;
      curr[j] = Math.min(curr[j - 1] + 1, prev[j] + 1, prev[j - 1] + cost);
    }
    [prev, curr] = [curr, prev];
  }
  return prev[b.length];
}

/** 0..1 similarity from edit distance, relative to the longer string. */
export function editSimilarity(a: string, b: string): number {
  const na = normalize(a);
  const nb = normalize(b);
  if (!na || !nb) return 0;
  const longest = Math.max(na.length, nb.length);
  return 1 - levenshtein(na, nb) / longest;
}
