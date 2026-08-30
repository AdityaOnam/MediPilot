import type { Lang } from '../tree/types';

/** BCP-47 codes for both the recogniser and speechSynthesis. India (-IN)
 *  variants where the platform ships them; falls back to bare hi/en. */
export const RECOGNITION_LANG: Record<Lang, string> = {
  en: 'en-IN',
  hi: 'hi-IN',
};

export const SPEECH_LANG: Record<Lang, string> = {
  en: 'en-IN',
  hi: 'hi-IN',
};

/** Picks the best available voice for a language, preferring an -IN
 *  regional voice, falling back to any voice whose lang starts with the
 *  base code, and finally to the platform default. */
export function pickVoice(lang: Lang, voices: SpeechSynthesisVoice[]): SpeechSynthesisVoice | null {
  if (!voices.length) return null;
  const want = SPEECH_LANG[lang];
  const base = lang; // 'en' | 'hi'
  return (
    voices.find((v) => v.lang === want) ??
    voices.find((v) => v.lang.toLowerCase().startsWith(base)) ??
    null
  );
}
