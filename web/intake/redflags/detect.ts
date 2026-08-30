import { RED_FLAGS, type RedFlagDef } from './observations';

/**
 * Tier A — deterministic, offline, instant. Runs on every free-text
 * answer (engine.ts calls this synchronously before anything else touches
 * the network) so the interrupt can never be delayed by wifi. Tier B
 * (the Groq observer, /api/intake/observe — B6/B7) runs in parallel and
 * can ONLY add flags this table missed; it never overrides what fires here.
 */
const PHRASES: Record<string, string[]> = {
  altered_consciousness: [
    'not responding', 'unresponsive', 'confused', 'disoriented', 'passed out', 'unconscious',
    'hosh nahi', 'behosh', 'बेहोश', 'होश नहीं',
  ],
  active_labour_or_bleeding_pregnancy: [
    'labour', 'labor', 'contractions', 'water broke', 'pregnant and bleeding',
    'प्रसव', 'दर्द उठ रहा है', 'पानी टूट गया',
  ],
  // Deliberately NOT a plain "chest pain" trigger — the rule is chest pain
  // COMBINED WITH sweating, radiation, or breathlessness (see the compound
  // check below). Chest pain alone routes into the chest_pain branch's
  // questions instead, which is where that combination actually gets
  // established. Firing on bare "chest pain" would call a nurse on every
  // stable angina and reflux presentation too.
  difficulty_speaking_full_sentences: [
    'cannot breathe', 'can\'t breathe', 'gasping', 'cannot talk', 'out of breath',
    'सांस नहीं ले पा', 'बोल नहीं पा',
  ],
  sudden_onesided_weakness_facial_droop_speech_change: [
    'one side weak', 'face drooping', 'slurred speech', 'cannot move my arm', 'facial droop',
    'लकवा', 'एक तरफ कमजोर', 'चेहरा टेढ़ा',
  ],
  uncontrolled_bleeding_or_penetrating_injury: [
    'bleeding heavily', 'won\'t stop bleeding', 'stabbed', 'gunshot', 'deep cut', 'blood everywhere',
    'बहुत खून बह रहा', 'खून नहीं रुक रहा', 'गहरा घाव',
  ],
  poisoning_overdose_or_snakebite: [
    'poison', 'overdose', 'snake bit', 'snakebite', 'swallowed pills', 'took too many',
    'जहर खा लिया', 'सांप ने काटा', 'ओवरडोज',
  ],
  infant_not_feeding_floppy_inconsolable: [
    'not feeding', 'floppy', 'won\'t stop crying', 'inconsolable', 'limp baby',
    'दूध नहीं पी रहा', 'ढीला पड़ गया', 'रोना बंद नहीं',
  ],
};

// RF-03 is the one flag in the table that is a genuine compound condition
// rather than a single symptom — chest pain BY ITSELF is common and not
// urgent on its own; chest pain WITH sweating, radiation, or breathlessness
// is the ACS pattern the rule exists to catch. Kept out of PHRASES above so
// it can be checked as a conjunction instead of a single substring.
const CHEST_PAIN_WORDS = ['chest pain', 'crushing chest', 'सीने में दर्द', 'सीने का दर्द'];
const CHEST_PAIN_QUALIFIERS = [
  'sweating', 'sweat', 'radiating', 'left arm', 'jaw', 'neck pain', 'breathless', 'short of breath',
  'पसीना', 'बांह में दर्द', 'जबड़े', 'सांस फूल',
];

export function detectRedFlagsLocal(text: string): RedFlagDef[] {
  const norm = (text || '').toLowerCase();
  if (!norm.trim()) return [];
  const hits: RedFlagDef[] = [];

  for (const flag of RED_FLAGS) {
    const phrases = PHRASES[flag.observation] ?? [];
    if (phrases.some((p) => norm.includes(p.toLowerCase()))) hits.push(flag);
  }

  const hasChestPain = CHEST_PAIN_WORDS.some((w) => norm.includes(w.toLowerCase()));
  const hasQualifier = CHEST_PAIN_QUALIFIERS.some((w) => norm.includes(w.toLowerCase()));
  if (hasChestPain && hasQualifier) {
    const flag = RED_FLAGS.find((f) => f.observation === 'chest_pain_with_sweating_radiation_breathlessness');
    if (flag && !hits.includes(flag)) hits.push(flag);
  }

  return hits;
}
