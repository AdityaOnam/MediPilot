'use client';

import { useEffect, useState } from 'react';
import Link from 'next/link';
import { useParams } from 'next/navigation';
import { api } from '@/lib/api/client';
import type { Encounter, ScoreResponse, Band, Disposition } from '@/lib/api/types';
import { DISPOSITIONS } from '@/lib/api/types';
import { AcuityCard } from '@/components/clinical/AcuityCard';
import { AbstentionCard } from '@/components/clinical/AbstentionCard';
import { VitalChip } from '@/components/clinical/VitalChip';
import { VitalIcon } from '@/components/clinical/VitalIcon';
import { LockedAcuitySlot } from '@/components/clinical/LockedAcuitySlot';
import { CadenceStrip } from '@/components/clinical/CadenceStrip';
import { OverrideDialog } from '@/components/clinical/OverrideDialog';
import { VitalEntryDialog } from '@/components/clinical/VitalEntryDialog';
import { stratumLabel } from '@/lib/clinical/ageBands';
import { VITALS, normaliseVitalCode } from '@/lib/clinical/vitals';

/** Small panel wrapper — one place that owns the card chrome, so the
 *  surface tokens are applied consistently instead of per-section. */
function Panel({
  title,
  accent,
  right,
  children,
}: {
  title?: string;
  accent?: boolean;
  right?: React.ReactNode;
  children: React.ReactNode;
}) {
  return (
    <section
      className="p-5 rounded-xl"
      style={{
        background: 'var(--bg-card)',
        border: '1px solid var(--line)',
        borderLeft: accent ? '3px solid var(--mp-red)' : undefined,
      }}
    >
      {(title || right) && (
        <div className="flex items-center justify-between mb-3 gap-3">
          {title && (
            <h2 className="text-[11px] font-semibold uppercase tracking-wider" style={{ color: 'var(--text-dim)' }}>
              {title}
            </h2>
          )}
          {right}
        </div>
      )}
      {children}
    </section>
  );
}

export default function CardPage() {
  const params = useParams();
  const id = params.id as string;
  const [encounter, setEncounter] = useState<Encounter | null>(null);
  const [score, setScore] = useState<ScoreResponse | null>(null);
  const [simNowMs, setSimNowMs] = useState(Date.now());
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState<string | null>(null);
  const [overrideTarget, setOverrideTarget] = useState<Band | null>(null);
  const [showVitalEntry, setShowVitalEntry] = useState(false);
  const [dischargeOpen, setDischargeOpen] = useState(false);
  const [dispositionChoice, setDispositionChoice] = useState<Disposition | null>(null);
  const [dispositionNote, setDispositionNote] = useState('');

  useEffect(() => {
    let cancelled = false;
    const load = () => Promise.all([api.getEncounter(id), api.score(id)]).then(([e, s]) => {
      if (!cancelled) { setEncounter(e); setScore(s); }
    });
    load();
    const iv = setInterval(load, 2000);
    return () => { cancelled = true; clearInterval(iv); };
  }, [id]);

  useEffect(() => {
    const iv = setInterval(() => setSimNowMs(Date.now()), 1000);
    return () => clearInterval(iv);
  }, []);

  async function accept() {
    if (!encounter || !score) return;
    setBusy(true);
    try {
      await api.decide({
        encounterId: encounter.encounterId,
        action: 'accept',
        band: score.effectiveBand,
        clinicianId: 'demo-nurse-01',
        clinicianRole: 'triage-nurse',
      });
      setNotice(`Accepted ${score.effectiveBand} for ${encounter.token}.`);
    } finally { setBusy(false); }
  }

  async function confirmDischarge() {
    if (!encounter || !dispositionChoice) return;
    setBusy(true);
    try {
      const updated = await api.setDisposition({
        encounterId: encounter.encounterId,
        disposition: dispositionChoice,
        note: dispositionNote.trim() || undefined,
        clinicianId: 'demo-nurse-01',
      });
      setEncounter(updated);
      setDischargeOpen(false);
      setDispositionChoice(null);
      setDispositionNote('');
      const label = DISPOSITIONS.find(d => d.value === updated.disposition)?.label ?? updated.disposition;
      setNotice(`${updated.token} closed as "${label}". Removed from the board.`);
    } finally { setBusy(false); }
  }

  function beginOverride(newBand: Band) {
    if (!encounter || !score) return;
    if (newBand === score.effectiveBand) return;
    setOverrideTarget(newBand);
  }

  if (!encounter || !score) {
    return (
      <div data-surface="ward" className="min-h-screen flex items-center justify-center" style={{ background: 'var(--bg)', color: 'var(--text-dim)' }}>
        Loading encounter {id}…
      </div>
    );
  }

  const departed = encounter.state === 'departed';
  const owed = encounter.requiredVitals ?? [];

  return (
    <div data-surface="ward" className="min-h-screen pb-20 font-sans" style={{ background: 'var(--bg)', color: 'var(--text)' }}>
      {/* Header */}
      <header
        className="px-6 py-4 sticky top-0 z-40 border-b"
        style={{ background: 'var(--bg)', borderColor: 'var(--line)' }}
      >
        <div className="max-w-7xl mx-auto flex items-center justify-between gap-6 flex-wrap">
          <div className="flex items-center gap-6 flex-wrap">
            <Link
              href="/board"
              className="text-[13px] font-semibold hover:underline flex items-center gap-1.5 uppercase tracking-wide"
              style={{ color: 'var(--text-dim)' }}
            >
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5"><path d="M19 12H5M12 19l-7-7 7-7" /></svg>
              Board
            </Link>
            <div className="w-px h-6" style={{ background: 'var(--line)' }} />
            <div className="flex items-center gap-4 flex-wrap">
              <h1 className="text-xl font-semibold tracking-tight">Token {encounter.token}</h1>
              <div className="flex gap-2 flex-wrap">
                <span className="px-2 py-0.5 rounded-md text-xs font-medium capitalize" style={{ background: 'var(--bg-raised)', border: '1px solid var(--line)', color: 'var(--text-dim)' }}>
                  {stratumLabel(encounter.ageStratum, encounter.ageStratumInferred)}
                </span>
                {encounter.sex && (
                  <span className="px-2 py-0.5 rounded-md text-xs font-medium capitalize" style={{ background: 'var(--bg-raised)', border: '1px solid var(--line)', color: 'var(--text-dim)' }}>
                    {encounter.sex}
                  </span>
                )}
                <span className="px-2 py-0.5 rounded-md text-xs font-medium capitalize" style={{ background: 'rgba(146,106,71,0.12)', border: '1px solid rgba(146,106,71,0.28)', color: 'var(--focus)' }}>
                  {encounter.arrivalMode.replace(/-/g, ' ')}
                </span>
              </div>
            </div>
          </div>

          <div className="flex items-center gap-5">
            <div className="flex items-center gap-2">
              <span className="w-2 h-2 rounded-full" style={{ background: departed ? 'var(--text-dim)' : 'var(--acuity-green)' }} />
              <div className="flex flex-col">
                <span className="text-[11px] font-semibold uppercase tracking-wider leading-none">
                  {departed ? 'Encounter closed' : 'Continuous Re-Triage'}
                </span>
                <span className="text-[10px] leading-none mt-1" style={{ color: 'var(--text-dim)' }}>
                  {departed ? 'No longer on the board' : 'Active monitoring'}
                </span>
              </div>
            </div>
            <span className="text-[11px] font-mono hidden md:inline" style={{ color: 'var(--text-dim)' }}>
              {score.modelVersion}
            </span>
          </div>
        </div>
      </header>

      {/* Closed banner */}
      {departed && (
        <div
          className="max-w-7xl mx-auto mt-4 mb-2 px-5 py-3 rounded-xl text-sm font-medium"
          style={{ background: 'var(--bg-raised)', border: '1px solid var(--line)', color: 'var(--text-dim)' }}
        >
          Closed as{' '}
          <span style={{ color: 'var(--text)' }}>
            {DISPOSITIONS.find(d => d.value === encounter.disposition)?.label ?? encounter.disposition}
          </span>
          {encounter.dispositionAt && ` · ${new Date(encounter.dispositionAt).toLocaleTimeString()}`}
          {encounter.dispositionBy && ` · by ${encounter.dispositionBy}`}
          {encounter.dispositionNote && ` · “${encounter.dispositionNote}”`}
        </div>
      )}

      <main className="max-w-7xl mx-auto p-6 grid gap-6 lg:grid-cols-12 mt-2">
        {/* LEFT */}
        <div className="lg:col-span-8 flex flex-col gap-6">
          <Panel
            title="Chief Complaint"
            accent
            right={score.abstained ? (
              <span className="text-[10px] font-bold uppercase tracking-wider px-2 py-0.5 rounded" style={{ background: 'var(--acuity-abstained-fill)', color: 'var(--acuity-abstained)' }}>OOD</span>
            ) : undefined}
          >
            <p className="text-base leading-relaxed font-medium">{encounter.chiefComplaint ?? '—'}</p>
            {!encounter.medicalInfoConsent && (
              <div
                className="mt-4 flex items-start gap-2 text-xs p-2.5 rounded-lg"
                style={{ background: 'var(--acuity-yellow-fill)', border: '1px solid var(--acuity-yellow)', color: 'var(--acuity-yellow)' }}
              >
                <svg className="w-4 h-4 shrink-0" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" /><path d="M12 8v4" /><path d="M12 16h.01" /></svg>
                <span className="font-medium">History sharing declined. Triaged on observation alone. Queue position unaffected.</span>
              </div>
            )}
          </Panel>

          {/* Provisional-score notice — the patient is on the board but the
              counter has not reported back yet. */}
          {encounter.awaitingVitals && owed.length > 0 && (
            <Panel title="Awaiting measurement">
              <p className="text-sm mb-3">
                This band is scored on the patient&apos;s words alone. These vitals were
                requested at <span className="font-semibold">{encounter.counter ?? 'the counter'}</span> and
                have not been recorded yet:
              </p>
              <div className="flex flex-wrap gap-2 mb-3">
                {owed.map(code => (
                  <span
                    key={code}
                    className="flex items-center gap-1.5 px-2.5 py-1 rounded-lg text-xs font-medium"
                    style={{ background: 'var(--bg-raised)', border: '1px dashed var(--line)', color: 'var(--text-dim)' }}
                  >
                    <VitalIcon code={code} size={14} />
                    {normaliseVitalCode(code) ? VITALS[normaliseVitalCode(code)!].label : code}
                  </span>
                ))}
              </div>
              <Link href="/counter" className="text-sm font-medium hover:underline" style={{ color: 'var(--focus)' }}>
                Open the vitals counter →
              </Link>
            </Panel>
          )}

          <section>
            <h2 className="text-[11px] font-semibold uppercase tracking-wider mb-3 ml-1" style={{ color: 'var(--text-dim)' }}>
              Clinical Signals
            </h2>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
              {score.abstained && (
                <div className="p-3.5 rounded-xl" style={{ background: 'var(--bg-card)', border: '1px solid var(--line)' }}>
                  <h4 className="text-xs font-semibold mb-1">OOD Presentation</h4>
                  <p className="text-[11px] leading-snug" style={{ color: 'var(--text-dim)' }}>
                    Patient presentation does not map to known safe corridors.
                  </p>
                </div>
              )}
              {(!score.confidence || score.confidence === 'low' || score.confidence === 'moderate') && (
                <div className="p-3.5 rounded-xl" style={{ background: 'var(--bg-card)', border: '1px solid var(--line)' }}>
                  <h4 className="text-xs font-semibold mb-1">Low Confidence</h4>
                  <p className="text-[11px] leading-snug" style={{ color: 'var(--text-dim)' }}>
                    {score.suggestsReviewReason ?? 'Model inference confidence is below standard threshold.'}
                  </p>
                </div>
              )}
              <LockedAcuitySlot />
            </div>
          </section>

          <section>
            {score.abstained ? (
              <AbstentionCard
                reason={score.abstentionReason ?? 'OUT_OF_DISTRIBUTION'}
                effectiveBand="YELLOW"
                unmetReviewBreach={encounter.cadence.breachKind === 'UNMET_REVIEW'}
              />
            ) : (
              <Panel title="Automated Status">
                <AcuityCard score={score} />
              </Panel>
            )}
          </section>

          <Panel title="Nurse Decision">
            {notice && (
              <div
                className="mb-4 p-3 rounded-lg text-[13px] font-medium flex items-center gap-2"
                style={{ background: 'rgba(146,106,71,0.10)', border: '1px solid rgba(146,106,71,0.30)', color: 'var(--focus)' }}
              >
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5"><path d="M22 11.08V12a10 10 0 1 1-5.93-9.14" /><polyline points="22 4 12 14.01 9 11.01" /></svg>
                {notice}
              </div>
            )}

            {departed ? (
              <p className="text-sm" style={{ color: 'var(--text-dim)' }}>
                This encounter is closed. Reopen it from the board&apos;s departed list to make further decisions.
              </p>
            ) : (
              <>
                <div className="flex flex-wrap items-center gap-3">
                  <button
                    onClick={accept}
                    disabled={busy || score.abstained}
                    className="px-6 py-2.5 rounded-lg text-sm font-semibold transition-opacity disabled:opacity-40 flex items-center gap-2"
                    style={{ background: 'var(--mp-red)', color: '#fff' }}
                  >
                    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3"><path d="M20 6L9 17l-5-5" /></svg>
                    Accept {!score.abstained && score.effectiveBand}
                  </button>

                  <div className="h-6 w-px mx-1" style={{ background: 'var(--line)' }} />

                  {(['RED', 'YELLOW', 'GREEN'] as Band[]).filter(b => b !== score.effectiveBand).map(b => (
                    <button
                      key={b}
                      onClick={() => beginOverride(b)}
                      disabled={busy}
                      className="px-4 py-2.5 rounded-lg text-[13px] font-semibold transition-opacity disabled:opacity-40"
                      style={{
                        background: 'var(--bg-raised)',
                        border: '1px solid var(--line)',
                        color: b === 'RED' ? 'var(--acuity-red)' : b === 'YELLOW' ? 'var(--acuity-yellow)' : 'var(--acuity-green)',
                      }}
                    >
                      Override to {b}
                    </button>
                  ))}
                </div>

                <p className="text-[11px] mt-4 flex items-start gap-1.5 max-w-lg" style={{ color: 'var(--text-dim)' }}>
                  <svg className="w-3.5 h-3.5 mt-0.5 shrink-0" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><circle cx="12" cy="12" r="10" /><line x1="12" y1="16" x2="12" y2="12" /><line x1="12" y1="8" x2="12.01" y2="8" /></svg>
                  Overrides open a 16-field legal capture record. Downward acuity changes require a 1.5s confirm-and-hold.
                </p>
              </>
            )}
          </Panel>

          {/* Disposition — the only way a patient leaves the board. */}
          {!departed && (
            <Panel title="Close encounter">
              {!dischargeOpen ? (
                <div className="flex items-center justify-between gap-4 flex-wrap">
                  <p className="text-sm max-w-md" style={{ color: 'var(--text-dim)' }}>
                    This patient stays on the board — across reloads and shift changes — until
                    someone records where they went.
                  </p>
                  <button
                    onClick={() => setDischargeOpen(true)}
                    className="px-5 py-2.5 rounded-lg text-sm font-semibold shrink-0"
                    style={{ background: 'var(--bg-raised)', border: '1px solid var(--line)', color: 'var(--text)' }}
                  >
                    Record disposition
                  </button>
                </div>
              ) : (
                <div className="flex flex-col gap-4">
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                    {DISPOSITIONS.map(d => (
                      <button
                        key={d.value}
                        onClick={() => setDispositionChoice(d.value)}
                        className="text-left px-4 py-3 rounded-xl transition-colors"
                        style={{
                          background: dispositionChoice === d.value ? 'var(--acuity-red-fill)' : 'var(--bg-raised)',
                          border: `1px solid ${dispositionChoice === d.value ? 'var(--mp-red)' : 'var(--line)'}`,
                        }}
                      >
                        <div className="text-sm font-semibold">{d.label}</div>
                        <div className="text-[11px] mt-0.5" style={{ color: 'var(--text-dim)' }}>{d.hint}</div>
                      </button>
                    ))}
                  </div>

                  <div>
                    <label className="text-xs font-semibold uppercase tracking-wider block mb-1.5" style={{ color: 'var(--text-dim)' }}>
                      Note (optional)
                    </label>
                    <input
                      value={dispositionNote}
                      onChange={e => setDispositionNote(e.target.value)}
                      placeholder="Anything the next shift should know"
                      className="w-full px-4 py-2.5 rounded-lg text-sm outline-none"
                      style={{ background: 'var(--bg-raised)', border: '1px solid var(--line)', color: 'var(--text)' }}
                    />
                  </div>

                  <div className="flex items-center gap-3">
                    <button
                      onClick={confirmDischarge}
                      disabled={!dispositionChoice || busy}
                      className="px-6 py-2.5 rounded-lg text-sm font-semibold disabled:opacity-40"
                      style={{ background: 'var(--mp-red)', color: '#fff' }}
                    >
                      {busy ? 'Saving…' : 'Close and remove from board'}
                    </button>
                    <button
                      onClick={() => { setDischargeOpen(false); setDispositionChoice(null); }}
                      className="text-sm font-medium"
                      style={{ color: 'var(--text-dim)' }}
                    >
                      Cancel
                    </button>
                  </div>
                </div>
              )}
            </Panel>
          )}
        </div>

        {/* RIGHT */}
        <aside className="lg:col-span-4 flex flex-col gap-6">
          <section>
            <div className="flex items-center justify-between mb-3 ml-1">
              <div className="flex items-center gap-2">
                <h2 className="text-[11px] font-semibold uppercase tracking-wider" style={{ color: 'var(--text-dim)' }}>Vital Signs</h2>
                <span className="text-[10px] font-bold uppercase" style={{ color: 'var(--text-dim)' }}>({encounter.measurements.length})</span>
              </div>
              {!departed && (
                <button
                  onClick={() => setShowVitalEntry(true)}
                  className="text-[10px] font-bold px-2.5 py-1 rounded-md uppercase tracking-wider transition-colors"
                  style={{ background: 'var(--acuity-red-fill)', border: '1px solid var(--mp-red)', color: 'var(--mp-red)' }}
                >
                  + Record
                </button>
              )}
            </div>
            <div className="flex flex-col gap-2">
              {encounter.measurements.map(m => (
                <VitalChip
                  key={m.code}
                  m={m}
                  stratum={encounter.ageStratum}
                  stratumInferred={encounter.ageStratumInferred}
                />
              ))}
              {encounter.measurements.length === 0 && (
                <p className="text-sm px-1 py-3" style={{ color: 'var(--text-dim)' }}>
                  No measurements recorded yet.
                </p>
              )}
            </div>
          </section>

          <Panel title="Re-Assessment Cadence">
            <CadenceStrip cadence={encounter.cadence} simNowMs={simNowMs} />
          </Panel>
        </aside>
      </main>

      {overrideTarget && (
        <OverrideDialog
          encounter={encounter}
          score={score}
          targetBand={overrideTarget}
          onCancel={() => setOverrideTarget(null)}
          onConfirm={async (payload) => {
            const rec = await api.decide({
              encounterId: encounter.encounterId,
              action: 'override',
              band: payload.band,
              reasonCode: payload.reasonCode,
              reasonText: payload.reasonText,
              factorsShown: payload.factorsShown,
              scoreAtDecision: payload.scoreAtDecision,
              clinicianId: 'demo-nurse-01',
              clinicianRole: 'triage-nurse',
            });
            setOverrideTarget(null);
            setNotice(`Signed into ledger · ${payload.band} · hash ${rec.hash?.slice(0, 8)}…`);
          }}
        />
      )}

      {showVitalEntry && (
        <VitalEntryDialog
          encounterId={encounter.encounterId}
          requiredVitals={encounter.requiredVitals}
          ageStratum={encounter.ageStratum}
          onClose={() => setShowVitalEntry(false)}
          onSubmitted={(updatedEncounter) => {
            setEncounter(updatedEncounter);
            setNotice(`Vitals recorded for ${updatedEncounter.token}. Cadence reset.`);
          }}
        />
      )}
    </div>
  );
}
