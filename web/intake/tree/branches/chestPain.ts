import type { Branch } from '../types';

/**
 * OPQRST-shaped. Three of the six questions feed the red-flag table
 * (RF-03 chest pain + sweating/radiation/breathlessness) — the branch is
 * built as a set of questions chosen because their answers can change a
 * band, not as a generic form. Full content; B8 will not need to revisit
 * this one.
 */
export const CHEST_PAIN_BRANCH: Branch = {
  id: 'chest_pain',
  label: { en: 'Chest pain', hi: 'सीने में दर्द' },
  questions: [
    {
      id: 'cp_onset',
      kind: 'choice',
      prompt: { en: 'When did the chest pain start?', hi: 'सीने का दर्द कब शुरू हुआ?' },
      options: [
        { value: 'just_now', label: { en: 'Just now', hi: 'अभी अभी' } },
        { value: 'within_hour', label: { en: 'Within the last hour', hi: 'पिछले एक घंटे में' } },
        { value: 'today', label: { en: 'Earlier today', hi: 'आज पहले' } },
        { value: 'days', label: { en: 'A few days ago', hi: 'कुछ दिन पहले' } },
      ],
      synonyms: {
        just_now: ['right now', 'this second', 'abhi', 'अभी'],
        within_hour: ['an hour ago', 'ek ghante', 'एक घंटे पहले'],
        today: ['this morning', 'aaj', 'आज सुबह'],
        days: ['a week', 'kai din', 'कई दिन से'],
      },
    },
    {
      id: 'cp_quality',
      kind: 'choice',
      prompt: { en: 'What does the pain feel like?', hi: 'दर्द कैसा महसूस होता है?' },
      options: [
        { value: 'pressure', label: { en: 'Pressure or heaviness', hi: 'दबाव या भारीपन' } },
        { value: 'sharp', label: { en: 'Sharp, stabbing', hi: 'तेज, चुभने वाला' } },
        { value: 'burning', label: { en: 'Burning', hi: 'जलन' } },
        { value: 'tight_band', label: { en: 'A tight band across the chest', hi: 'सीने पर कसी हुई पट्टी जैसा' } },
      ],
      synonyms: {
        pressure: ['heavy', 'someone sitting on my chest', 'bhaari', 'भारी'],
        sharp: ['stabbing', 'teekha', 'तीखा'],
        burning: ['jalan', 'जलन जैसा'],
        tight_band: ['squeezing', 'tight', 'kasa hua', 'कसा हुआ'],
      },
    },
    {
      id: 'cp_radiation',
      kind: 'choice',
      prompt: { en: 'Does the pain spread anywhere?', hi: 'क्या दर्द कहीं और फैलता है?' },
      options: [
        { value: 'left_arm', label: { en: 'Left arm', hi: 'बाईं बांह' } },
        { value: 'jaw_neck', label: { en: 'Jaw or neck', hi: 'जबड़ा या गर्दन' } },
        { value: 'back', label: { en: 'Back', hi: 'पीठ' } },
        { value: 'stays_chest', label: { en: 'Stays in the chest', hi: 'सीने में ही रहता है' } },
      ],
      observes: ['chest_pain_with_sweating_radiation_breathlessness'],
    },
    {
      id: 'cp_sweating',
      kind: 'yes_no',
      prompt: { en: 'Are you sweating, or were you sweating when it started?', hi: 'क्या आपको पसीना आ रहा है, या शुरू होते समय आ रहा था?' },
      observes: ['chest_pain_with_sweating_radiation_breathlessness'],
    },
    {
      id: 'cp_breathless',
      kind: 'yes_no',
      prompt: { en: 'Are you finding it hard to breathe?', hi: 'क्या आपको सांस लेने में तकलीफ हो रही है?' },
      observes: ['chest_pain_with_sweating_radiation_breathlessness', 'difficulty_speaking_full_sentences'],
    },
    {
      id: 'cp_exertion',
      kind: 'yes_no',
      prompt: { en: 'Did it start while you were doing something physical?', hi: 'क्या यह किसी शारीरिक काम के दौरान शुरू हुआ?' },
    },
  ],
};
