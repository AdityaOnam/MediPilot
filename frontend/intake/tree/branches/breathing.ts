import type { Branch } from '../types';

export const BREATHING_BRANCH: Branch = {
  id: 'breathing',
  label: { en: 'Breathing difficulty', hi: 'सांस लेने में तकलीफ' },
  questions: [
    {
      id: 'br_onset',
      kind: 'choice',
      prompt: { en: 'When did the breathlessness start?', hi: 'सांस फूलना कब शुरू हुआ?' },
      options: [
        { value: 'just_now', label: { en: 'Just now', hi: 'अभी अभी' } },
        { value: 'today', label: { en: 'Earlier today', hi: 'आज पहले' } },
        { value: 'days', label: { en: 'A few days ago', hi: 'कुछ दिन पहले' } },
      ],
      synonyms: {
        just_now: ['right now', 'suddenly', 'abhi', 'अभी', 'achanak'],
        today: ['this morning', 'aaj', 'आज सुबह', 'subah se'],
        days: ['a week', 'kai din', 'कई दिन से', 'long time'],
      },
    },
    {
      // Phrased positively because that is what a breathless patient can
      // actually answer — so NO is the alarming answer here.
      id: 'br_speak_sentences',
      kind: 'yes_no',
      prompt: {
        en: 'Can you speak a full sentence without stopping for breath?',
        hi: 'क्या आप बिना रुके पूरा वाक्य बोल सकते हैं?',
      },
      observes: ['difficulty_speaking_full_sentences'],
      observeOn: 'no',
    },
    {
      id: 'br_at_rest',
      kind: 'yes_no',
      prompt: {
        en: 'Is it hard to breathe even when you are sitting still?',
        hi: 'क्या आराम से बैठे हुए भी सांस लेने में तकलीफ होती है?',
      },
    },
    {
      id: 'br_chest_pain',
      kind: 'yes_no',
      prompt: { en: 'Do you have chest pain along with it?', hi: 'क्या इसके साथ सीने में दर्द भी है?' },
      observes: ['chest_pain_with_sweating_radiation_breathlessness'],
    },
    {
      id: 'br_wheeze',
      kind: 'yes_no',
      prompt: { en: 'Is your breathing noisy or wheezy?', hi: 'क्या सांस लेते समय आवाज़ या सीटी जैसी आती है?' },
    },
    {
      id: 'br_known_lung',
      kind: 'yes_no',
      prompt: { en: 'Do you have asthma or a known lung condition?', hi: 'क्या आपको अस्थमा या फेफड़ों की कोई बीमारी है?' },
    },
  ],
};
