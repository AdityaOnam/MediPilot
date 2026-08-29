import type { Question } from './types';

/**
 * Asked once, after any branch, each gated by `askIf`. `engine.ts` also
 * drops any of these outright if the patient already volunteered the
 * answer in free text (see engine.ts `applyObservedFields`).
 */
export const TAIL_QUESTIONS: Question[] = [
  {
    id: 'pain_score',
    kind: 'scale_0_10',
    prompt: {
      en: 'On a scale of 0 to 10, how bad is the pain right now?',
      hi: '0 से 10 के बीच, अभी दर्द कितना है?',
    },
    // Pre-verbal strata (neonate, infant) can't self-report a 0-10 score.
    askIf: (s) => s.__stratum !== 'neonate' && s.__stratum !== 'infant',
  },
  {
    id: 'duration',
    kind: 'choice',
    prompt: { en: 'When did this start?', hi: 'यह कब शुरू हुआ?' },
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
    askIf: (s) => !s['duration'] && !s['onset'],
  },
  {
    id: 'meds_taken',
    kind: 'free_text',
    prompt: { en: 'Have you taken any medicine for this? Which one?', hi: 'क्या आपने इसके लिए कोई दवा ली है? कौन सी?' },
  },
  {
    id: 'allergies',
    kind: 'free_text',
    prompt: { en: 'Are you allergic to any medicine?', hi: 'क्या आपको किसी दवा से एलर्जी है?' },
  },
  {
    id: 'prior_episode',
    kind: 'yes_no',
    prompt: { en: 'Has this happened to you before?', hi: 'क्या पहले भी आपके साथ ऐसा हुआ है?' },
  },
  {
    id: 'can_walk',
    kind: 'yes_no',
    prompt: { en: 'Are you able to walk right now?', hi: 'क्या आप अभी चल सकते हैं?' },
  },
  {
    id: 'pregnancy',
    kind: 'yes_no',
    prompt: { en: 'Is there any chance you are pregnant?', hi: 'क्या कोई संभावना है कि आप गर्भवती हैं?' },
    askIf: (s) => s.__sex === 'F' && (s.__stratum === 'adolescent' || s.__stratum === 'adult'),
  },
];
