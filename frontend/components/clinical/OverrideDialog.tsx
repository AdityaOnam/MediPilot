'use client';

import { useEffect, useRef, useState } from 'react';
import type { Band, Encounter, Factor, ScoreResponse } from '@/lib/api/types';
import { OVERRIDE_REASON_CODES, BAND_RANK } from '@/lib/api/types';
import { BandChip } from './BandChip';

interface Props {
  encounter: Encounter;
  score: ScoreResponse;
  targetBand: Band;
  onCancel: () => void;
  onConfirm: (payload: {
    band: Band;
    reasonCode: string;
    reasonText: string;
    factorsShown: Factor[];
    scoreAtDecision: { probability: number; confidence: 'high' | 'moderate' | 'low' };
  }) => Promise<void>;
}

const HOLD_MS = 1500;
const CLINICIAN_ID = 'demo-nurse-01';
const CLINICIAN_ROLE = 'triage-nurse';

/**
 * The 16-field override capture. Shows the nurse EXACTLY what will be written
 * before they confirm — nobody signs a record they have not seen (DESIGN §8).
 *
 * A downward override requires a confirm-and-hold: the button records a 1.5-s
 * hold before committing. §6 puts the asymmetric-autonomy claim in the
 * interaction cost and the signed record, not in an animation curve.
 */
export function OverrideDialog({ encounter, score, targetBand, onCancel, onConfirm }: Props) {
  const [reasonCode, setReasonCode] = useState('');
  const [reasonText, setReasonText] = useState('');
  const [holding, setHolding] = useState(false);
  const [holdProgress, setHoldProgress] = useState(0);
  const [busy, setBusy] = useState(false);
  const holdStart = useRef<number | null>(null);
  const rafId = useRef<number | null>(null);

  const systemBand = score.effectiveBand;
  const direction: 'escalation' | 'de-escalation' =
    BAND_RANK[targetBand] > BAND_RANK[systemBand] ? 'escalation' : 'de-escalation';
  const isDownward = direction === 'de-escalation';

  const applicableCodes = OVERRIDE_REASON_CODES.filter(c => {
    if (direction === 'escalation' && c.deescalationOnly) return false;
    if (direction === 'de-escalation' && c.escalationOnly) return false;
    return true;
  });

  const noteRequired = reasonCode === 'other-with-note';
  const canConfirm = !!reasonCode && (!noteRequired || reasonText.trim().length >= 10);

  const factorsShown = score.explanation?.channel1 ?? [];
  const inputsHashPreview = 'sha256(vitals)…';

  async function commit() {
    if (!canConfirm || busy) return;
    setBusy(true);
    try {
      await onConfirm({
        band: targetBand,
        reasonCode,
        reasonText: reasonText.trim(),
        factorsShown,
        scoreAtDecision: {
          probability: score.probability ?? 0,
          confidence: score.confidence ?? 'moderate',
        },
      });
    } finally {
      setBusy(false);
    }
  }

  function startHold() {
    if (!canConfirm || busy) return;
    setHolding(true);
    holdStart.current = performance.now();
    const step = (t: number) => {
      const elapsed = t - (holdStart.current ?? t);
      const p = Math.min(1, elapsed / HOLD_MS);
      setHoldProgress(p);
      if (p >= 1) {
        setHolding(false);
        setHoldProgress(0);
        commit();
      } else {
        rafId.current = requestAnimationFrame(step);
      }
    };
    rafId.current = requestAnimationFrame(step);
  }

  function endHold() {
    setHolding(false);
    setHoldProgress(0);
    holdStart.current = null;
    if (rafId.current !== null) cancelAnimationFrame(rafId.current);
  }

  useEffect(() => () => { if (rafId.current !== null) cancelAnimationFrame(rafId.current); }, []);

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-labelledby="override-title"
      className="fixed inset-0 z-50 flex items-start justify-center p-6 overflow-y-auto"
      style={{ background: 'rgba(0,0,0,0.65)' }}
      onClick={onCancel}
    >
      <div
        className="w-full max-w-3xl rounded-lg border shadow-2xl my-4"
        style={{ background: 'var(--bg-card)', borderColor: 'var(--line)', color: 'var(--text)' }}
        onClick={e => e.stopPropagation()}
      >
        {/* Header */}
        <header className="p-5 border-b flex items-center justify-between" style={{ borderColor: 'var(--line)' }}>
          <div>
            <h2 id="override-title" className="text-lg font-bold">Override capture · Token {encounter.token}</h2>
            <p className="text-xs mt-0.5" style={{ color: 'var(--text-dim)' }}>
              Sixteen fields will be written to the audit ledger. Review before confirming.
            </p>
          </div>
          <div className="flex items-center gap-2 text-xs">
            <BandChip band={systemBand} size="sm" />
            <span style={{ color: 'var(--text-dim)' }}>→</span>
            <BandChip band={targetBand} size="sm" />
            {isDownward && (
              <span
                className="ml-2 px-2 py-0.5 rounded text-[10px] font-bold uppercase"
                style={{ background: 'var(--acuity-red-fill)', color: 'var(--acuity-red)', border: '1px solid var(--acuity-red)' }}
              >
                Downward · Requires Hold
              </span>
            )}
          </div>
        </header>

        {/* Reason capture */}
        <section className="p-5 space-y-4 border-b" style={{ borderColor: 'var(--line)' }}>
          <div>
            <label className="block text-xs font-semibold uppercase tracking-wider mb-2" style={{ color: 'var(--text-dim)' }}>
              Reason code {applicableCodes.length < OVERRIDE_REASON_CODES.length && (
                <span className="normal-case font-normal ml-1">({direction} codes only)</span>
              )}
            </label>
            <div className="grid gap-1.5 sm:grid-cols-2">
              {applicableCodes.map(c => (
                <label
                  key={c.code}
                  className="flex items-start gap-2 p-2 rounded cursor-pointer text-sm"
                  style={{
                    background: reasonCode === c.code ? 'var(--bg-raised)' : 'transparent',
                    border: `1px solid ${reasonCode === c.code ? 'var(--focus)' : 'var(--line)'}`,
                  }}
                >
                  <input
                    type="radio"
                    name="reasonCode"
                    value={c.code}
                    checked={reasonCode === c.code}
                    onChange={() => setReasonCode(c.code)}
                    className="mt-0.5"
                  />
                  <span>{c.label}</span>
                </label>
              ))}
            </div>
          </div>

          <div>
            <label className="block text-xs font-semibold uppercase tracking-wider mb-2" style={{ color: 'var(--text-dim)' }}>
              Free-text note{noteRequired ? ' · required (≥10 chars)' : ' · optional'}
            </label>
            <textarea
              className="w-full p-3 rounded border text-sm"
              rows={3}
              value={reasonText}
              onChange={e => setReasonText(e.target.value)}
              placeholder="What led to this decision?"
              style={{
                background: 'var(--bg-raised)',
                borderColor: noteRequired && reasonText.trim().length < 10 ? 'var(--acuity-yellow)' : 'var(--line)',
                color: 'var(--text)',
              }}
            />
          </div>
        </section>

        {/* Verbatim preview — what will be written */}
        <section className="p-5">
          <h3 className="text-xs font-semibold uppercase tracking-wider mb-3" style={{ color: 'var(--text-dim)' }}>
            Preview · what will be signed into the ledger
          </h3>
          <div
            className="p-4 rounded font-mono text-[11px] overflow-x-auto"
            style={{ background: 'var(--bg-raised)', color: 'var(--text)' }}
          >
            <PreviewRow k="patientId"          v={encounter.encounterId} />
            <PreviewRow k="timestampUtc"       v={new Date().toISOString()} />
            <PreviewRow k="clinicianId"        v={CLINICIAN_ID} />
            <PreviewRow k="clinicianRole"      v={CLINICIAN_ROLE} />
            <PreviewRow k="systemBand"         v={systemBand} />
            <PreviewRow k="clinicianBand"      v={targetBand} />
            <PreviewRow k="direction"          v={direction} />
            <PreviewRow k="reasonCode"         v={reasonCode || '(not selected)'} />
            <PreviewRow k="reasonText"         v={reasonText.trim() || '(empty)'} />
            <PreviewRow k="score"              v={(score.probability ?? 0).toFixed(3)} />
            <PreviewRow k="confidence"         v={score.confidence ?? '—'} />
            <PreviewRow k="factorsShown"       v={`[${factorsShown.length} factors, as displayed]`} />
            <PreviewRow k="inputsHash"         v={inputsHashPreview} />
            <PreviewRow k="modelVersion"       v={score.modelVersion} />
            <PreviewRow k="calibrationVersion" v={score.calibrationVersion} />
            <PreviewRow k="consentState"       v={encounter.medicalInfoConsent ? 'full' : 'observation-only'} />
            <PreviewRow k="outcomeRef"         v="null (back-filled when known)" />
          </div>
        </section>

        {/* Actions */}
        <footer className="p-5 border-t flex items-center justify-between" style={{ borderColor: 'var(--line)' }}>
          <button
            onClick={onCancel}
            className="px-4 py-2 rounded text-sm font-medium border"
            style={{ borderColor: 'var(--line)', color: 'var(--text)' }}
          >
            Cancel
          </button>

          {isDownward ? (
            <button
              onMouseDown={startHold}
              onMouseUp={endHold}
              onMouseLeave={endHold}
              onTouchStart={startHold}
              onTouchEnd={endHold}
              disabled={!canConfirm || busy}
              className="relative px-6 py-2.5 rounded font-medium text-sm text-white overflow-hidden disabled:opacity-50"
              style={{ background: 'var(--acuity-red)' }}
            >
              <span
                className="absolute inset-y-0 left-0"
                style={{ background: 'rgba(0,0,0,0.35)', width: `${holdProgress * 100}%`, transition: holding ? 'none' : 'width 120ms' }}
                aria-hidden
              />
              <span className="relative">
                {holding ? `Hold… ${Math.round(holdProgress * 100)}%` : 'Hold to confirm downward override'}
              </span>
            </button>
          ) : (
            <button
              onClick={commit}
              disabled={!canConfirm || busy}
              className="px-6 py-2.5 rounded font-medium text-sm text-white disabled:opacity-50"
              style={{ background: 'var(--focus)' }}
            >
              {busy ? 'Signing…' : 'Confirm & sign to ledger'}
            </button>
          )}
        </footer>
      </div>
    </div>
  );
}

function PreviewRow({ k, v }: { k: string; v: string }) {
  return (
    <div className="flex gap-3 py-0.5">
      <span className="min-w-[150px]" style={{ color: 'var(--text-dim)' }}>{k}</span>
      <span className="flex-1 break-all">{v}</span>
    </div>
  );
}
