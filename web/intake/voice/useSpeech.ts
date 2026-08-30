'use client';

import { useCallback, useEffect, useRef, useState } from 'react';
import type { AnswerKind, Lang } from '../tree/types';
import { RECOGNITION_LANG } from './languages';
import { speak, cancelSpeech } from './tts';
import { createVad, type Vad } from './vad';

/* eslint-disable @typescript-eslint/no-explicit-any */
declare global {
  interface Window {
    SpeechRecognition: any;
    webkitSpeechRecognition: any;
  }
}

export type MicPhase = 'idle' | 'speaking' | 'arming' | 'listening' | 'settling' | 'matching';

/** Adaptive silence windows (Part 2 of the plan). A flat 5 s after "haan"
 *  reads as a crash, so the window follows the question, and 5 s is the
 *  ceiling rather than the default. */
export const SILENCE_MS: Record<AnswerKind, number> = {
  yes_no: 1500,
  choice: 2000,
  scale_0_10: 2000,
  number: 2000,
  free_text: 3000,
};

export const SILENCE_CEILING_MS = 5000;
const ARM_MS = 2000;
const SETTLE_MS = 300;
const ONSET_MS = 300;
const MAX_UTTERANCE_MS = 30_000;
const NO_SPEECH_MS = 12_000;
const POLL_MS = 50;

export interface UseSpeechArgs {
  /** Changing this restarts the whole cycle. Pass the question id. */
  turnKey: string;
  /** Read aloud at the start of the turn. The mic is hard-closed until
   *  this finishes — see the SPEAKING phase below. */
  spokenText: string;
  kind: AnswerKind;
  lang: Lang;
  /** False when the patient declined listening consent, or voice is off.
   *  The hook then does nothing at all — no getUserMedia, no permission
   *  prompt, and the typed path is untouched. */
  enabled: boolean;
  onTranscript: (text: string) => void;
  /** Nothing heard for NO_SPEECH_MS. The caller re-prompts once, then
   *  surfaces the keyboard. */
  onNoSpeech?: () => void;
  /** Fired alongside onTranscript with what the utterance sounded like
   *  rather than what it said. See SpeechMetrics. */
  onMetrics?: (m: SpeechMetrics) => void;
}

/**
 * Observable properties of HOW the patient spoke, measured from the VAD
 * we are already running for silence detection — no extra cost.
 *
 * `fragmented` is the interesting one: a patient who cannot get six words
 * out without stopping for breath is producing a respiratory-effort
 * finding that a stated respiratory rate can miss entirely.
 *
 * It is an OBSERVATION FOR THE NURSE, never an automatic red flag. It is
 * noisy — a nervous patient stammers, a thoughtful one pauses — so it is
 * recorded and shown, and nothing downstream escalates on it alone.
 */
export interface SpeechMetrics {
  /** Voiced stretches separated by pauses within one answer. */
  segments: number;
  /** Longest uninterrupted stretch of speech, ms. */
  longestRunMs: number;
  /** Total time from first word to last, ms. */
  spanMs: number;
  /** Many short bursts with gaps, over an answer long enough to judge. */
  fragmented: boolean;
}

/** Gap that ends a voiced segment for fragmentation purposes — shorter
 *  than any silence window, so it counts pauses WITHIN an answer. */
const SEGMENT_GAP_MS = 400;
/** Below this, a run is a fragment rather than a phrase. */
const SHORT_RUN_MS = 1500;
/** Do not judge an answer too short to have a shape. */
const MIN_SPAN_FOR_JUDGEMENT_MS = 2500;
const MIN_SEGMENTS_FOR_JUDGEMENT = 3;

export interface UseSpeechReturn {
  phase: MicPhase;
  /** 0..1 RMS, drives the orb. */
  level: number;
  /** Live text as the patient speaks. Display-only until committed. */
  interim: string;
  supported: boolean;
  error: string | null;
  /** Patient tapped to skip the reading — jump straight to listening. */
  skip: () => void;
  /** Re-open the mic for the SAME question after an answer that could not
   *  be matched. Without this a turn was one-shot: commit() latches
   *  committedRef and beginListening() refuses to run again, so a single
   *  mis-hear left the mic dead until the question changed. */
  retry: () => void;
  /** Patient pressed stop, or started typing. Latches the mic off for
   *  this turn; nothing re-opens it until the next question. */
  stop: () => void;
}

export function useSpeech(args: UseSpeechArgs): UseSpeechReturn {
  const { turnKey, spokenText, kind, lang, enabled, onTranscript, onNoSpeech, onMetrics } = args;

  const [phase, setPhase] = useState<MicPhase>('idle');
  const [level, setLevel] = useState(0);
  const [interim, setInterim] = useState('');
  const [error, setError] = useState<string | null>(null);

  const supported =
    typeof window !== 'undefined' && !!(window.SpeechRecognition || window.webkitSpeechRecognition);

  // --- long-lived, survives turns -----------------------------------------
  const streamRef = useRef<MediaStream | null>(null);
  const vadRef = useRef<Vad | null>(null);
  const recRef = useRef<any>(null);

  // --- per-turn state ------------------------------------------------------
  const phaseRef = useRef<MicPhase>('idle');
  const gateRef = useRef(0.02);
  const finalRef = useRef('');
  const interimRef = useRef('');
  const listenStartRef = useRef(0);
  const lastVoicedRef = useRef(0);
  const voicedRunRef = useRef(0);
  const hasOnsetRef = useRef(false);
  const settleFromRef = useRef(0);
  const abandonedRef = useRef(false); // patient stopped it themselves
  const committedRef = useRef(false);

  const timersRef = useRef<ReturnType<typeof setTimeout>[]>([]);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  // Latest callbacks without re-running the turn effect on every render.
  const onTranscriptRef = useRef(onTranscript);
  const onNoSpeechRef = useRef(onNoSpeech);
  const onMetricsRef = useRef(onMetrics);
  onTranscriptRef.current = onTranscript;
  onNoSpeechRef.current = onNoSpeech;
  onMetricsRef.current = onMetrics;

  // Speech-shape accumulators, reset per turn.
  const firstVoicedRef = useRef(0);
  const segmentsRef = useRef(0);
  const longestRunRef = useRef(0);
  const inSegmentRef = useRef(false);
  const segmentStartRef = useRef(0);

  const silenceMs = Math.min(SILENCE_MS[kind] ?? 3000, SILENCE_CEILING_MS);

  const setPhaseBoth = useCallback((p: MicPhase) => {
    phaseRef.current = p;
    setPhase(p);
  }, []);

  const clearTimers = useCallback(() => {
    timersRef.current.forEach(clearTimeout);
    timersRef.current = [];
    if (pollRef.current) {
      clearInterval(pollRef.current);
      pollRef.current = null;
    }
  }, []);

  const later = useCallback((fn: () => void, ms: number) => {
    timersRef.current.push(setTimeout(fn, ms));
  }, []);

  /** Hard close: abort the recogniser outright. Chrome's
   *  webkitSpeechRecognition opens its OWN capture and ignores our
   *  MediaStream, so muting a track does nothing to it — this is the only
   *  thing that stops the kiosk hearing its own prompt and answering
   *  itself. */
  const stopRecognition = useCallback(() => {
    const rec = recRef.current;
    if (!rec) return;
    try {
      rec.onend = null;
      rec.onresult = null;
      rec.onerror = null;
      rec.abort();
    } catch {
      // already stopped
    }
    recRef.current = null;
  }, []);

  const commit = useCallback(() => {
    if (committedRef.current) return;
    committedRef.current = true;
    clearTimers();
    stopRecognition();

    // Close any open segment so its length counts.
    if (inSegmentRef.current) {
      const run = lastVoicedRef.current - segmentStartRef.current;
      if (run > longestRunRef.current) longestRunRef.current = run;
      inSegmentRef.current = false;
    }

    const spanMs = firstVoicedRef.current ? lastVoicedRef.current - firstVoicedRef.current : 0;
    const metrics: SpeechMetrics = {
      segments: segmentsRef.current,
      longestRunMs: longestRunRef.current,
      spanMs,
      fragmented:
        spanMs >= MIN_SPAN_FOR_JUDGEMENT_MS &&
        segmentsRef.current >= MIN_SEGMENTS_FOR_JUDGEMENT &&
        longestRunRef.current < SHORT_RUN_MS,
    };

    const text = (finalRef.current + ' ' + interimRef.current).trim();
    setPhaseBoth('matching');
    onMetricsRef.current?.(metrics);
    onTranscriptRef.current(text);
  }, [clearTimers, stopRecognition, setPhaseBoth]);

  const startRecognition = useCallback(() => {
    if (!supported) return;
    const Ctor = window.SpeechRecognition || window.webkitSpeechRecognition;
    const rec = new Ctor();
    rec.lang = RECOGNITION_LANG[lang];
    rec.continuous = true;
    rec.interimResults = true;
    rec.maxAlternatives = 1;

    rec.onresult = (e: any) => {
      let live = '';
      for (let i = e.resultIndex; i < e.results.length; i++) {
        const r = e.results[i];
        if (r.isFinal) finalRef.current += r[0].transcript + ' ';
        else live += r[0].transcript;
      }
      interimRef.current = live;
      setInterim((finalRef.current + ' ' + live).trim());
      // A recognised word is proof of speech even if RMS was borderline.
      hasOnsetRef.current = true;
      lastVoicedRef.current = Date.now();
    };

    rec.onerror = (e: any) => {
      // 'no-speech' is Chrome's own silence timeout; our VAD owns that
      // decision, so it is not an error condition here.
      if (e?.error === 'no-speech' || e?.error === 'aborted') return;
      if (e?.error === 'not-allowed' || e?.error === 'service-not-allowed') {
        setError('mic-denied');
        abandonedRef.current = true;
        setPhaseBoth('idle');
      }
    };

    rec.onend = () => {
      // Chrome ends sessions on its own schedule. While we are still
      // meant to be listening, restart — otherwise a patient pausing
      // mid-sentence silently loses the rest of their answer.
      if (phaseRef.current === 'listening' && !abandonedRef.current && !committedRef.current) {
        try {
          rec.start();
        } catch {
          // start() throws if it is already starting; harmless.
        }
      }
    };

    recRef.current = rec;
    try {
      rec.start();
    } catch {
      // Already started — Chrome throws on a double start().
    }
  }, [supported, lang, setPhaseBoth]);

  const beginListening = useCallback(() => {
    if (abandonedRef.current || committedRef.current) return;
    setPhaseBoth('listening');
    listenStartRef.current = Date.now();
    lastVoicedRef.current = Date.now();
    voicedRunRef.current = 0;
    hasOnsetRef.current = false;
    startRecognition();

    pollRef.current = setInterval(() => {
      const vad = vadRef.current;
      const now = Date.now();
      const lvl = vad ? vad.level() : 0;
      setLevel(lvl);

      if (lvl > gateRef.current) {
        voicedRunRef.current += POLL_MS;
        // Opening a new voiced segment: either the first of the answer, or
        // one following a gap long enough to count as a pause.
        if (!inSegmentRef.current && now - lastVoicedRef.current >= SEGMENT_GAP_MS) {
          inSegmentRef.current = true;
          segmentStartRef.current = now;
          segmentsRef.current += 1;
        } else if (!inSegmentRef.current && !firstVoicedRef.current) {
          inSegmentRef.current = true;
          segmentStartRef.current = now;
          segmentsRef.current += 1;
        }
        if (!firstVoicedRef.current) firstVoicedRef.current = now;
        lastVoicedRef.current = now;
        if (voicedRunRef.current >= ONSET_MS) hasOnsetRef.current = true;
      } else {
        voicedRunRef.current = 0;
        // Close the segment once the gap is long enough to be a pause.
        if (inSegmentRef.current && now - lastVoicedRef.current >= SEGMENT_GAP_MS) {
          const run = lastVoicedRef.current - segmentStartRef.current;
          if (run > longestRunRef.current) longestRunRef.current = run;
          inSegmentRef.current = false;
        }
      }

      // Nothing has been said yet: no silence timer runs at all, so a
      // patient who thinks for eight seconds is never cut off.
      if (!hasOnsetRef.current) {
        if (now - listenStartRef.current >= NO_SPEECH_MS) {
          clearTimers();
          stopRecognition();
          setPhaseBoth('idle');
          onNoSpeechRef.current?.();
        }
        return;
      }

      if (phaseRef.current === 'settling') {
        // New speech during the grace period puts us back to listening.
        if (lastVoicedRef.current > settleFromRef.current) setPhaseBoth('listening');
        return;
      }

      if (now - lastVoicedRef.current >= silenceMs) {
        settleFromRef.current = now;
        setPhaseBoth('settling');
        later(() => {
          if (lastVoicedRef.current > settleFromRef.current) {
            setPhaseBoth('listening');
          } else {
            commit();
          }
        }, SETTLE_MS);
        return;
      }

      if (now - listenStartRef.current >= MAX_UTTERANCE_MS) commit();
    }, POLL_MS);
  }, [setPhaseBoth, startRecognition, clearTimers, stopRecognition, silenceMs, later, commit]);

  const arm = useCallback(async () => {
    if (abandonedRef.current) return;
    setPhaseBoth('arming');

    // Calibrate against the room while the patient registers the question.
    const vad = vadRef.current;
    if (vad) {
      const gate = await vad.calibrate(ARM_MS);
      gateRef.current = gate;
      if (!abandonedRef.current && phaseRef.current === 'arming') beginListening();
      return;
    }
    later(() => {
      if (!abandonedRef.current && phaseRef.current === 'arming') beginListening();
    }, ARM_MS);
  }, [setPhaseBoth, beginListening, later]);

  const skip = useCallback(() => {
    if (!enabled || abandonedRef.current) return;
    cancelSpeech();
    clearTimers();
    if (phaseRef.current === 'speaking' || phaseRef.current === 'arming') beginListening();
  }, [enabled, clearTimers, beginListening]);

  /**
   * Listen again for the same question.
   *
   * Resets only the per-utterance accumulators — the acquired stream, the
   * VAD and the calibrated noise gate are kept, so a retry re-opens the
   * mic immediately instead of paying the 2 s arming window again. The
   * prompt is NOT re-read: the patient just heard it, and repeating it in
   * full is what makes a kiosk feel broken.
   */
  const retry = useCallback(() => {
    if (!enabled || abandonedRef.current) return;
    clearTimers();
    stopRecognition();
    cancelSpeech();
    committedRef.current = false;
    finalRef.current = '';
    interimRef.current = '';
    setInterim('');
    hasOnsetRef.current = false;
    firstVoicedRef.current = 0;
    segmentsRef.current = 0;
    longestRunRef.current = 0;
    inSegmentRef.current = false;
    setLevel(0);
    beginListening();
  }, [enabled, clearTimers, stopRecognition, beginListening]);

  const stop = useCallback(() => {
    abandonedRef.current = true;
    clearTimers();
    stopRecognition();
    cancelSpeech();
    setLevel(0);
    setPhaseBoth('idle');
  }, [clearTimers, stopRecognition, setPhaseBoth]);

  // --- the turn ------------------------------------------------------------
  useEffect(() => {
    if (!enabled) {
      setPhaseBoth('idle');
      return;
    }

    let cancelled = false;

    // Reset per-turn state.
    clearTimers();
    stopRecognition();
    finalRef.current = '';
    interimRef.current = '';
    setInterim('');
    abandonedRef.current = false;
    committedRef.current = false;
    hasOnsetRef.current = false;
    firstVoicedRef.current = 0;
    segmentsRef.current = 0;
    longestRunRef.current = 0;
    inSegmentRef.current = false;
    setLevel(0);

    async function run() {
      // Acquire the metering stream once, lazily, so the permission
      // prompt lands on the first real question rather than on page load.
      if (!streamRef.current) {
        try {
          streamRef.current = await navigator.mediaDevices.getUserMedia({ audio: true });
        } catch {
          setError('mic-denied');
          return; // typed path still works; this is not fatal
        }
      }
      if (!vadRef.current && streamRef.current) {
        try {
          vadRef.current = await createVad(streamRef.current);
        } catch {
          vadRef.current = null; // fall back to a plain 2 s arm
        }
      }
      if (cancelled) return;

      setPhaseBoth('speaking');
      speak(spokenText, lang, () => {
        if (cancelled || abandonedRef.current) return;
        void arm();
      });
    }

    void run();

    return () => {
      cancelled = true;
      clearTimers();
      stopRecognition();
      cancelSpeech();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [turnKey, enabled]);

  // Release the microphone when intake leaves the conversation entirely.
  useEffect(() => {
    return () => {
      clearTimers();
      stopRecognition();
      vadRef.current?.detach();
      vadRef.current = null;
      streamRef.current?.getTracks().forEach((t) => t.stop());
      streamRef.current = null;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return { phase, level, interim, supported, error, skip, retry, stop };
}
