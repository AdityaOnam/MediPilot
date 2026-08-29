'use client';

import { useState } from 'react';
import { Screen } from '../Screen';
import { QuestionCard } from '../QuestionCard';
import { MicOrb } from '../MicOrb';
import { VoiceBar } from '../VoiceBar';
import { STR, t } from '../../strings';
import { useIntakeSession } from '../../session';
import { useVoiceAnswer } from '../../voice/useVoiceAnswer';
import { setTtsMuted } from '../../voice/tts';
import type { Question } from '../../tree/types';

const QUESTION: Question = {
  id: 'companion',
  kind: 'choice',
  prompt: STR.companionQ,
  options: [
    { value: 'with', label: STR.companionWith },
    { value: 'alone', label: STR.companionAlone },
  ],
  synonyms: {
    with: ['someone is here', 'not alone', 'with me', 'mere saath', 'मेरे साथ है'],
    alone: ['by myself', 'nobody', 'no one', 'akela hoon', 'अकेला हूं', 'अकेली हूं'],
  },
};

/**
 * First voice-driven screen — consent to listen has just been granted on
 * the previous screen, so this is the earliest point the mic may
 * legitimately turn on (see engine.ts setConsent).
 */
export function Companion() {
  const { session, actions } = useIntakeSession();
  const [muted, setMuted] = useState(false);

  const { voice, hint, picked, submit } = useVoiceAnswer({
    question: QUESTION,
    lang: session.lang,
    enabled: session.consent.listen && !muted,
    onAnswer: (value) => actions.setCompanion(value === 'with'),
  });

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
      title={t(session.lang, STR.companionQ)}
      onBack={() => actions.goTo('consent')}
    >
      <MicOrb phase={voice.phase} level={voice.level} lang={session.lang} />
      {hint && (
        <p className="text-center text-sm mb-2" style={{ color: 'var(--mp-red)' }}>
          {hint}
        </p>
      )}
      <QuestionCard lang={session.lang} question={QUESTION} onSubmit={submit} highlightValue={picked} />
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
