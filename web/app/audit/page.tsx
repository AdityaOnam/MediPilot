'use client';

import { useEffect, useMemo, useState } from 'react';
import { api } from '@/lib/api/client';
import type { OverrideRecord, SiteConfig } from '@/lib/api/types';
import { BandChip } from '@/components/clinical/BandChip';

type Filter = 'all' | 'overrides' | 'downward' | 'escalations';

export default function AuditPage() {
  const [records, setRecords] = useState<OverrideRecord[]>([]);
  const [config, setConfig] = useState<SiteConfig | null>(null);
  const [filter, setFilter] = useState<Filter>('all');
  const [expanded, setExpanded] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    const load = () => Promise.all([api.getAudit(), api.getConfig()]).then(([a, c]) => {
      if (!cancelled) { setRecords(a); setConfig(c); }
    });
    load();
    const iv = setInterval(load, 2000);
    return () => { cancelled = true; clearInterval(iv); };
  }, []);

  const filtered = useMemo(() => records.filter(r => {
    if (filter === 'downward') return r.direction === 'de-escalation';
    if (filter === 'escalations') return r.direction === 'escalation';
    if (filter === 'overrides') return r.systemBand !== r.clinicianBand;
    return true;
  }), [records, filter]);

  // Verify the chain — head to tail in reverse-time order.
  const chainValid = useMemo(() => {
    const asc = [...records].reverse();
    for (let i = 1; i < asc.length; i++) {
      if (asc[i].prevHash !== asc[i - 1].hash) return false;
    }
    return true;
  }, [records]);

  function exportJson() {
    const blob = new Blob([JSON.stringify(records, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `medipilot-audit-${new Date().toISOString().slice(0, 19).replace(/:/g, '')}.json`;
    a.click();
    URL.revokeObjectURL(url);
  }

  return (
    <div data-surface="clinical" className="min-h-screen flex flex-col bg-[#0A0D14] text-white selection:bg-[#58A6FF]/30 font-sans">
      <header className="flex items-center justify-between px-6 py-4 border-b border-white/10 bg-[#0A0D14]/90 backdrop-blur-md sticky top-0 z-40">
        <div className="flex items-center gap-4">
          <div>
            <h1 className="text-[13px] font-bold tracking-widest uppercase text-white/90">Audit Ledger</h1>
            <p className="text-[11px] font-medium text-white/50 tracking-wide mt-0.5">
              Override records rendered verbatim · hash-chained · <span className="text-white/80 tabular-nums">{records.length} rows</span>
            </p>
          </div>
          <div className={`flex items-center gap-2 px-3 py-1 bg-white/[0.03] border rounded-full ml-4 ${chainValid ? 'border-emerald-500/30' : 'border-red-500/50'}`}>
            <span className={`w-1.5 h-1.5 rounded-full ${chainValid ? 'bg-emerald-500 shadow-[0_0_8px_rgba(16,185,129,0.5)]' : 'bg-red-500 animate-pulse'}`}></span>
            <span className={`text-[10px] font-bold tracking-widest uppercase ${chainValid ? 'text-emerald-400' : 'text-red-400'}`}>
              {chainValid ? 'Chain Valid' : 'Chain Broken'}
            </span>
          </div>
        </div>
      </header>

      <main className="flex-1 p-6 max-w-[1600px] w-full mx-auto">
        {/* Model card */}
        {config && (
          <section className="rounded-xl border border-white/10 bg-[#11141D] shadow-sm mb-6 flex flex-col sm:flex-row overflow-hidden">
            <div className="p-4 sm:p-5 sm:border-r border-white/10 bg-white/[0.02] flex items-center justify-center sm:min-w-[140px]">
              <h2 className="text-[11px] font-bold tracking-widest uppercase text-white/40">Model Card</h2>
            </div>
            <div className="flex-1 p-4 sm:p-5 grid grid-cols-2 sm:grid-cols-4 gap-6 text-[13px]">
              <div>
                <div className="text-[10px] font-bold tracking-widest uppercase text-white/40 mb-1">Model</div>
                <div className="font-mono text-white/90">{config.modelVersion}</div>
              </div>
              <div>
                <div className="text-[10px] font-bold tracking-widest uppercase text-white/40 mb-1">Calibration</div>
                <div className="font-mono text-white/90">{config.calibrationVersion}</div>
              </div>
              <div>
                <div className="text-[10px] font-bold tracking-widest uppercase text-white/40 mb-1">Cost Ratio R</div>
                <div className="font-mono text-[#58A6FF] tabular-nums">{config.costRatioR}</div>
              </div>
              <div>
                <div className="text-[10px] font-bold tracking-widest uppercase text-white/40 mb-1">p* Threshold</div>
                <div className="font-mono text-white/90 tabular-nums">{(1 / (1 + config.costRatioR)).toFixed(4)}</div>
              </div>
            </div>
          </section>
        )}

        {/* Filters + export */}
        <div className="flex items-center justify-between mb-6 flex-wrap gap-4">
          <div className="flex bg-[#11141D] border border-white/10 rounded-lg p-1">
            {(['all', 'overrides', 'downward', 'escalations'] as Filter[]).map(f => (
              <button
                key={f}
                onClick={() => setFilter(f)}
                className={`px-4 py-1.5 text-xs font-semibold rounded-md transition-all capitalize ${
                  filter === f
                    ? 'bg-white/10 text-white shadow-sm'
                    : 'text-white/40 hover:text-white/70 hover:bg-white/[0.02]'
                }`}
              >
                {f}
              </button>
            ))}
          </div>
          <button
            onClick={exportJson}
            disabled={records.length === 0}
            className="px-4 py-2 rounded-lg text-xs font-bold uppercase tracking-wider border border-white/20 bg-white/[0.03] text-white hover:bg-white/[0.08] hover:border-white/30 disabled:opacity-30 disabled:cursor-not-allowed transition-all shadow-sm flex items-center gap-2"
          >
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/></svg>
            Export JSON
          </button>
        </div>

        {/* Records */}
        {filtered.length === 0 ? (
          <div className="p-12 text-center rounded-xl border border-white/10 bg-[#11141D] shadow-sm flex flex-col items-center justify-center">
            <svg className="w-8 h-8 text-white/20 mb-3" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="1.5"><path strokeLinecap="round" strokeLinejoin="round" d="M19.5 14.25v-2.625a3.375 3.375 0 00-3.375-3.375h-1.5A1.125 1.125 0 0113.5 7.125v-1.5a3.375 3.375 0 00-3.375-3.375H8.25m2.25 0H5.625c-.621 0-1.125.504-1.125 1.125v17.25c0 .621.504 1.125 1.125 1.125h12.75c.621 0 1.125-.504 1.125-1.125V11.25a9 9 0 00-9-9z" /></svg>
            <p className="text-sm text-white/50 font-medium">
              {records.length === 0
                ? 'No overrides recorded yet.'
                : `No rows match "${filter}".`}
            </p>
            {records.length === 0 && (
              <p className="text-xs mt-2 text-white/30 font-medium max-w-sm">
                Override a patient on the board (e.g., P-14) to see the 16-field cryptographic record here.
              </p>
            )}
          </div>
        ) : (
          <div className="space-y-3">
            {filtered.map(r => (
              <RecordRow
                key={r.hash ?? r.timestampUtc}
                r={r}
                expanded={expanded === (r.hash ?? r.timestampUtc)}
                onToggle={() => setExpanded(v => v === (r.hash ?? r.timestampUtc) ? null : (r.hash ?? r.timestampUtc))}
              />
            ))}
          </div>
        )}
      </main>
    </div>
  );
}

function RecordRow({ r, expanded, onToggle }: { r: OverrideRecord; expanded: boolean; onToggle: () => void }) {
  const isDown = r.direction === 'de-escalation';
  const changed = r.systemBand !== r.clinicianBand;

  return (
    <div className="rounded-xl border border-white/10 bg-[#11141D] shadow-sm overflow-hidden transition-colors hover:border-white/20">
      <button
        onClick={onToggle}
        className="w-full p-4 sm:px-6 flex items-center gap-4 text-left bg-transparent transition-colors hover:bg-white/[0.02]"
        aria-expanded={expanded}
      >
        <span className="text-xs font-mono tabular-nums text-white/40 w-32 shrink-0">
          {new Date(r.timestampUtc).toLocaleTimeString()}
        </span>
        <span className="font-bold font-mono tabular-nums text-white w-12 shrink-0">{r.patientId}</span>
        
        <div className="flex items-center gap-3 shrink-0">
          <div className="opacity-70"><BandChip band={r.systemBand} size="sm" /></div>
          <span className="text-white/30 font-mono">→</span>
          <BandChip band={r.clinicianBand} size="sm" />
        </div>

        {changed && (
          <span
            className={`text-[9px] px-2 py-0.5 rounded font-bold uppercase tracking-widest shrink-0 border ${
              isDown 
                ? 'text-red-400 border-red-500/30 bg-red-500/10' 
                : 'text-amber-400 border-amber-500/30 bg-amber-500/10'
            }`}
          >
            {r.direction}
          </span>
        )}
        
        <span className="text-xs flex-1 truncate text-white/40 font-medium pl-2 hidden sm:block">
          {r.reasonCode}
        </span>
        
        <span className="text-[10px] font-mono text-white/30 shrink-0 hidden md:flex items-center gap-1.5">
          <span>{r.prevHash ? r.prevHash.slice(0, 6) : 'genesis'}</span>
          <span className="text-white/20">→</span>
          <span className="text-white/50">{r.hash?.slice(0, 6)}</span>
        </span>
        
        <span aria-hidden className={`text-white/30 transition-transform ${expanded ? 'rotate-180' : ''}`}>
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5"><polyline points="6 9 12 15 18 9"/></svg>
        </span>
      </button>

      {expanded && (
        <div className="bg-[#0A0D14] p-5 sm:p-6 border-t border-white/10 font-mono text-[11px] space-y-1.5 overflow-x-auto shadow-inner">
          <VerbatimRow k="patientId"          v={r.patientId} />
          <VerbatimRow k="timestampUtc"       v={r.timestampUtc} />
          <VerbatimRow k="clinicianId"        v={r.clinicianId} />
          <VerbatimRow k="clinicianRole"      v={r.clinicianRole} />
          <VerbatimRow k="systemBand"         v={r.systemBand} />
          <VerbatimRow k="clinicianBand"      v={r.clinicianBand} />
          <VerbatimRow k="direction"          v={r.direction} />
          <VerbatimRow k="reasonCode"         v={r.reasonCode} />
          <VerbatimRow k="reasonText"         v={r.reasonText || 'null'} />
          <VerbatimRow k="score"              v={r.score.toFixed(3)} />
          <VerbatimRow k="confidence"         v={r.confidence} />
          <VerbatimRow k="factorsShown"       v={`[${r.factorsShown.length} factors as displayed]`} />
          <FactorsBlock factors={r.factorsShown} />
          <VerbatimRow k="inputsHash"         v={r.inputsHash} />
          <VerbatimRow k="modelVersion"       v={r.modelVersion} />
          <VerbatimRow k="calibrationVersion" v={r.calibrationVersion} />
          <VerbatimRow k="consentState"       v={r.consentState} />
          <VerbatimRow k="outcomeRef"         v={r.outcomeRef ?? 'null'} />
          <div className="mt-4 pt-4 border-t border-white/10 flex flex-col gap-1.5">
            <VerbatimRow k="prevHash"         v={r.prevHash ?? 'null (genesis)'} />
            <VerbatimRow k="hash"             v={r.hash ?? 'null'} />
          </div>
        </div>
      )}
    </div>
  );
}

function VerbatimRow({ k, v }: { k: string; v: string }) {
  const isNull = v === 'null' || v === 'null (genesis)';
  return (
    <div className="flex gap-4 py-0.5 hover:bg-white/[0.02] rounded px-2 -mx-2 transition-colors">
      <span className="min-w-[160px] shrink-0 text-[#58A6FF]/70 select-none">{k}:</span>
      <span className={`flex-1 break-all ${isNull ? 'text-white/20 italic' : 'text-white/80'}`}>
        {isNull ? v : `"${v}"`}
      </span>
    </div>
  );
}

function FactorsBlock({ factors }: { factors: OverrideRecord['factorsShown'] }) {
  if (factors.length === 0) return null;
  return (
    <div className="ml-[176px] pl-4 py-2 border-l border-white/10 space-y-1.5">
      {factors.map((f, i) => (
        <div key={i} className="flex gap-3 text-[10px]">
          <span className={f.direction === 'supports' ? 'text-amber-500' : 'text-emerald-500'}>
            {f.direction === 'supports' ? '++' : '--'}
          </span>
          <span className="text-white/70">"{f.label}"</span>
          <span className="text-white/30 shrink-0">
            src: {f.source} | mag: {f.magnitude.toFixed(2)}
          </span>
        </div>
      ))}
    </div>
  );
}
