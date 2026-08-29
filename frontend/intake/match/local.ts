import type { Lang, Option, Question } from '../tree/types';
import { containsWord, editSimilarity, normalize, tokenSet } from './normalize';
import {
  asciiDigits, EN_TENS, EN_UNITS,
  HI_FORMS_ROMAN_AMBIGUOUS, HI_FORMS_ROMAN_SAFE, HI_FORMS_SCRIPT,
} from './numbers';

/**
 * Tiers 0 and 1 — everything that resolves with zero network. Tier 2
 * (the Groq picker in remote.ts) is only reached when tier 1 scores below
 * ACCEPT_THRESHOLD, so the common answers never cost a round-trip.
 */

/** Below this the spoken answer is "not one of the options" and the
 *  caller escalates to Groq rather than guessing. */
export const ACCEPT_THRESHOLD = 0.55;

// ---- tier 0: exact lexicons -------------------------------------------------

// Negation is checked FIRST everywhere below: "not really" must never read
// as yes on the strength of containing no "no" token boundary trick.
const NO_WORDS = [
  'no', 'nope', 'nah', 'not really', 'dont think so', 'do not think so', 'never', 'negative',
  'nahi', 'nahin', 'nai', 'bilkul nahi', 'na',
  'नहीं', 'नही', 'ना', 'बिल्कुल नहीं',
];

const YES_WORDS = [
  'yes', 'yeah', 'yep', 'yup', 'sure', 'definitely', 'correct', 'right', 'ok', 'okay', 'affirmative',
  'haan', 'han', 'ha', 'haa', 'bilkul', 'ji', 'ji haan',
  'हाँ', 'हां', 'जी', 'जी हाँ', 'बिल्कुल',
];

export interface LocalMatch {
  value: string | null;
  confidence: number;
  tier: 0 | 1;
}

export function matchYesNo(transcript: string): LocalMatch {
  const n = normalize(transcript);
  if (!n) return { value: null, confidence: 0, tier: 0 };
  if (NO_WORDS.some((w) => containsWord(n, w))) return { value: 'no', confidence: 1, tier: 0 };
  if (YES_WORDS.some((w) => containsWord(n, w))) return { value: 'yes', confidence: 1, tier: 0 };
  return { value: null, confidence: 0, tier: 0 };
}

/**
 * 0–10 for pain and other scale questions.
 *
 * Delegates to the same parser as an open number, bounded to the scale's
 * eleven legal values. It used to carry its own word list, which meant the
 * romanised-Hindi/English collisions ("do" = 2) had to be fixed twice and
 * were in fact only fixed once — a patient saying "I do not know" scored a
 * 2 out of 10 for pain. Anything outside 0–10 is a mis-hear and is
 * rejected rather than clamped: a pain score of 72 is not a 10.
 */
export function matchScale(transcript: string, lang: Lang = 'en'): LocalMatch {
  return matchNumber(transcript, [0, 10], lang);
}

/**
 * An open numeric answer — age, and anything else measured rather than
 * rated. Unlike `matchScale` this accepts the whole plausible range and
 * understands the way people actually say numbers out loud:
 *
 *   "72"            "७२"              (digits, either script)
 *   "seventy two"   "seventy-two"     (English compounds)
 *   "बहत्तर"         "bahattar"        (Hindi, irregular past twenty)
 *   "I'm 72 years old"  "72 saal ka"  (numbers buried in a sentence)
 *
 * `range` rejects the implausible instead of accepting it: an age of 300
 * is a recognition error, and taking it would resolve the patient into the
 * wrong age stratum — which changes every downstream vital threshold.
 */
export function matchNumber(
  transcript: string,
  range: [number, number] = [0, 120],
  lang: Lang = 'en',
): LocalMatch {
  const [min, max] = range;
  const inRange = (v: number) => Number.isFinite(v) && v >= min && v <= max;
  const hit = (v: number): LocalMatch => ({ value: String(v), confidence: 1, tier: 0 });

  const raw = asciiDigits(transcript);

  // A spoken negative is never a valid age or count. Rejected outright
  // rather than left to the range check, so "minus five" cannot be read as
  // a plain five once the sign word is dropped by normalisation.
  if (/(^|\s)(minus|negative|माइनस|ऋण)(\s|$)/i.test(normalize(raw))) {
    return { value: null, confidence: 0, tier: 0 };
  }
  if (/-\s*\d/.test(raw)) return { value: null, confidence: 0, tier: 0 };

  // Hyphens are split here rather than in the shared normaliser, which
  // other matchers rely on leaving alone.
  const n = normalize(raw.replace(/[-–—]/g, ' '));
  if (!n) return { value: null, confidence: 0, tier: 0 };

  // 1. Digits win outright — the least ambiguous thing a patient can say.
  //    Every run is considered so "counter 3, I am 72" still lands on 72.
  const digits = n.match(/\d+/g);
  if (digits) {
    const valid = digits.map(Number).filter(inRange);
    if (valid.length > 0) return hit(valid[0]);
  }

  // 2. Hindi. Devanagari and unambiguous romanisations match in either
  //    language mode — code-mixing is normal. Longest form first, so
  //    इक्कीस (21) beats the एक (1) hiding inside it.
  const hindiForms = lang === 'hi'
    ? [...HI_FORMS_SCRIPT, ...HI_FORMS_ROMAN_SAFE, ...HI_FORMS_ROMAN_AMBIGUOUS]
        .sort((a, b) => b[0].length - a[0].length)
    : [...HI_FORMS_SCRIPT, ...HI_FORMS_ROMAN_SAFE]
        .sort((a, b) => b[0].length - a[0].length);

  for (const [form, value] of hindiForms) {
    if (containsWord(n, form) && inRange(value)) return hit(value);
  }

  // 3. English, composing an adjacent tens + unit pair ("seventy two").
  const words = n.split(' ').filter(Boolean);
  for (let i = 0; i < words.length; i++) {
    const tens = EN_TENS[words[i]];
    if (tens !== undefined) {
      const unit = EN_UNITS[words[i + 1] ?? ''];
      const combined = unit !== undefined && unit >= 1 && unit <= 9 ? tens + unit : tens;
      if (inRange(combined)) return hit(combined);
      continue;
    }
    const unit = EN_UNITS[words[i]];
    if (unit !== undefined && inRange(unit)) return hit(unit);
  }

  // "a hundred" / "सौ" with nothing attached.
  if (containsWord(n, 'hundred') && inRange(100)) return hit(100);

  return { value: null, confidence: 0, tier: 0 };
}

// ---- tier 1: similarity over labels, slugs and synonyms ---------------------

function jaccard(a: Set<string>, b: Set<string>): number {
  if (a.size === 0 || b.size === 0) return 0;
  let hit = 0;
  for (const tok of a) if (b.has(tok)) hit++;
  const union = a.size + b.size - hit;
  return union === 0 ? 0 : hit / union;
}

/** Best score for one option across every surface form it has: the
 *  English label, the Hindi label, the raw value slug, and every entry in
 *  the question's synonym list for that value. */
function scoreOption(spokenTokens: Set<string>, spokenRaw: string, option: Option, synonyms: string[]): number {
  const forms = [
    option.label.en,
    option.label.hi,
    option.value.replace(/[-_]/g, ' '),
    ...synonyms,
  ];

  let best = 0;
  for (const form of forms) {
    const overlap = jaccard(spokenTokens, tokenSet(form));
    if (overlap > best) best = overlap;

    // Rescue ASR near-misses on short labels only — on a long sentence
    // edit distance is noise, not signal.
    if (form.length <= 24) {
      const edit = editSimilarity(spokenRaw, form);
      if (edit > 0.8 && edit > best) best = edit;
    }
  }
  return best;
}

export function matchOption(transcript: string, question: Question): LocalMatch {
  const options = question.options ?? [];
  if (options.length === 0) return { value: null, confidence: 0, tier: 1 };

  const spokenTokens = tokenSet(transcript);
  if (spokenTokens.size === 0) return { value: null, confidence: 0, tier: 1 };

  let best: string | null = null;
  let bestScore = 0;
  for (const option of options) {
    const syns = question.synonyms?.[option.value] ?? [];
    const score = scoreOption(spokenTokens, transcript, option, syns);
    if (score > bestScore) {
      bestScore = score;
      best = option.value;
    }
  }
  return { value: best, confidence: bestScore, tier: 1 };
}

/** Entry point for tiers 0+1. Returns a null value when nothing cleared
 *  the bar — the caller decides whether to escalate to Groq. */
export function matchLocal(transcript: string, question: Question, lang: Lang = 'en'): LocalMatch {
  switch (question.kind) {
    case 'yes_no':
      return matchYesNo(transcript);
    case 'scale_0_10':
      return matchScale(transcript, lang);
    case 'number':
      // Was routed to matchScale, which only ever recognised 0–10 — so any
      // age above ten was silently unmatchable by voice.
      return matchNumber(transcript, question.numberRange, lang);
    case 'choice':
      return matchOption(transcript, question);
    case 'free_text':
    default:
      // Free text is its own answer — there is nothing to match against.
      return { value: transcript.trim() || null, confidence: transcript.trim() ? 1 : 0, tier: 0 };
  }
}
