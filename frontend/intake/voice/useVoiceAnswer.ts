'use client';

import { useCallback, useEffect, useRef, useState } from 'react';
import type { Lang, Question } from '../tree/types';
import { STR, t } from '../strings';
import { matchAnswer } from '../match';
import { useSpeech } from './useSpeech';
import { buildSpokenPrompt } from './answerMode';

/**
 * The speak -> listen -> match -> auto-submit cycle for a single, simple
 * question — the same mechanics Conversation.tsx runs for the tree, pulled
 * out so Companion/HumanOffer/Basics can drive one voice question each
 * without re-implementing the failure-count and settle-timer bookkeeping.
 *
 * Conversation.tsx keeps its own copy rather than adopting this hook: it
 * also has to run the red-flag scan and the branch classifier on every
 * free-text answer, which a plain yes/no or choice question here never
 * needs.
 */
export function useVoiceAnswer({
  question,
  lang,
  enabled,
  onAnswer,
}: {
  question: Question;
  lang: Lang;
  /** False before listening consent is granted, or while muted. */
  enabled: boolean;
  onAnswer: (value: string) => void;
}) {
  const [hint, setHint] = useState<string | null>(null);
  const [picked, setPicked] = useState<string | null>(null);
  const failuresRef = useRef(0);
  const submitTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const retryTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const submit = useCallback(
    (value: string) => {
      if (submitTimerRef.current) clearTimeout(submitTimerRef.current);
      if (retryTimerRef.current) clearTimeout(retryTimerRef.current);
      setHint(null);
      setPicked(null);
      failuresRef.current = 0;
      onAnswer(value);
    },
    [onAnswer],
  );

  /**
   * A turn is not one-shot. After an answer that could not be matched the
   * mic re-opens for the same question, twice, before falling back to
   * "please pick below" and leaving it to the touchscreen.
   *
   * Without this a single mis-hear ended voice for that question — the
   * hint appeared and the microphone simply never listened again. It bit
   * numeric answers hardest, because a bare "72" or "seven" is the
   * easiest thing for a recogniser to drop.
   */
  const MAX_RETRIES = 2;
  const retryRef = useRef<(() => void) | null>(null);

  const failAndRetry = useCallback(() => {
    failuresRef.current += 1;
    const exhausted = failuresRef.current > MAX_RETRIES;
    setHint(exhausted ? t(lang, STR.pleasePickBelow) : t(lang, STR.didntCatch));
    if (!exhausted) {
      // Let the hint paint before the mic re-opens, so the patient sees
      // that they were not understood rather than being cut off silently.
      retryTimerRef.current = setTimeout(() => retryRef.current?.(), 500);
    }
  }, [lang]);

  const handleTranscript = useCallback(
    async (text: string) => {
      if (!text.trim()) {
        failAndRetry();
        return;
      }
      const verdict = await matchAnswer(text, question, undefined, lang);
      if (verdict.value !== null) {
        setPicked(verdict.value);
        submitTimerRef.current = setTimeout(() => submit(verdict.value as string), 650);
        return;
      }
      failAndRetry();
    },
    [question, lang, submit, failAndRetry],
  );

  const handleNoSpeech = useCallback(() => {
    failAndRetry();
  }, [failAndRetry]);

  // A patient who cannot read the screen still has to be told how to
  // answer — the options for a choice, "yes or no" for a binary, and for
  // a numeric that a number is wanted and which ones are allowed. The
  // numeric case is what was missing: the kiosk read the question and then
  // waited in silence for a number it never asked for.
  const spoken = buildSpokenPrompt(question, lang);

  const voice = useSpeech({
    turnKey: question.id,
    spokenText: spoken,
    kind: question.kind,
    lang,
    enabled,
    onTranscript: handleTranscript,
    onNoSpeech: handleNoSpeech,
  });

  // Kept in a ref, assigned from an effect rather than during render, so
  // the deferred retry timer always calls the current turn's retry.
  useEffect(() => {
    retryRef.current = voice.retry;
  });

  useEffect(() => {
    setHint(null);
    setPicked(null);
    failuresRef.current = 0;
  }, [question.id]);

  useEffect(
    () => () => {
      if (submitTimerRef.current) clearTimeout(submitTimerRef.current);
      if (retryTimerRef.current) clearTimeout(retryTimerRef.current);
    },
    [],
  );

  return { voice, hint, picked, submit };
}
