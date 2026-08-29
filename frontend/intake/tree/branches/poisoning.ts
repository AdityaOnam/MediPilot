import type { Branch } from '../types';

export const POISONING_BRANCH: Branch = {
  id: 'poisoning',
  label: { en: 'Poisoning or bite', hi: 'जहर या डंक' },
  questions: [
    {
      // Explicit confirmation rather than trusting the branch itself.
      // Classification is a routing guess; this is the answer that
      // actually establishes the observation.
      id: 'po_confirm',
      kind: 'yes_no',
      prompt: {
        en: 'Did you swallow something harmful, take too much medicine, or get bitten or stung?',
        hi: 'क्या आपने कुछ हानिकारक निगला, ज्यादा दवा ली, या आपको काटा या डंक मारा गया?',
      },
      observes: ['poisoning_overdose_or_snakebite'],
    },
    {
      id: 'po_what',
      kind: 'free_text',
      prompt: { en: 'What was it? Name it if you can.', hi: 'वह क्या था? अगर बता सकें तो नाम बताइए।' },
    },
    {
      id: 'po_when',
      kind: 'choice',
      prompt: { en: 'How long ago?', hi: 'कितनी देर पहले?' },
      options: [
        { value: 'just_now', label: { en: 'Just now', hi: 'अभी अभी' } },
        { value: 'within_hour', label: { en: 'Within the last hour', hi: 'पिछले एक घंटे में' } },
        { value: 'longer', label: { en: 'Longer ago', hi: 'उससे ज्यादा पहले' } },
      ],
      synonyms: {
        just_now: ['minutes ago', 'abhi', 'अभी'],
        within_hour: ['an hour', 'ek ghanta', 'एक घंटा'],
        longer: ['hours ago', 'kai ghante', 'कई घंटे', 'yesterday'],
      },
    },
    {
      id: 'po_amount',
      kind: 'free_text',
      prompt: {
        en: 'How much was taken, if you know? Bring the packet if you have it.',
        hi: 'अगर पता हो तो कितनी मात्रा थी? अगर डिब्बा है तो साथ लाइए।',
      },
    },
    {
      id: 'po_feeling_now',
      kind: 'yes_no',
      prompt: { en: 'Are you feeling unwell right now?', hi: 'क्या आपको अभी तबीयत खराब लग रही है?' },
    },
  ],
};
