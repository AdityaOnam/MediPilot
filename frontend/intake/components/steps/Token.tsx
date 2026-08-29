'use client';

import { Screen } from '../Screen';
import { STR, t } from '../../strings';
import { useIntakeSession } from '../../session';
import { VitalIcon } from '@/components/clinical/VitalIcon';
import { VITALS, normaliseVitalCode } from '@/lib/clinical/vitals';

export function Token() {
  const { session, actions } = useIntakeSession();

  const owed = session.requiredVitals ?? [];
  const hasCounter = !!session.counter && owed.length > 0;

  // The counter directive is read aloud too — a patient who cannot read
  // the board still has to know where to walk.
  const spoken = [
    `${t(session.lang, STR.tokenIssued)} ${session.token}.`,
    hasCounter ? `${t(session.lang, STR.counterGoTo)} ${session.counter}.` : '',
    t(session.lang, STR.tokenWatch),
  ]
    .filter(Boolean)
    .join(' ');

  return (
    <Screen lang={session.lang} spokenText={spoken}>
      <div className="text-center">
        <p className="text-sm mb-2" style={{ color: 'var(--text-dim)' }}>
          {t(session.lang, STR.tokenIssued)}
        </p>
        <p className="text-7xl font-bold tabular-nums mb-6" style={{ color: 'var(--mp-red)' }}>
          {session.token}
        </p>

        {hasCounter ? (
          <div
            className="rounded-2xl px-5 py-6 mb-6 text-left"
            style={{ background: 'var(--bg-raised)', border: '1px solid var(--line)' }}
          >
            <p className="text-sm mb-1 text-center" style={{ color: 'var(--text-dim)' }}>
              {t(session.lang, STR.counterGoTo)}
            </p>
            <p
              className="text-3xl font-semibold text-center mb-5"
              style={{ color: 'var(--text)' }}
            >
              {session.counter}
            </p>

            <p className="text-sm mb-3" style={{ color: 'var(--text-dim)' }}>
              {t(session.lang, STR.counterWhy)}
            </p>
            <ul className="flex flex-col gap-2 mb-4">
              {owed.map((code) => {
                const canonical = normaliseVitalCode(code);
                return (
                  <li key={code} className="flex items-center gap-3 text-base">
                    <span
                      className="shrink-0 flex items-center justify-center w-9 h-9 rounded-xl"
                      style={{ background: 'var(--bg)', color: 'var(--mp-red)' }}
                    >
                      <VitalIcon code={code} size={18} />
                    </span>
                    <span style={{ color: 'var(--text)' }}>
                      {canonical ? VITALS[canonical].label : code}
                    </span>
                  </li>
                );
              })}
            </ul>

            <p className="text-xs leading-relaxed" style={{ color: 'var(--text-dim)' }}>
              {t(session.lang, STR.counterThen)}
            </p>
          </div>
        ) : (
          session.counter && (
            <p className="text-lg mb-6" style={{ color: 'var(--text)' }}>
              {session.counter}
            </p>
          )
        )}

        <p className="text-base mb-8" style={{ color: 'var(--text-dim)' }}>
          {t(session.lang, STR.tokenWatch)}
        </p>

        <button
          type="button"
          className="w-full px-6 py-5 rounded-2xl text-lg font-semibold"
          style={{ background: 'var(--mp-red)', color: 'white' }}
        >
          {t(session.lang, STR.feelWorse)}
        </button>

        <button
          type="button"
          className="mt-8 text-sm underline"
          style={{ color: 'var(--text-dim)' }}
          onClick={actions.reset}
        >
          {session.lang === 'hi' ? 'नया मरीज' : 'New patient'}
        </button>
      </div>
    </Screen>
  );
}
