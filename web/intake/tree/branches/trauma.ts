import type { Branch } from '../types';

export const TRAUMA_BRANCH: Branch = {
  id: 'trauma',
  label: { en: 'Injury', hi: 'चोट' },
  questions: [
    {
      id: 'tr_mechanism',
      kind: 'free_text',
      prompt: { en: 'What happened?', hi: 'क्या हुआ?' },
    },
    {
      id: 'tr_when',
      kind: 'choice',
      prompt: { en: 'When did it happen?', hi: 'यह कब हुआ?' },
      options: [
        { value: 'just_now', label: { en: 'Just now', hi: 'अभी अभी' } },
        { value: 'today', label: { en: 'Earlier today', hi: 'आज पहले' } },
        { value: 'days', label: { en: 'A few days ago', hi: 'कुछ दिन पहले' } },
      ],
      synonyms: {
        just_now: ['minutes ago', 'abhi', 'अभी'],
        today: ['this morning', 'aaj', 'आज'],
        days: ['yesterday', 'kal', 'कल', 'kai din'],
      },
    },
    {
      id: 'tr_bleeding_uncontrolled',
      kind: 'yes_no',
      prompt: { en: 'Is there bleeding that will not stop?', hi: 'क्या ऐसा खून बह रहा है जो रुक नहीं रहा?' },
      observes: ['uncontrolled_bleeding_or_penetrating_injury'],
    },
    {
      id: 'tr_lost_consciousness',
      kind: 'yes_no',
      prompt: { en: 'Did you black out, even for a moment?', hi: 'क्या आप एक पल के लिए भी बेहोश हुए?' },
      observes: ['altered_consciousness'],
    },
    {
      id: 'tr_head_neck_back',
      kind: 'yes_no',
      prompt: { en: 'Was your head, neck or back hurt?', hi: 'क्या आपके सिर, गर्दन या पीठ पर चोट लगी?' },
    },
    {
      id: 'tr_can_move',
      kind: 'yes_no',
      prompt: { en: 'Can you move the injured part normally?', hi: 'क्या आप चोट वाले हिस्से को सामान्य रूप से हिला सकते हैं?' },
    },
  ],
};
