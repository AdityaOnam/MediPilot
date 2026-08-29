'use client';

import { useState } from 'react';
import { Screen } from '../Screen';
import { STR, t } from '../../strings';
import { useIntakeSession } from '../../session';
import { api } from '@/lib/api/client';
import type { IntakeSubmission } from '@/lib/api/types';

/**
 * A real branch with its own screen, not a bounce-out (declining consent
 * or preferring a person). Token still issued; queue position is not
 * affected — the screen says so, and the submission carries no penalty
 * signal (Part 1 / consent-must-never-be-rendered-as-risk).
 */
export function HumanLane() {
  const { session, actions } = useIntakeSession();
  const [busy, setBusy] = useState(false);

  const spoken = `${t(session.lang, STR.humanLaneTitle)} ${t(session.lang, STR.humanLaneNote)}`;

  async function requestToken() {
    setBusy(true);
    const submission: IntakeSubmission = {
      displayName: 'Anonymous Patient',
      ageYears: session.ageYears ?? undefined,
      sex: session.sex ?? undefined,
      chiefComplaint: session.chiefComplaint || 'Human lane — details to be taken in person',
      arrivalMode: 'walk-in',
      assisted: session.assisted ?? true,
      humanAssistanceRequested: true,
      medicalInfoConsent: session.consent.records,
      listeningConsent: session.consent.listen,
      language: session.lang,
      symptomAnswers: session.answers,
      redFlagsFired: session.redFlags.map((f) => f.code),
      // Carried even here. Choosing a person over the kiosk changes who
      // takes the details; it does not change which vitals the complaint
      // owes, and dropping them would quietly send this patient to the
      // board with nothing for the counter to measure.
      branch: session.branch,
      painScore: session.painScore,
    };
    try {
      const res = await api.submitIntake(submission);
      actions.issueToken(res.token, res.counter ?? null, res.requiredVitals ?? []);
    } catch (e) {
      console.error('submitIntake failed (human lane)', e);
      actions.issueToken(String(Math.floor(Math.random() * 899 + 100)), null);
    } finally {
      setBusy(false);
    }
  }

  return (
    <Screen lang={session.lang} spokenText={spoken} title={t(session.lang, STR.humanLaneTitle)}>
      <p className="text-base mb-10" style={{ color: 'var(--text-dim)' }}>
        {t(session.lang, STR.humanLaneNote)}
      </p>
      <button
        type="button"
        onClick={requestToken}
        disabled={busy}
        className="w-full px-6 py-5 rounded-2xl text-lg font-semibold disabled:opacity-50"
        style={{ background: 'var(--mp-red)', color: 'white' }}
      >
        {busy ? '…' : t(session.lang, STR.continue)}
      </button>
    </Screen>
  );
}
