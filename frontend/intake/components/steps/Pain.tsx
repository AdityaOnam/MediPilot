'use client';

import { useState } from 'react';
import { Screen } from '../Screen';
import { ContinueBar } from '../controls';
import { MicOrb } from '../MicOrb';
import { VoiceBar } from '../VoiceBar';
import { STR, t } from '../../strings';
import { useIntakeSession } from '../../session';
import { useVoiceAnswer } from '../../voice/useVoiceAnswer';
import { setTtsMuted } from '../../voice/tts';
import type { Question } from '../../tree/types';

const FACES = ['😀', '🙂', '😐', '😕', '😣', '😖'];

/** A real question object so the voice cycle treats the pain slider like
 *  any other turn — same turn key, same silence window, same matcher. */
const PAIN_QUESTION: Question = {
  id: 'pain_score',
  kind: 'scale_0_10',
  prompt: STR.painQ,
};

/**
 * The 0–10 pain scale.
 *
 * This screen was tap-only: it rendered a slider and a Continue bar and
 * never opened the mic, so on the one question in the whole intake that
 * is literally a number, the patient could not answer by voice. Every
 * other screen had already been converted. It now runs the same
 * speak -> listen -> match cycle, and the slider moves to the number that
 * was heard before the answer is committed, so a mishear is visible and
 * correctable rather than silently submitted.
 */
export function Pain() {
  const { session, actions } = useIntakeSession();
  const [score, setScore] = useState(session.painScore ?? 0);
  const [muted, setMuted] = useState(false);

  const { voice, hint, picked, submit } = useVoiceAnswer({
    question: PAIN_QUESTION,
    lang: session.lang,
    enabled: session.consent.listen && !muted,
    onAnswer: (value) => actions.setPainScore(Number(value)),
  });

  // The number to show right now. Derived rather than mirrored into state
  // on an effect, so what Continue submits is always what is on screen
  // during the settle delay before the voice answer auto-commits.
  const heard = picked != null && picked !== '' ? Number(picked) : NaN;
  const shown = Number.isFinite(heard) ? heard : score;

  function toggleMute() {
    setMuted((m) => {
      const next = !m;
      setTtsMuted(next);
      if (next) voice.stop();
      return next;
    });
  }

  return (
    <Screen
      lang={session.lang}
      spokenText=""
      title={t(session.lang, STR.painQ)}
      onBack={() => actions.goBackOne()}
    >
      <MicOrb phase={voice.phase} level={voice.level} lang={session.lang} />

      {voice.error === 'mic-denied' && (
        <p className="text-center text-xs mb-2" style={{ color: 'var(--text-dim)' }}>
          {session.lang === 'hi'
            ? 'माइक उपलब्ध नहीं है — कृपया स्लाइडर का उपयोग करें।'
            : 'Microphone unavailable — please use the slider below.'}
        </p>
      )}

      {hint && (
        <p className="text-center text-sm mb-2" style={{ color: 'var(--mp-red)' }}>
          {hint}
        </p>
      )}

      <div className="text-center mb-2">
        <span className="text-6xl">{FACES[Math.min(5, Math.floor(shown / 2))]}</span>
      </div>
      <div className="text-center mb-4">
        <span
          className="text-6xl font-bold tabular-nums transition-transform"
          style={{
            color: 'var(--mp-red)',
            transform: Number.isFinite(heard) ? 'scale(1.12)' : 'scale(1)',
          }}
        >
          {shown}
        </span>
      </div>
      <input
        type="range"
        min={0}
        max={10}
        value={shown}
        onChange={(e) => setScore(Number(e.target.value))}
        className="w-full"
      />
      <div className="flex justify-between text-xs mt-1 mb-4" style={{ color: 'var(--text-dim)' }}>
        <span>{session.lang === 'hi' ? 'दर्द नहीं' : 'No pain'}</span>
        <span>{session.lang === 'hi' ? 'सबसे तेज' : 'Worst possible'}</span>
      </div>

      <ContinueBar label={t(session.lang, STR.continue)} onContinue={() => submit(String(shown))} />

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
