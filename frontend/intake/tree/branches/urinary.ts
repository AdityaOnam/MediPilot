import type { Branch } from '../types';

export const URINARY_BRANCH: Branch = {
  id: 'urinary',
  label: { en: 'Urinary', hi: 'पेशाब संबंधी' },
  questions: [
    {
      id: 'ur_symptom',
      kind: 'choice',
      prompt: { en: 'What are you noticing?', hi: 'आपको क्या महसूस हो रहा है?' },
      options: [
        { value: 'burning', label: { en: 'Burning when passing urine', hi: 'पेशाब करते समय जलन' } },
        { value: 'blood', label: { en: 'Blood in the urine', hi: 'पेशाब में खून' } },
        { value: 'cant_pass', label: { en: 'Cannot pass urine at all', hi: 'बिलकुल पेशाब नहीं हो रहा' } },
        { value: 'frequent', label: { en: 'Going very often', hi: 'बार बार जाना' } },
      ],
      synonyms: {
        burning: ['stinging', 'jalan', 'जलन', 'pain when peeing'],
        blood: ['red urine', 'khoon', 'खून'],
        cant_pass: ['nothing comes', 'blocked', 'ruka hua', 'रुका हुआ', 'retention'],
        frequent: ['every few minutes', 'baar baar', 'बार बार'],
      },
      // No red-flag code here: blood in urine is NOT "uncontrolled bleeding
      // or penetrating injury", and mapping it to that code would fire the
      // interrupt on a routine UTI. It informs the model, not the alarm.
    },
    {
      id: 'ur_duration',
      kind: 'choice',
      prompt: { en: 'How long has this been going on?', hi: 'यह कब से हो रहा है?' },
      options: [
        { value: 'today', label: { en: 'Since today', hi: 'आज से' } },
        { value: 'few_days', label: { en: 'A few days', hi: 'कुछ दिन से' } },
        { value: 'weeks', label: { en: 'Weeks or longer', hi: 'हफ्तों या ज्यादा से' } },
      ],
    },
    {
      id: 'ur_flank_pain',
      kind: 'yes_no',
      prompt: { en: 'Any pain in your side or lower back?', hi: 'क्या बगल या पीठ के निचले हिस्से में दर्द है?' },
    },
    {
      id: 'ur_fever',
      kind: 'yes_no',
      prompt: { en: 'Do you also have a fever or chills?', hi: 'क्या आपको बुखार या ठंड भी लग रही है?' },
    },
    {
      id: 'ur_pregnant_or_catheter',
      kind: 'yes_no',
      prompt: {
        en: 'Are you pregnant, or do you have a urinary catheter?',
        hi: 'क्या आप गर्भवती हैं, या आपको पेशाब की नली लगी है?',
      },
    },
    {
      // Urosepsis. Most urinary presentations are genuinely low acuity,
      // which is exactly why this branch needs a route to a nurse: an
      // older patient whose urine infection presents as new confusion is
      // the atypical-sepsis case that gets missed, and without this the
      // branch had no path to the alarm at all.
      id: 'ur_alert',
      kind: 'yes_no',
      prompt: {
        en: 'Are you fully awake and thinking clearly?',
        hi: 'क्या आप पूरी तरह होश में हैं और साफ सोच पा रहे हैं?',
      },
      observes: ['altered_consciousness'],
      observeOn: 'no',
    },
  ],
};
