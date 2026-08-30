import type { Branch } from '../types';

/** Vomiting / diarrhoea, framed around fluid loss — distinct from
 *  abdominal.ts, which is framed around pain. */
export const GI_BRANCH: Branch = {
  id: 'gi',
  label: { en: 'Vomiting or diarrhoea', hi: 'उल्टी या दस्त' },
  questions: [
    {
      id: 'gi_which',
      kind: 'choice',
      prompt: { en: 'Is it vomiting, diarrhoea, or both?', hi: 'उल्टी है, दस्त है, या दोनों?' },
      options: [
        { value: 'vomit', label: { en: 'Vomiting', hi: 'उल्टी' } },
        { value: 'diarrhea', label: { en: 'Diarrhoea', hi: 'दस्त' } },
        { value: 'both', label: { en: 'Both', hi: 'दोनों' } },
      ],
      synonyms: {
        vomit: ['throwing up', 'ulti', 'उल्टी', 'vomits'],
        diarrhea: ['loose motion', 'loose motions', 'dast', 'दस्त', 'loose stool'],
        both: ['dono', 'दोनों', 'everything'],
      },
    },
    {
      id: 'gi_frequency',
      kind: 'free_text',
      prompt: { en: 'How many times has it happened today?', hi: 'आज कितनी बार हुआ है?' },
    },
    {
      id: 'gi_blood',
      kind: 'yes_no',
      prompt: { en: 'Is there any blood in it?', hi: 'क्या उसमें खून है?' },
      observes: ['uncontrolled_bleeding_or_penetrating_injury'],
    },
    {
      // Positively phrased — NO means they cannot rehydrate orally, which
      // is the answer that changes the disposition. Not one of the eight
      // codes, so it informs rather than interrupts.
      id: 'gi_keep_fluids',
      kind: 'yes_no',
      prompt: { en: 'Can you keep water or fluids down?', hi: 'क्या आप पानी या तरल पदार्थ पेट में रोक पा रहे हैं?' },
    },
    {
      id: 'gi_urinating',
      kind: 'yes_no',
      prompt: { en: 'Are you passing urine as usual?', hi: 'क्या आप सामान्य रूप से पेशाब कर पा रहे हैं?' },
    },
  ],
};
