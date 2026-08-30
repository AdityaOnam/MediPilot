import type { Branch } from '../types';

export const ALLERGY_BRANCH: Branch = {
  id: 'allergy',
  label: { en: 'Allergic reaction', hi: 'एलर्जी प्रतिक्रिया' },
  questions: [
    {
      // Airway questions come first — anaphylaxis is the reason this
      // branch exists, and it is the only thing here that cannot wait.
      id: 'al_swelling_face',
      kind: 'yes_no',
      prompt: {
        en: 'Are your lips, tongue or throat swelling?',
        hi: 'क्या आपके होंठ, जीभ या गला सूज रहा है?',
      },
      observes: ['difficulty_speaking_full_sentences'],
    },
    {
      id: 'al_breathless',
      kind: 'yes_no',
      prompt: {
        en: 'Is it hard to breathe or swallow?',
        hi: 'क्या सांस लेने या निगलने में तकलीफ हो रही है?',
      },
      observes: ['difficulty_speaking_full_sentences'],
    },
    {
      id: 'al_trigger',
      kind: 'free_text',
      prompt: { en: 'What do you think caused it?', hi: 'आपको क्या लगता है इसकी वजह क्या है?' },
    },
    {
      id: 'al_rash_spreading',
      kind: 'yes_no',
      prompt: { en: 'Is the rash spreading?', hi: 'क्या दाने फैल रहे हैं?' },
    },
    {
      id: 'al_had_before',
      kind: 'yes_no',
      prompt: {
        en: 'Have you had a serious reaction like this before?',
        hi: 'क्या पहले भी आपको ऐसी गंभीर प्रतिक्रिया हुई है?',
      },
    },
  ],
};
