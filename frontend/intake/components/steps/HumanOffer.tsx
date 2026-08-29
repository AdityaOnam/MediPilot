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
  id: 'human-offer',
  kind: 'choice',
  prompt: STR.humanOfferQ,
  options: [
    { value: 'yes', label: STR.humanOfferYes },
    { value: 'no', label: STR.humanOfferNo },
  ],
  synonyms: {
    yes: ['a person', 'someone else', 'human', 'insaan', 'इंसान से'],
    no: ['continue', 'you are fine', 'chalte hain', 'चलते हैं'],
  },
};

/** The human offer comes BEFORE the machine proceeds alone, not after it
 *  fails (Part 1 of the plan — order matters and is unchanged from the
 *  paper's argument). Yes routes straight to Human Lane. */
export function HumanOffer() {
  const { session, actions } = useIntakeSession();
  const [muted, setMuted] = useState(false);

  const { voice, hint, picked, submit } = useVoiceAnswer({
    question: QUESTION,
    lang: session.lang,
    enabled: session.consent.listen && !muted,
    onAnswer: (value) => actions.setHumanOffer(value === 'yes'),
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
      title={t(session.lang, STR.humanOfferQ)}
      onBack={() => actions.goTo('companion')}
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
