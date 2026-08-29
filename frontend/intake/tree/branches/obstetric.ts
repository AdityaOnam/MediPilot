import type { Branch } from '../types';

export const OBSTETRIC_BRANCH: Branch = {
  id: 'obstetric',
  label: { en: 'Pregnancy-related', hi: 'गर्भावस्था संबंधी' },
  questions: [
    {
      id: 'ob_weeks',
      kind: 'free_text',
      prompt: { en: 'How many weeks or months pregnant are you?', hi: 'आप कितने हफ्ते या महीने की गर्भवती हैं?' },
    },
    {
      id: 'ob_contractions',
      kind: 'yes_no',
      prompt: {
        en: 'Are you having regular tightening or contractions?',
        hi: 'क्या आपको नियमित रूप से पेट में कसाव या संकुचन हो रहा है?',
      },
      observes: ['active_labour_or_bleeding_pregnancy'],
    },
    {
      id: 'ob_bleeding',
      kind: 'yes_no',
      prompt: { en: 'Is there any bleeding?', hi: 'क्या कोई रक्तस्राव हो रहा है?' },
      observes: ['active_labour_or_bleeding_pregnancy'],
    },
    {
      id: 'ob_waters',
      kind: 'yes_no',
      prompt: { en: 'Have your waters broken?', hi: 'क्या आपका पानी टूट गया है?' },
      observes: ['active_labour_or_bleeding_pregnancy'],
    },
    {
      // Positively phrased. Reduced fetal movement is serious but is not
      // one of the eight codes, so it informs the nurse card only.
      id: 'ob_movement',
      kind: 'yes_no',
      prompt: { en: 'Have you felt the baby move today?', hi: 'क्या आपने आज बच्चे की हलचल महसूस की है?' },
    },
    {
      // Pre-eclampsia screen. Also not one of the eight codes.
      id: 'ob_headache_vision',
      kind: 'yes_no',
      prompt: {
        en: 'Do you have a bad headache, blurred vision, or swelling of the hands and face?',
        hi: 'क्या आपको तेज सिरदर्द, धुंधला दिखना, या हाथ और चेहरे पर सूजन है?',
      },
    },
  ],
};
