import type { Branch } from '../types';

export const NEURO_BRANCH: Branch = {
  id: 'neuro',
  label: { en: 'Neurological', hi: 'तंत्रिका संबंधी' },
  questions: [
    {
      // Onset is first because the thrombolysis window is measured from
      // it, and it is the one answer that changes what happens next.
      id: 'nr_onset',
      kind: 'choice',
      prompt: { en: 'When did this start?', hi: 'यह कब शुरू हुआ?' },
      options: [
        { value: 'just_now', label: { en: 'Just now', hi: 'अभी अभी' } },
        { value: 'within_hour', label: { en: 'Within the last hour', hi: 'पिछले एक घंटे में' } },
        { value: 'few_hours', label: { en: 'A few hours ago', hi: 'कुछ घंटे पहले' } },
        { value: 'today_or_more', label: { en: 'Yesterday or earlier', hi: 'कल या उससे पहले' } },
      ],
      synonyms: {
        just_now: ['right now', 'abhi', 'अभी', 'achanak'],
        within_hour: ['an hour ago', 'ek ghante', 'एक घंटे पहले'],
        few_hours: ['this morning', 'kuch ghante', 'कुछ घंटे'],
        today_or_more: ['yesterday', 'kal', 'कल', 'days ago'],
      },
    },
    {
      id: 'nr_weakness_side',
      kind: 'yes_no',
      prompt: {
        en: 'Is one side of your body weak, or does your face feel different on one side?',
        hi: 'क्या शरीर का एक हिस्सा कमजोर है, या चेहरा एक तरफ अलग महसूस हो रहा है?',
      },
      observes: ['sudden_onesided_weakness_facial_droop_speech_change'],
    },
    {
      id: 'nr_speech_change',
      kind: 'yes_no',
      prompt: { en: 'Has your speech become slurred or hard to get out?', hi: 'क्या आपकी बोली लड़खड़ा रही है या बोलने में कठिनाई हो रही है?' },
      observes: ['sudden_onesided_weakness_facial_droop_speech_change'],
    },
    {
      id: 'nr_alert',
      kind: 'yes_no',
      prompt: {
        en: 'Are you fully awake and aware of where you are?',
        hi: 'क्या आप पूरी तरह होश में हैं और जानते हैं कि आप कहां हैं?',
      },
      observes: ['altered_consciousness'],
      observeOn: 'no',
    },
    {
      id: 'nr_seizure',
      kind: 'yes_no',
      prompt: { en: 'Did you have a fit or seizure?', hi: 'क्या आपको दौरा पड़ा?' },
      observes: ['altered_consciousness'],
    },
    {
      // Thunderclap headache. Clinically important, but not one of the
      // eight codes — it informs the nurse card, it does not interrupt.
      id: 'nr_worst_headache',
      kind: 'yes_no',
      prompt: {
        en: 'Is this the worst headache you have ever had?',
        hi: 'क्या यह अब तक का सबसे तेज सिरदर्द है?',
      },
    },
  ],
};
