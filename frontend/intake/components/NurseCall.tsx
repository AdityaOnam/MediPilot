'use client';

import { useEffect, useState } from 'react';
import { Screen } from './Screen';
import { STR, t } from '../strings';
import { useIntakeSession } from '../session';
import { api } from '@/lib/api/client';
import type { IntakeSubmission } from '@/lib/api/types';

/**
 * The red-flag interrupt (Part 4). Renders in place of every other screen
 * the instant `session.needsImmediateNurse` is set — IntakeApp checks this
 * before the normal step router, so it wins regardless of what `step`
 * says. Calm-serious, no siren, no flashing, and no acuity word anywhere
 * (the paper's rule that acuity is never shown or spoken within patient
 * earshot). Submits immediately so the orchestrator's red-flag
 * short-circuit (app.py) sets human_assigned_band=RED and routes to the
 * triage bay without the patient waiting through the rest of a form.
 */
export function NurseCall() {
  const { session, actions } = useIntakeSession();
  const [elapsedSec, setElapsedSec] = useState(0);

  useEffect(() => {
    if (session.token || !session.nurseCalledAt) return;

    let cancelled = false;
    const submission: IntakeSubmission = {
      displayName: 'Anonymous Patient',
      ageYears: session.ageYears ?? undefined,
      sex: session.sex ?? undefined,
      chiefComplaint: session.chiefComplaint || 'Reported during intake',
      arrivalMode: 'walk-in',
      assisted: session.assisted ?? true,
      // An urgentOn question (self-harm risk) calls a nurse without a
      // red-flag code, so it is submitted as a human-assistance request
      // rather than as a physiological flag the band engine cannot
      // substantiate. Staff still get called; we just do not claim
      // something the eight-code table does not say.
      humanAssistanceRequested: (session.wantsHuman ?? false) || session.urgentWithoutCode,
      medicalInfoConsent: session.consent.records,
      listeningConsent: session.consent.listen,
      language: session.lang,
      symptomAnswers: session.answers,
      redFlagsFired: session.redFlags.map((f) => f.code),
    };

    api.submitIntake(submission)
      .then((res) => {
        if (!cancelled) actions.issueToken(res.token, res.counter ?? null);
      })
      .catch((e) => {
        console.error('submitIntake failed (red flag)', e);
        if (!cancelled) actions.issueToken(String(Math.floor(Math.random() * 899 + 100)), null);
      });

    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [session.nurseCalledAt]);

  useEffect(() => {
    if (!session.nurseCalledAt) return;
    const start = new Date(session.nurseCalledAt).getTime();
    const id = setInterval(() => setElapsedSec(Math.floor((Date.now() - start) / 1000)), 1000);
    return () => clearInterval(id);
  }, [session.nurseCalledAt]);

  const calledTime = session.nurseCalledAt
    ? new Date(session.nurseCalledAt).toLocaleTimeString(session.lang === 'hi' ? 'hi-IN' : 'en-IN', {
        hour: '2-digit',
        minute: '2-digit',
      })
    : '';

  return (
    <Screen lang={session.lang} spokenText={t(session.lang, STR.nurseCallTitle)}>
      <div className="text-center">
        <div
          className="mx-auto mb-8 rounded-full flex items-center justify-center"
          style={{ width: 96, height: 96, background: 'var(--bg-raised)', border: '2px solid var(--mp-red)' }}
        >
          <span className="text-4xl">🛎️</span>
        </div>

        <h1 className="text-2xl font-semibold mb-6">{t(session.lang, STR.nurseCallTitle)}</h1>

        {session.token ? (
          <>
            <p className="text-sm mb-1" style={{ color: 'var(--text-dim)' }}>
              {t(session.lang, STR.tokenIssued)}
            </p>
            <p className="text-6xl font-bold tabular-nums mb-4" style={{ color: 'var(--mp-red)' }}>
              {session.token}
            </p>
          </>
        ) : (
          <p className="text-sm mb-4" style={{ color: 'var(--text-dim)' }}>
            …
          </p>
        )}

        <p className="text-base tabular-nums" style={{ color: 'var(--text-dim)' }}>
          {t(session.lang, STR.nurseCalledAt)} {calledTime} · {formatElapsed(elapsedSec)}
        </p>
      </div>
    </Screen>
  );
}

function formatElapsed(sec: number): string {
  const m = Math.floor(sec / 60);
  const s = sec % 60;
  return `${m}:${String(s).padStart(2, '0')}`;
}
