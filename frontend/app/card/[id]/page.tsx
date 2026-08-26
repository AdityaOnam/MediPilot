'use client';

import { useEffect, useState } from 'react';
import Link from 'next/link';
import { useParams } from 'next/navigation';
import { api } from '@/lib/api/client';
import type { Encounter, ScoreResponse, Band } from '@/lib/api/types';
import { AcuityCard } from '@/components/clinical/AcuityCard';
import { AbstentionCard } from '@/components/clinical/AbstentionCard';
import { VitalChip } from '@/components/clinical/VitalChip';
import { LockedAcuitySlot } from '@/components/clinical/LockedAcuitySlot';
import { CadenceStrip } from '@/components/clinical/CadenceStrip';
import { OverrideDialog } from '@/components/clinical/OverrideDialog';
import { VitalEntryDialog } from '@/components/clinical/VitalEntryDialog';
import { stratumLabel } from '@/lib/clinical/ageBands';

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

  function beginOverride(newBand: Band) {
    if (!encounter || !score) return;
    if (newBand === score.effectiveBand) return;
    setOverrideTarget(newBand);
  }

  if (!encounter || !score) {
    return (
      <div data-surface="clinical" className="min-h-screen flex items-center justify-center" style={{ background: 'var(--bg)', color: 'var(--text-dim)' }}>
        Loading encounter {id}…
      </div>
    );
  }

  return (
    <div data-surface="clinical" className="min-h-screen bg-[#0A0D14] text-white/80 pb-20 font-sans selection:bg-[#58A6FF]/30">
      {/* Restrained Clinical Header */}
      <header className="border-b border-white/10 bg-[#0A0D14]/95 px-6 py-4 sticky top-0 z-40">
        <div className="max-w-7xl mx-auto flex items-center justify-between">
          <div className="flex items-center gap-6">
            <Link href="/board" className="text-[13px] font-semibold text-white/50 hover:text-white transition-colors flex items-center gap-1.5 uppercase tracking-wide">
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5"><path d="M19 12H5M12 19l-7-7 7-7"/></svg>
              Board
            </Link>
            <div className="w-px h-6 bg-white/10" />
            <div className="flex items-center gap-4">
              <h1 className="text-xl font-medium tracking-tight text-white">Token {encounter.token}</h1>
              <div className="flex gap-2">
                <span className="px-2 py-0.5 rounded-md bg-white/5 border border-white/10 text-xs font-medium text-white/70 capitalize">
                  {stratumLabel(encounter.ageStratum, encounter.ageStratumInferred)}
                </span>
                {encounter.sex && (
                  <span className="px-2 py-0.5 rounded-md bg-white/5 border border-white/10 text-xs font-medium text-white/70 capitalize">
                    {encounter.sex}
                  </span>
                )}
                <span className="px-2 py-0.5 rounded-md bg-[#58A6FF]/10 border border-[#58A6FF]/20 text-xs font-medium text-[#58A6FF] capitalize">
                  {encounter.arrivalMode.replace(/-/g, ' ')}
                </span>
              </div>
            </div>
          </div>

          <div className="flex items-center gap-6">
            <div className="flex items-center gap-2">
              <span className="w-2 h-2 rounded-full bg-[#10B981]" />
              <div className="flex flex-col">
                <span className="text-[11px] font-semibold uppercase tracking-wider text-white/70 leading-none">Continuous Re-Triage</span>
                <span className="text-[10px] text-white/40 leading-none mt-1">Active Monitoring</span>
              </div>
            </div>
            <div className="w-px h-6 bg-white/10 hidden md:block" />
            <div className="hidden md:flex items-center gap-3">
              <span className="text-[11px] text-white/40 font-mono">{score.modelVersion}</span>
              <span className="px-1.5 py-0.5 rounded bg-white/5 text-[10px] font-bold uppercase tracking-wider text-white/30 border border-white/10">Simulated Data</span>
            </div>
          </div>
        </div>
      </header>

      <main className="max-w-7xl mx-auto p-6 grid gap-6 lg:grid-cols-12 mt-2">
        {/* LEFT COLUMN: Clinical Context & Signals */}
        <div className="lg:col-span-8 flex flex-col gap-6">
          
          {/* Chief Complaint Panel */}
          <section className="p-5 rounded-xl border border-white/10 bg-white/[0.02] border-l-2 border-l-[#58A6FF]">
            <div className="flex items-center justify-between mb-3">
              <h2 className="text-[11px] font-semibold uppercase tracking-wider text-white/50 flex items-center gap-2">
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/><line x1="16" y1="13" x2="8" y2="13"/><line x1="16" y1="17" x2="8" y2="17"/><polyline points="10 9 9 9 8 9"/></svg>
                Chief Complaint
              </h2>
              {score.abstained && (
                <span className="text-[10px] font-bold uppercase tracking-wider bg-white/10 px-2 py-0.5 rounded text-white/70">OOD</span>
              )}
            </div>
            <p className="text-base text-white/90 leading-relaxed font-medium">
              {encounter.chiefComplaint ?? '—'}
            </p>
            {!encounter.medicalInfoConsent && (
              <div className="mt-4 flex items-start gap-2 text-xs text-[#F59E0B] bg-[#F59E0B]/10 border border-[#F59E0B]/20 p-2.5 rounded-lg">
                <svg className="w-4 h-4 shrink-0" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/><path d="M12 8v4"/><path d="M12 16h.01"/></svg>
                <span className="font-medium">History sharing declined. Triaged on observation alone. Queue position unaffected.</span>
              </div>
            )}
          </section>

          {/* Clinical Signals */}
          <section>
            <h2 className="text-[11px] font-semibold uppercase tracking-wider text-white/50 mb-3 ml-1">Clinical Signals</h2>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
               {score.abstained && (
                 <div className="p-3.5 rounded-xl border border-white/10 bg-white/[0.02]">
                   <h4 className="text-xs font-semibold text-white/80 mb-1">OOD Presentation</h4>
                   <p className="text-[11px] text-white/40 leading-snug">Patient presentation does not map to known safe corridors.</p>
                 </div>
               )}
               {(!score.confidence || score.confidence === 'low' || score.confidence === 'moderate') && (
                 <div className="p-3.5 rounded-xl border border-white/10 bg-white/[0.02]">
                   <h4 className="text-xs font-semibold text-white/80 mb-1">Low Confidence</h4>
                   <p className="text-[11px] text-white/40 leading-snug">Model inference confidence is below standard threshold.</p>
                 </div>
               )}
               <LockedAcuitySlot />
            </div>
          </section>

          {/* Needs Your Eyes / Acuity */}
          <section>
            {score.abstained ? (
              <AbstentionCard
                reason={score.abstentionReason ?? 'OUT_OF_DISTRIBUTION'}
                effectiveBand="YELLOW"
                unmetReviewBreach={encounter.cadence.breachKind === 'UNMET_REVIEW'}
              />
            ) : (
              <div className="p-5 rounded-xl border border-white/10 bg-white/[0.02]">
                 <h2 className="text-[11px] font-semibold uppercase tracking-wider text-white/50 mb-4">Automated Status</h2>
                 <AcuityCard score={score} />
              </div>
            )}
          </section>

          {/* Nurse Decision Action Panel */}
          <section className="p-5 rounded-xl border border-white/10 bg-white/[0.02] mt-2">
            <h2 className="text-[11px] font-semibold uppercase tracking-wider text-white/50 mb-4">Nurse Decision</h2>
            
            {notice && (
              <div className="mb-4 p-3 rounded-lg border border-[#58A6FF]/30 bg-[#58A6FF]/10 text-[13px] font-medium text-[#58A6FF] flex items-center gap-2">
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5"><path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"/><polyline points="22 4 12 14.01 9 11.01"/></svg>
                {notice}
              </div>
            )}

            <div className="flex flex-wrap items-center gap-3">
              <button
                onClick={accept}
                disabled={busy || score.abstained}
                className="px-6 py-2.5 rounded-lg text-sm font-semibold transition-colors disabled:opacity-50 flex items-center gap-2"
                style={{ background: 'white', color: 'black' }}
              >
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3"><path d="M20 6L9 17l-5-5"/></svg>
                Accept {!score.abstained && score.effectiveBand}
              </button>
              
              <div className="h-6 w-px bg-white/10 mx-1" />
              
              {(['RED','YELLOW','GREEN'] as Band[]).filter(b => b !== score.effectiveBand).map(b => (
                <button
                  key={b}
                  onClick={() => beginOverride(b)}
                  disabled={busy}
                  className="px-4 py-2.5 rounded-lg text-[13px] font-medium border border-white/20 bg-white/5 hover:bg-white/10 transition-colors disabled:opacity-50"
                  style={{ color: b === 'RED' ? '#EF4444' : b === 'YELLOW' ? '#F59E0B' : '#10B981' }}
                >
                  Override to {b}
                </button>
              ))}
            </div>
            
            <p className="text-[11px] text-white/40 mt-4 flex items-start gap-1.5 max-w-lg">
              <svg className="w-3.5 h-3.5 mt-0.5 shrink-0" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><circle cx="12" cy="12" r="10"/><line x1="12" y1="16" x2="12" y2="12"/><line x1="12" y1="8" x2="12.01" y2="8"/></svg>
              Overrides open a 16-field legal capture record. Downward acuity changes require a 1.5s confirm-and-hold.
            </p>
          </section>
        </div>

        {/* RIGHT COLUMN: Vitals & Reassessment */}
        <aside className="lg:col-span-4 flex flex-col gap-6">
          
          <section>
            <div className="flex items-center justify-between mb-3 ml-1">
              <div className="flex items-center gap-2">
                <h2 className="text-[11px] font-semibold uppercase tracking-wider text-white/50">Vital Signs</h2>
                <span className="text-[10px] font-bold text-white/30 uppercase">({encounter.measurements.length})</span>
              </div>
              <button 
                onClick={() => setShowVitalEntry(true)}
                className="text-[10px] font-bold bg-[#58A6FF]/10 text-[#58A6FF] hover:bg-[#58A6FF]/20 px-2.5 py-1 rounded-md uppercase tracking-wider border border-[#58A6FF]/20 transition-colors"
              >
                + Record
              </button>
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
            </div>
          </section>

          <section className="p-5 rounded-xl border border-white/10 bg-white/[0.02]">
            <h2 className="text-[11px] font-semibold uppercase tracking-wider text-white/50 mb-4">Re-Assessment Cadence</h2>
            <CadenceStrip cadence={encounter.cadence} simNowMs={simNowMs} />
          </section>
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
