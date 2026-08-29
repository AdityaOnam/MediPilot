import type { BranchId } from './types';

/**
 * Instant, offline, keyword-based branch classifier. Runs before
 * /api/intake/classify (the Groq-backed version, B6) ever gets a chance:
 * a confident local hit skips the network round-trip the same way the
 * Python tree's lexicon fast-path does, and it is also what `classify`
 * falls back to if Groq times out or the key is missing (fail-soft, per
 * the plan's Part 6). Keyword coverage here does not need to be
 * exhaustive — Groq is the safety net for phrasing this table misses.
 */
const KEYWORDS: Record<Exclude<BranchId, 'other' | 'paeds_general'>, string[]> = {
  chest_pain: ['chest pain', 'chest', 'seene', 'सीने', 'सीना'],
  breathing: ['breath', 'breathless', 'saans', 'सांस', 'dam ghut', 'दम घुट'],
  abdominal_pain: ['stomach', 'abdomen', 'belly', 'pet', 'पेट'],
  neuro: ['weakness', 'numb', 'face droop', 'slurred', 'stroke', 'lakwa', 'लकवा', 'सुन्न'],
  fever: ['fever', 'bukhar', 'bukhaar', 'बुखार', 'temperature'],
  trauma: [
    'fall', 'fell', 'slipped', 'accident', 'hit', 'injury', 'injured', 'wound', 'fracture', 'broke my',
    'giri', 'gir gaya', 'गिर', 'चोट', 'accident hua', 'फ्रैक्चर',
  ],
  bleeding: ['bleeding', 'blood', 'khoon', 'खून', 'रक्तस्राव'],
  gi: ['vomit', 'vomiting', 'diarrhea', 'diarrhoea', 'loose motion', 'ulti', 'उल्टी', 'दस्त'],
  obstetric: ['pregnant', 'pregnancy', 'labour', 'labor', 'contractions', 'garbhvati', 'गर्भवती', 'प्रसव'],
  poisoning: ['poison', 'overdose', 'snake bite', 'snakebite', 'zeher', 'ज़हर', 'जहर', 'सांप'],
  burn: ['burn', 'burnt', 'jal gaya', 'जल गया', 'जलन', 'scald'],
  allergy: ['allergy', 'allergic', 'reaction', 'swelling face', 'एलर्जी', 'सूजन'],
  urinary: ['urine', 'urinating', 'peshab', 'पेशाब', 'urination'],
  mental_behavioural: ['sad', 'anxious', 'panic', 'harm myself', 'suicide', 'pareshan', 'परेशान', 'उदास'],
};

const MIN_CONFIDENT_LEN = 3;

export function localClassify(text: string): BranchId | null {
  const norm = (text || '').toLowerCase();
  if (norm.trim().length < MIN_CONFIDENT_LEN) return null;

  let best: BranchId | null = null;
  let bestHits = 0;
  for (const [branch, words] of Object.entries(KEYWORDS) as [BranchId, string[]][]) {
    const hits = words.filter((w) => norm.includes(w.toLowerCase())).length;
    if (hits > bestHits) {
      bestHits = hits;
      best = branch;
    }
  }
  return bestHits > 0 ? best : null;
}
