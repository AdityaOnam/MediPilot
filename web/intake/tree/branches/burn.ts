import type { Branch } from '../types';

export const BURN_BRANCH: Branch = {
  id: 'burn',
  label: { en: 'Burn', hi: 'जलना' },
  questions: [
    {
      id: 'bu_cause',
      kind: 'choice',
      prompt: { en: 'What caused the burn?', hi: 'जलन किस वजह से हुई?' },
      options: [
        { value: 'flame', label: { en: 'Fire or flame', hi: 'आग' } },
        { value: 'hot_liquid', label: { en: 'Hot liquid or steam', hi: 'गर्म तरल या भाप' } },
        { value: 'chemical', label: { en: 'Chemical', hi: 'रसायन' } },
        { value: 'electrical', label: { en: 'Electricity', hi: 'बिजली' } },
      ],
      synonyms: {
        flame: ['fire', 'aag', 'आग', 'stove'],
        hot_liquid: ['boiling water', 'scald', 'garam pani', 'गर्म पानी', 'tea', 'oil'],
        chemical: ['acid', 'tezaab', 'तेजाब', 'cleaner'],
        electrical: ['current', 'shock', 'bijli', 'बिजली', 'karant'],
      },
    },
    {
      // Airway burn. The one answer here that cannot wait.
      id: 'bu_face_airway',
      kind: 'yes_no',
      prompt: {
        en: 'Was your face, mouth or throat burned, or did you breathe in smoke?',
        hi: 'क्या आपका चेहरा, मुंह या गला जला, या आपने धुआं अंदर लिया?',
      },
      observes: ['difficulty_speaking_full_sentences'],
    },
    {
      id: 'bu_area',
      kind: 'free_text',
      prompt: {
        en: 'Which part of the body, and roughly how big is it?',
        hi: 'शरीर का कौन सा हिस्सा, और लगभग कितना बड़ा है?',
      },
    },
    {
      id: 'bu_when',
      kind: 'choice',
      prompt: { en: 'When did it happen?', hi: 'यह कब हुआ?' },
      options: [
        { value: 'just_now', label: { en: 'Just now', hi: 'अभी अभी' } },
        { value: 'today', label: { en: 'Earlier today', hi: 'आज पहले' } },
        { value: 'days', label: { en: 'A day or more ago', hi: 'एक दिन या ज्यादा पहले' } },
      ],
    },
    {
      id: 'bu_blisters',
      kind: 'yes_no',
      prompt: { en: 'Are there blisters, or is the skin broken?', hi: 'क्या छाले हैं, या त्वचा फट गई है?' },
    },
  ],
};
