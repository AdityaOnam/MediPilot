'use client';

import { useState } from 'react';
import { Screen } from '../Screen';
import { BigButton } from '../controls';
import { STR, t } from '../../strings';
import { useIntakeSession } from '../../session';
import { getQuestion } from '../../tree';
import { api } from '@/lib/api/client';
import type { IntakeSubmission } from '@/lib/api/types';

/**
 * Spoken summary, dashed borders until confirmed (Part 1). Submits via
 * the shared api.submitIntake() so the patient reaches /board exactly as
 * the existing flow does — nothing about the backend contract changes
 * (Part 7 of the plan).
 */
export function Readback() {
  const { session, actions } = useIntakeSession();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fields: { label: string; value: string }[] = [
    { label: t(session.lang, STR.openingQ), value: session.chiefComplaint },
    ...Object.entries(session.answers)
      .filter(([k]) => !k.startsWith('__') && k !== 'chief_complaint')
      .map(([id, value]) => ({
        label: t(session.lang, getQuestion(id)?.prompt ?? { en: id, hi: id }),
        value,
      })),
    { label: t(session.lang, STR.painQ), value: String(session.painScore ?? '—') },
  ];

  const summarySpoken = fields.map((f) => `${f.label}: ${f.value}`).join('. ');

  async function handleConfirm() {
    setBusy(true);
    setError(null);
    actions.confirmReadback();

    const submission: IntakeSubmission = {
      displayName: 'Anonymous Patient',
      ageYears: session.ageYears ?? undefined,
      sex: session.sex ?? undefined,
      chiefComplaint: session.chiefComplaint || 'No complaint',
      arrivalMode: 'walk-in',
      assisted: session.assisted ?? true,
      humanAssistanceRequested: session.wantsHuman ?? false,
      medicalInfoConsent: session.consent.records,
      listeningConsent: session.consent.listen,
      language: session.lang,
      symptomAnswers: session.answers,
      redFlagsFired: session.redFlags.map((f) => f.code),
      // Both drive the risk engine on the other side: the branch decides
      // which vitals the counter must capture, and the pain score is the
      // only acuity number the patient states themselves.
      branch: session.branch,
      painScore: session.painScore,
    };

    try {
      const res = await api.submitIntake(submission);
      actions.issueToken(res.token, res.counter ?? null, res.requiredVitals ?? []);
    } catch (e) {
      console.error('submitIntake failed', e);
      setError(session.lang === 'hi' ? 'कुछ गलत हुआ। कृपया फिर कोशिश करें।' : 'Something went wrong. Please try again.');
    } finally {
      setBusy(false);
    }
  }

  return (
    <Screen lang={session.lang} spokenText={summarySpoken} title={t(session.lang, STR.readbackTitle)} wide>
      <div className="flex flex-col gap-3 mb-6">
        {fields.map((f, i) => (
          <div
            key={i}
            className="px-4 py-3 rounded-xl"
            style={{ border: '1px dashed var(--line)', background: 'var(--bg-raised)' }}
          >
            <div className="text-xs mb-1" style={{ color: 'var(--text-dim)' }}>
              {f.label}
            </div>
            <div className="text-base">{f.value || '—'}</div>
          </div>
        ))}
      </div>

      {error && (
        <p className="text-sm mb-3" style={{ color: 'var(--mp-red)' }}>
          {error}
        </p>
      )}

      <div className="grid grid-cols-2 gap-3">
        {/* Steps back onto the pain question rather than jumping to the
            conversation step. The old goTo('conversation') left the cursor
            parked past the end of the plan, so currentQuestion() returned
            null and the patient got a blank screen with no way forward. */}
        <BigButton variant="secondary" onClick={() => actions.goBackOne()} disabled={busy}>
          {t(session.lang, STR.readbackFix)}
        </BigButton>
        <BigButton onClick={handleConfirm} disabled={busy}>
          {busy ? '…' : t(session.lang, STR.readbackConfirm)}
        </BigButton>
      </div>
    </Screen>
  );
}
