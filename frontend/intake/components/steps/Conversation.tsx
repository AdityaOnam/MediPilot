'use client';

import { useCallback, useEffect, useRef, useState } from 'react';
import { Screen } from '../Screen';
import { QuestionCard } from '../QuestionCard';
import { MicOrb } from '../MicOrb';
import { VoiceBar } from '../VoiceBar';
import { STR, t } from '../../strings';
import { useIntakeSession } from '../../session';
import { canGoBack, currentQuestion } from '../../tree/engine';
import { localClassify } from '../../tree/localClassify';
import { classifyRemote } from '../../tree/classifyRemote';
import { observeRemote } from '../../redflags/observe';
import type { Question } from '../../tree/types';
import { useSpeech } from '../../voice/useSpeech';
import { setTtsMuted } from '../../voice/tts';
import { matchAnswer } from '../../match';
import { buildSpokenPrompt } from '../../voice/answerMode';

/** Q0 is a real question object so the voice cycle treats it identically
 *  to every branch node — same turn key, same silence window rules. */
const OPENING_QUESTION: Question = {
  id: '__opening',
  kind: 'free_text',
  prompt: STR.openingQ,
};

/**
 * Q0 plus the branch/tail walk. Owns the speak -> arm -> listen cycle for
 * the whole clinical conversation; Screen is passed an empty spokenText
 * here because useSpeech does the speaking, and two speakers would talk
 * over each other.
 */
export function Conversation() {
  const { session, actions } = useIntakeSession();
  const asked = !!session.chiefComplaint;
  const question = asked ? currentQuestion(session) : OPENING_QUESTION;

  const [hint, setHint] = useState<string | null>(null);
  const [picked, setPicked] = useState<string | null>(null);
  const [muted, setMuted] = useState(false);
  const failuresRef = useRef(0);
  const submitTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const retryTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const retryRef = useRef<(() => void) | null>(null);

  const submit = useCallback(
    (value: string) => {
      if (submitTimerRef.current) clearTimeout(submitTimerRef.current);
      if (retryTimerRef.current) clearTimeout(retryTimerRef.current);
      setHint(null);
      setPicked(null);
      failuresRef.current = 0;

      const wasFreeText = (question?.kind ?? 'free_text') === 'free_text';

      if (!asked) {
        actions.setChiefComplaint(value);
        // Groq refines the branch only when the offline keyword pass had
        // no confident hit — otherwise the round-trip buys nothing.
        if (!localClassify(value)) {
          void classifyRemote(value).then((branch) => {
            // 'other' is also what this route returns when it fails soft,
            // so it carries no information — applying it would overwrite
            // the paeds_general routing the local pass gives a child with
            // a non-specific complaint.
            if (branch && branch !== 'other') actions.refineBranch(branch);
          });
        }
      } else {
        actions.submitAnswer(value);
      }

      // Tier B runs on every free-text answer, alongside the deterministic
      // tier A scan that engine.ts already completed synchronously. It can
      // only ADD observations, so a slow or failed call never costs a flag
      // that tier A had already caught.
      if (wasFreeText) {
        void observeRemote(value).then((r) => {
          if (r.redFlags.length || Object.keys(r.fields).length) {
            actions.applyObserved(r.redFlags, r.fields);
          }
        });
      }
    },
    [asked, actions, question],
  );

  /** The mic re-opens for the same question after an unmatched answer,
   *  twice, before deferring to the touchscreen. A turn used to be
   *  one-shot: commit() latched the recogniser closed and nothing
   *  re-opened it until the question changed. */
  const MAX_RETRIES = 2;

  const failAndRetry = useCallback(() => {
    failuresRef.current += 1;
    const exhausted = failuresRef.current > MAX_RETRIES;
    setHint(
      exhausted ? t(session.lang, STR.pleasePickBelow) : t(session.lang, STR.didntCatch),
    );
    if (!exhausted) {
      retryTimerRef.current = setTimeout(() => retryRef.current?.(), 500);
    }
  }, [session.lang]);

  const handleTranscript = useCallback(
    async (text: string) => {
      const q = question;
      if (!q || !text.trim()) {
        failAndRetry();
        return;
      }

      const verdict = await matchAnswer(text, q, undefined, session.lang);
      if (verdict.value !== null) {
        // Flash what was understood before advancing, so the screen does
        // not simply jump from under the patient.
        setPicked(q.kind === 'free_text' ? null : verdict.value);
        submitTimerRef.current = setTimeout(() => submit(verdict.value as string), 650);
        return;
      }

      failAndRetry();
    },
    [question, session.lang, submit, failAndRetry],
  );

  const handleNoSpeech = useCallback(() => {
    failAndRetry();
  }, [failAndRetry]);

  // What gets read aloud. answerMode owns the per-shape suffix — options
  // for a choice, "yes or no" for a binary, "say a number between X and Y"
  // for a numeric — so this and useVoiceAnswer cannot drift apart.
  const promptText = question ? t(session.lang, question.prompt) : '';
  const spoken = question ? buildSpokenPrompt(question, session.lang) : '';

  const voice = useSpeech({
    turnKey: question?.id ?? 'none',
    spokenText: spoken,
    kind: question?.kind ?? 'free_text',
    lang: session.lang,
    enabled: session.consent.listen && !muted,
    onTranscript: handleTranscript,
    onNoSpeech: handleNoSpeech,
    onMetrics: (m) => {
      // Recorded for the nurse card only. Never escalates on its own —
      // see engine.noteSpeechEffort.
      if (m.fragmented) actions.noteSpeechEffort();
    },
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
  }, [question?.id]);

  useEffect(() => () => {
    if (submitTimerRef.current) clearTimeout(submitTimerRef.current);
    if (retryTimerRef.current) clearTimeout(retryTimerRef.current);
  }, []);

  function toggleMute() {
    setMuted((m) => {
      const next = !m;
      setTtsMuted(next);
      if (next) voice.stop();
      return next;
    });
  }

  if (!question) return null;

  // Available on every question now. Voice mishears things, and until this
  // was here a wrong answer to any branch question was unrecoverable —
  // only the opening question ever had a way back.
  const backHandler = canGoBack(session)
    ? () => actions.goBackOne()
    : () => actions.goTo('basics');

  return (
    <Screen
      lang={session.lang}
      spokenText=""
      title={promptText}
      onBack={backHandler}
    >
      <MicOrb phase={voice.phase} level={voice.level} lang={session.lang} />

      {voice.error === 'mic-denied' && (
        <p className="text-center text-xs mb-2" style={{ color: 'var(--text-dim)' }}>
          {session.lang === 'hi'
            ? 'माइक उपलब्ध नहीं है — कृपया टाइप करें या नीचे से चुनें।'
            : 'Microphone unavailable — please type or choose below.'}
        </p>
      )}

      {hint && (
        <p className="text-center text-sm mb-2" style={{ color: 'var(--mp-red)' }}>
          {hint}
        </p>
      )}

      <QuestionCard
        lang={session.lang}
        question={question}
        onSubmit={submit}
        voiceText={question.kind === 'free_text' ? voice.interim : undefined}
        highlightValue={picked}
      />

      <VoiceBar
        lang={session.lang}
        phase={voice.phase}
        muted={muted}
        onToggleMute={toggleMute}
        onSkip={voice.skip}
        onStop={voice.stop}
        onRetry={voice.retry}
        micDenied={voice.error === 'mic-denied'}
      />
    </Screen>
  );
}
