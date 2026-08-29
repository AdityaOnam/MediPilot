import type { Branch } from '../types';

/**
 * Forced when the stratum is neonate/infant/child AND the complaint is
 * non-specific (see engine.ts branch selection). A floppy, not-feeding
 * infant needs different questions than an adult who used the same words
 * on the form — and the answers here are the ones whose absence is
 * dangerous, so several are phrased positively with `observeOn: 'no'`.
 */
export const PAEDS_GENERAL_BRANCH: Branch = {
  id: 'paeds_general',
  label: { en: 'Child, general', hi: 'बच्चा, सामान्य' },
  questions: [
    {
      id: 'pg_feeding',
      kind: 'yes_no',
      prompt: { en: 'Is the child feeding or drinking normally?', hi: 'क्या बच्चा सामान्य रूप से दूध या पानी ले रहा है?' },
      observes: ['infant_not_feeding_floppy_inconsolable'],
      observeOn: 'no',
    },
    {
      id: 'pg_alert',
      kind: 'yes_no',
      prompt: {
        en: 'Is the child awake and responding to you as usual?',
        hi: 'क्या बच्चा जाग रहा है और सामान्य रूप से प्रतिक्रिया दे रहा है?',
      },
      observes: ['altered_consciousness', 'infant_not_feeding_floppy_inconsolable'],
      observeOn: 'no',
    },
    {
      id: 'pg_breathing_effort',
      kind: 'yes_no',
      prompt: {
        en: 'Is the child working hard to breathe — chest pulling in, or grunting?',
        hi: 'क्या बच्चे को सांस लेने में मेहनत करनी पड़ रही है — छाती अंदर धंसना, या कराहना?',
      },
      observes: ['difficulty_speaking_full_sentences'],
    },
    {
      id: 'pg_consolable',
      kind: 'yes_no',
      prompt: {
        en: 'Can the child be comforted when you hold them?',
        hi: 'क्या गोद में लेने पर बच्चा चुप हो जाता है?',
      },
      observes: ['infant_not_feeding_floppy_inconsolable'],
      observeOn: 'no',
    },
    {
      id: 'pg_wet_nappies',
      kind: 'choice',
      prompt: { en: 'How much has the child passed urine today?', hi: 'आज बच्चे ने कितनी बार पेशाब किया है?' },
      options: [
        { value: 'normal', label: { en: 'As usual', hi: 'सामान्य रूप से' } },
        { value: 'fewer', label: { en: 'Less than usual', hi: 'सामान्य से कम' } },
        { value: 'none', label: { en: 'Not at all', hi: 'बिलकुल नहीं' } },
      ],
      synonyms: {
        normal: ['same as always', 'normal', 'सामान्य', 'roz jaisa'],
        fewer: ['less', 'kam', 'कम'],
        none: ['nothing', 'bilkul nahi', 'बिलकुल नहीं', 'dry'],
      },
    },
    {
      // Non-blanching rash. Serious, but not one of the eight codes.
      id: 'pg_rash',
      kind: 'yes_no',
      prompt: {
        en: 'Is there a rash that does not fade when you press a glass on it?',
        hi: 'क्या ऐसे दाने हैं जो कांच दबाने पर हल्के नहीं होते?',
      },
    },
  ],
};
