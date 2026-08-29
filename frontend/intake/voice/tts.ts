import type { Lang } from '../tree/types';
import { SPEECH_LANG, pickVoice } from './languages';

/**
 * speechSynthesis wrapper — browser-native, zero keys, immune to venue
 * wifi (Part 5 / Part 6 of the plan). One queue slot: a new `speak()`
 * cancels whatever is in flight rather than stacking utterances, since a
 * kiosk that talks over itself is worse than one that interrupts itself.
 */

let mutedRef = false;
let volumeRef = 1;

export function setTtsMuted(muted: boolean) {
  mutedRef = muted;
  if (muted) cancelSpeech();
}

export function setTtsVolume(v: number) {
  volumeRef = Math.max(0, Math.min(1, v));
}

export function cancelSpeech() {
  if (typeof window === 'undefined') return;
  window.speechSynthesis?.cancel();
}

export function ttsSupported(): boolean {
  return typeof window !== 'undefined' && 'speechSynthesis' in window;
}

/**
 * Speaks `text` in `lang`. Calls `onEnd` whether the utterance finished,
 * errored, or was skipped because TTS is muted/unsupported — callers
 * (Screen.tsx's speak -> arm -> listen cycle) must always get to the next
 * phase, never hang waiting for an event that won't fire.
 */
export function speak(text: string, lang: Lang, onEnd?: () => void): void {
  if (!ttsSupported() || mutedRef || !text) {
    onEnd?.();
    return;
  }
  cancelSpeech();

  const utter = new SpeechSynthesisUtterance(text);
  utter.lang = SPEECH_LANG[lang];
  utter.rate = 0.95;
  utter.volume = volumeRef;

  const voices = window.speechSynthesis.getVoices();
  const voice = pickVoice(lang, voices);
  if (voice) utter.voice = voice;

  let ended = false;
  const finish = () => {
    if (ended) return;
    ended = true;
    onEnd?.();
  };
  utter.onend = finish;
  utter.onerror = finish;

  // A hard ceiling on the whole utterance. speechSynthesis is not
  // reliable about firing onend — a cancelled, interrupted or
  // never-started utterance can leave the caller waiting forever, and the
  // caller here is the speak -> arm -> listen cycle, so a missed onend
  // means the microphone never opens for that question at all.
  const guard = setTimeout(finish, Math.min(2000 + text.length * 90, 15000));
  const finishOnce = () => {
    clearTimeout(guard);
    finish();
  };
  utter.onend = finishOnce;
  utter.onerror = finishOnce;

  // Voices sometimes load asynchronously on first use; if the list was
  // empty, retry once the browser reports voices are ready. The guard
  // above still applies, so a browser that never fires onvoiceschanged
  // cannot strand the caller.
  if (!voice && voices.length === 0 && 'onvoiceschanged' in window.speechSynthesis) {
    window.speechSynthesis.onvoiceschanged = () => {
      window.speechSynthesis.onvoiceschanged = null;
      const retryVoice = pickVoice(lang, window.speechSynthesis.getVoices());
      if (retryVoice) utter.voice = retryVoice;
      window.speechSynthesis.speak(utter);
    };
    return;
  }

  window.speechSynthesis.speak(utter);
}
