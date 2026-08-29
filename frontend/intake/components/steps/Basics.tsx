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
import type { Question, SessionState } from '../../tree/types';

const AGE_QUESTION: Question = {
  id: 'basics_age',
  kind: 'number',
  prompt: STR.basicsAgeQ,
  numberRange: [0, 120],
};

const SEX_QUESTION: Question = {
  id: 'basics_sex',
  kind: 'choice',
  prompt: STR.basicsSexQ,
  options: [
    { value: 'M', label: STR.sexMale },
    { value: 'F', label: STR.sexFemale },
    { value: 'O', label: STR.sexOther },
  ],
  synonyms: {
    M: ['man', 'boy', 'male', 'purush', 'aadmi', 'ladka', 'पुरुष', 'आदमी', 'लड़का', 'मर्द'],
    F: ['woman', 'girl', 'female', 'mahila', 'aurat', 'ladki', 'महिला', 'औरत', 'लड़की', 'स्त्री'],
    O: [
      'other', 'anya', 'अन्य',
      'transgender', 'trans', 'non binary', 'nonbinary',
      'prefer not to say', 'kinnar', 'किन्नर', 'ट्रांसजेंडर', 'नहीं बताना',
    ],
  },
};

/** Age immediately resolves the six-stratum band (engine.ts `setBasics`) —
 *  everything asked after this point is stratum-aware. Two sequential
 *  voice turns on one screen: age, then sex. */
export function Basics() {
  const { session, actions } = useIntakeSession();
  const [muted, setMuted] = useState(false);
  const [ageAnswer, setAgeAnswer] = useState<string | null>(null);
  const [sex, setSex] = useState<SessionState['sex']>(null);

  const onAge = (v: string) => setAgeAnswer(v);
  const onSex = (v: string) => {
    const chosen = v as SessionState['sex'];
    setSex(chosen);
    actions.setBasics(ageAnswer ? Number(ageAnswer) : null, chosen);
  };

  const activeQuestion = ageAnswer === null ? AGE_QUESTION : SEX_QUESTION;
  const enabled = session.consent.listen && !muted;

  const { voice, hint, picked, submit } = useVoiceAnswer({
    question: activeQuestion,
    lang: session.lang,
    enabled,
    onAnswer: ageAnswer === null ? onAge : onSex,
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
      title={t(session.lang, activeQuestion.prompt)}
      onBack={() =>
        ageAnswer !== null ? setAgeAnswer(null) : actions.goTo('human-offer')
      }
    >
      <MicOrb phase={voice.phase} level={voice.level} lang={session.lang} />

      {ageAnswer !== null && (
        <p className="text-center text-sm mb-4" style={{ color: 'var(--text-dim)' }}>
          {t(session.lang, STR.basicsAgeQ)} — {ageAnswer}
        </p>
      )}

      {hint && (
        <p className="text-center text-sm mb-2" style={{ color: 'var(--mp-red)' }}>
          {hint}
        </p>
      )}

      <QuestionCard lang={session.lang} question={activeQuestion} onSubmit={submit} highlightValue={picked} />

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
