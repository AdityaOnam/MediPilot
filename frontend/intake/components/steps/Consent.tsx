'use client';

import { useState } from 'react';
import { Screen } from '../Screen';
import { ContinueBar } from '../controls';
import { STR, t } from '../../strings';
import { useIntakeSession } from '../../session';

/**
 * Two separate toggles (Part 1). The second is the DPDP §6(1)
 * purpose-specific consent — ABDM record access does not by itself cover
 * using those records as model input, so it is asked for on its own.
 * Declining the first forks to the Human Lane (engine.ts `setConsent`).
 * The spoken version is plain language; the screen carries the full text —
 * reading legalese aloud is not consent (Part 5).
 */
export function Consent() {
  const { session, actions } = useIntakeSession();
  const [listen, setListen] = useState(session.consent.listen);
  const [records, setRecords] = useState(session.consent.records);

  const spoken = `${t(session.lang, STR.consentListenSpoken)} ${t(session.lang, STR.consentRecordsSpoken)}`;

  return (
    <Screen
      lang={session.lang}
      spokenText={spoken}
      title={t(session.lang, STR.consentTitle)}
      onBack={() => actions.goTo('welcome')}
    >
      <div className="flex flex-col gap-4">
        <ConsentToggle
          checked={listen}
          onChange={setListen}
          label={t(session.lang, STR.consentListenLabel)}
        />
        <ConsentToggle
          checked={records}
          onChange={setRecords}
          label={t(session.lang, STR.consentRecordsLabel)}
        />
      </div>

      <ContinueBar
        label={t(session.lang, STR.consentContinue)}
        onContinue={() => actions.setConsent({ listen, records })}
      />
    </Screen>
  );
}

function ConsentToggle({
  checked,
  onChange,
  label,
}: {
  checked: boolean;
  onChange: (v: boolean) => void;
  label: string;
}) {
  return (
    <button
      type="button"
      onClick={() => onChange(!checked)}
      className="flex items-center gap-4 px-5 py-4 rounded-2xl text-left"
      style={{ background: 'var(--bg-raised)', border: '1px solid var(--line)' }}
    >
      <span
        className="shrink-0 rounded-md flex items-center justify-center transition-colors"
        style={{
          width: 26,
          height: 26,
          background: checked ? 'var(--mp-red)' : 'transparent',
          border: `2px solid ${checked ? 'var(--mp-red)' : 'var(--line)'}`,
        }}
      >
        {checked && (
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none">
            <path d="M5 13l4 4L19 7" stroke="white" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round" />
          </svg>
        )}
      </span>
      <span className="text-base" style={{ color: 'var(--text)' }}>
        {label}
      </span>
    </button>
  );
}
