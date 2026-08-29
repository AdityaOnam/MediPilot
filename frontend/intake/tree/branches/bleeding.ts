import type { Branch } from '../types';

export const BLEEDING_BRANCH: Branch = {
  id: 'bleeding',
  label: { en: 'Bleeding', hi: 'खून बहना' },
  questions: [
    {
      id: 'bl_source',
      kind: 'free_text',
      prompt: { en: 'Where is the bleeding coming from?', hi: 'खून कहां से बह रहा है?' },
    },
    {
      // Positively phrased, so NO is the alarming answer.
      id: 'bl_stopping',
      kind: 'yes_no',
      prompt: {
        en: 'Does the bleeding slow down when you press on it?',
        hi: 'क्या दबाने पर खून बहना कम हो जाता है?',
      },
      observes: ['uncontrolled_bleeding_or_penetrating_injury'],
      observeOn: 'no',
    },
    {
      id: 'bl_amount',
      kind: 'choice',
      prompt: { en: 'How much blood is there?', hi: 'कितना खून बह रहा है?' },
      options: [
        { value: 'spotting', label: { en: 'A few spots', hi: 'कुछ बूंदें' } },
        { value: 'steady', label: { en: 'A steady trickle', hi: 'लगातार रिस रहा है' } },
        { value: 'soaking', label: { en: 'Soaking through cloth', hi: 'कपड़ा भीग रहा है' } },
      ],
      synonyms: {
        spotting: ['a little', 'thoda', 'थोड़ा', 'few drops'],
        steady: ['continuous', 'lagatar', 'लगातार'],
        soaking: ['a lot', 'bahut', 'बहुत ज्यादा', 'pouring'],
      },
    },
    {
      id: 'bl_dizzy',
      kind: 'yes_no',
      prompt: { en: 'Do you feel dizzy or faint?', hi: 'क्या आपको चक्कर या बेहोशी जैसा लग रहा है?' },
    },
    {
      // Changes the disposition entirely — anticoagulation turns a minor
      // bleed into a serious one.
      id: 'bl_blood_thinners',
      kind: 'yes_no',
      prompt: {
        en: 'Do you take blood-thinning medicine, like warfarin or aspirin?',
        hi: 'क्या आप खून पतला करने की दवा लेते हैं, जैसे वारफरिन या एस्पिरिन?',
      },
    },
  ],
};
