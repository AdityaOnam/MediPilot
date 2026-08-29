import type { Branch } from '../types';

/**
 * The generic fallback branch. Every complaint that /api/intake/classify
 * cannot confidently place in one of the 15 named branches lands here —
 * a branch that never fires is worse than no branch, so `other` must be
 * usable on its own rather than a dead end.
 */
export const OTHER_BRANCH: Branch = {
  id: 'other',
  label: { en: 'General', hi: 'सामान्य' },
  questions: [
    {
      id: 'other_location',
      kind: 'free_text',
      prompt: { en: 'Where exactly do you feel it?', hi: 'आपको यह ठीक कहां महसूस होता है?' },
    },
    {
      id: 'other_severity',
      kind: 'choice',
      prompt: { en: 'How would you describe it?', hi: 'आप इसे कैसे बताएंगे?' },
      options: [
        { value: 'mild', label: { en: 'Mild', hi: 'हल्का' } },
        { value: 'moderate', label: { en: 'Moderate', hi: 'मध्यम' } },
        { value: 'severe', label: { en: 'Severe', hi: 'गंभीर' } },
      ],
      synonyms: {
        mild: ['not too bad', 'thoda', 'थोड़ा'],
        moderate: ['medium', 'theek thak', 'ठीक ठाक'],
        severe: ['very bad', 'bahut zyada', 'बहुत ज्यादा'],
      },
    },
    {
      id: 'other_getting_worse',
      kind: 'yes_no',
      prompt: { en: 'Is it getting worse?', hi: 'क्या यह बढ़ता जा रहा है?' },
    },
    {
      // The generic branch still has to be able to catch the two things
      // that cannot wait, since anything the classifier could not place
      // ends up here.
      id: 'other_alert',
      kind: 'yes_no',
      prompt: {
        en: 'Are you fully awake and thinking clearly?',
        hi: 'क्या आप पूरी तरह होश में हैं और साफ सोच पा रहे हैं?',
      },
      observes: ['altered_consciousness'],
      observeOn: 'no',
    },
    {
      id: 'other_breathing',
      kind: 'yes_no',
      prompt: {
        en: 'Can you speak a full sentence without stopping for breath?',
        hi: 'क्या आप बिना रुके पूरा वाक्य बोल सकते हैं?',
      },
      observes: ['difficulty_speaking_full_sentences'],
      observeOn: 'no',
    },
  ],
};
