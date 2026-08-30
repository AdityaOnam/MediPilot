import type { Branch } from '../types';

export const FEVER_BRANCH: Branch = {
  id: 'fever',
  label: { en: 'Fever', hi: 'बुखार' },
  questions: [
    {
      id: 'fv_duration',
      kind: 'choice',
      prompt: { en: 'How long have you had the fever?', hi: 'बुखार कब से है?' },
      options: [
        { value: 'today', label: { en: 'Since today', hi: 'आज से' } },
        { value: 'few_days', label: { en: 'A few days', hi: 'कुछ दिन से' } },
        { value: 'week_plus', label: { en: 'A week or more', hi: 'एक हफ्ते या ज्यादा से' } },
      ],
    },
    {
      id: 'fv_highest',
      kind: 'free_text',
      prompt: { en: 'How high has it been, if you checked?', hi: 'अगर आपने नापा है, तो सबसे ज्यादा कितना था?' },
    },
    {
      id: 'fv_rigors',
      kind: 'yes_no',
      prompt: { en: 'Have you had shivering or chills with it?', hi: 'क्या इसके साथ कंपकंपी या ठंड लगी है?' },
    },
    {
      id: 'fv_rash',
      kind: 'yes_no',
      prompt: { en: 'Any rash on the skin?', hi: 'क्या त्वचा पर कोई दाने हैं?' },
    },
    {
      // Meningism. Clinically important, but a stiff neck is NOT altered
      // consciousness — mapping it to that code would fire the interrupt
      // on the wrong grounds. It informs the nurse card instead.
      id: 'fv_stiff_neck',
      kind: 'yes_no',
      prompt: { en: 'Is your neck stiff, or does light bother your eyes?', hi: 'क्या गर्दन अकड़ी हुई है, या रोशनी से आंखों में तकलीफ है?' },
    },
    {
      id: 'fv_alert',
      kind: 'yes_no',
      prompt: {
        en: 'Are you fully awake and thinking clearly?',
        hi: 'क्या आप पूरी तरह होश में हैं और साफ सोच पा रहे हैं?',
      },
      observes: ['altered_consciousness'],
      observeOn: 'no',
    },
    {
      id: 'fv_poor_feeding',
      kind: 'yes_no',
      prompt: { en: 'Has the child stopped feeding, or become unusually floppy or hard to wake?', hi: 'क्या बच्चे ने दूध पीना बंद कर दिया है, या असामान्य रूप से ढीला या जगाना मुश्किल हो गया है?' },
      askIf: (s) => s.__stratum === 'neonate' || s.__stratum === 'infant' || s.__stratum === 'child',
      observes: ['infant_not_feeding_floppy_inconsolable'],
    },
  ],
};
