import type { Branch } from '../types';

/**
 * Deliberately gentle phrasing, and deliberately short. A kiosk is not
 * the place for a full risk assessment — the job here is to find out
 * whether this person should be sitting in a waiting room at all, and to
 * get them to a human if not.
 */
export const MENTAL_BRANCH: Branch = {
  id: 'mental_behavioural',
  label: { en: 'How you are feeling', hi: 'आप कैसा महसूस कर रहे हैं' },
  questions: [
    {
      id: 'mh_what_changed',
      kind: 'free_text',
      prompt: { en: 'Can you tell me what has been happening?', hi: 'क्या आप बता सकते हैं कि क्या हो रहा है?' },
    },
    {
      // No code in config/red_flags.yaml covers self-harm risk, so this
      // uses `urgentOn` instead: it calls a person immediately WITHOUT
      // fabricating a physiological red flag the band engine cannot
      // substantiate. See engine.ts submitAnswer.
      id: 'mh_safety',
      kind: 'yes_no',
      prompt: {
        en: 'Have you had thoughts of harming yourself?',
        hi: 'क्या आपके मन में खुद को नुकसान पहुंचाने के विचार आए हैं?',
      },
      urgentOn: 'yes',
    },
    {
      id: 'mh_substances',
      kind: 'yes_no',
      prompt: {
        en: 'Have you taken any alcohol or drugs today?',
        hi: 'क्या आपने आज शराब या कोई नशा लिया है?',
      },
    },
    {
      id: 'mh_sleeping_eating',
      kind: 'yes_no',
      prompt: {
        en: 'Have you been able to sleep and eat in the last few days?',
        hi: 'क्या पिछले कुछ दिनों में आप सो और खा पा रहे हैं?',
      },
    },
    {
      id: 'mh_someone_with',
      kind: 'yes_no',
      prompt: {
        en: 'Is there someone who can stay with you right now?',
        hi: 'क्या अभी कोई आपके साथ रह सकता है?',
      },
    },
  ],
};
