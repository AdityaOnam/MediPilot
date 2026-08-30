'use client';

import { Screen } from '../Screen';
import { BigButton } from '../controls';
import { STR, t } from '../../strings';
import { useIntakeSession } from '../../session';

export function Welcome() {
  const { session, actions } = useIntakeSession();
  return (
    <Screen
      lang={session.lang}
      spokenText={`${t(session.lang, STR.welcomeGreeting)} ${t(session.lang, STR.welcomeSub)}`}
    >
      <div className="text-center mb-6">
        <h1 className="text-3xl font-semibold mb-2">{t(session.lang, STR.welcomeGreeting)}</h1>
        <p style={{ color: 'var(--text-dim)' }}>{t(session.lang, STR.welcomeSub)}</p>
      </div>

      <p className="text-sm text-center mb-3" style={{ color: 'var(--text-dim)' }}>
        {t(session.lang, STR.chooseLanguage)}
      </p>
      <div className="grid grid-cols-2 gap-3">
        {/* Both neutral, not "primary" — tapping either navigates away
         *  immediately, so there is no selected state to represent. Using
         *  session.lang's default ('en') to pick a variant made English
         *  render as solid red before the patient had chosen anything. */}
        <BigButton
          variant="secondary"
          onClick={() => {
            actions.setLang('en');
            actions.goTo('consent');
          }}
        >
          <span className="block text-center">{STR.langEnglish.en}</span>
        </BigButton>
        <BigButton
          variant="secondary"
          onClick={() => {
            actions.setLang('hi');
            actions.goTo('consent');
          }}
        >
          <span className="block text-center">{STR.langHindi.hi}</span>
        </BigButton>
      </div>

      <button
        type="button"
        className="mt-8 text-sm underline mx-auto block"
        style={{ color: 'var(--text-dim)' }}
      >
        {t(session.lang, STR.needHelp)}
      </button>
    </Screen>
  );
}
