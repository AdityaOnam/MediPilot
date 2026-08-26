'use client';

import { useEffect, useMemo, useRef, useState } from 'react';
import Link from 'next/link';
import { motion, LayoutGroup } from 'motion/react';
import { api } from '@/lib/api/client';
import type { Encounter, Band } from '@/lib/api/types';
import { BAND_RANK } from '@/lib/api/types';
import { isGlobalMuted, setGlobalMute } from '@/lib/voice/audio';

const R_MIN = 10;
const R_MAX = 1000;

export default function ControlPage() {
  const [R, setR] = useState(500);
  const [pStar, setPStar] = useState(1 / (1 + 500));
  const [moved, setMoved] = useState({ up: 0, down: 0 });
  const [muted, setMuted] = useState(false); // will init in useEffect
  const [totalMoved, setTotalMoved] = useState({ up: 0, down: 0 });
  const [census, setCensus] = useState<Encounter[]>([]);
  const [clockSpeed, setClockSpeed] = useState(1);
  const [surgeActive, setSurgeActive] = useState(false);
  const [flash, setFlash] = useState<string | null>(null);
  const flashTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const debounce = useRef<ReturnType<typeof setTimeout> | null>(null);

  // Initial census + light polling to catch the ticker's escalations.
  useEffect(() => {
    setMuted(isGlobalMuted());
  }, []);

  function toggleMute() {
    const next = !muted;
    setGlobalMute(next);
    setMuted(next);
  }

  function dispatchScriptedVoice() {
    window.dispatchEvent(new CustomEvent('synthetic-speech', {
      detail: { finalTranscript: "mild chest discomfort, probably just acidity" }
    }));
  }

  useEffect(() => {
    let cancelled = false;
    const refresh = () => api.getCensus().then(c => { if (!cancelled) setCensus(c); });
    refresh();
    const iv = setInterval(refresh, 1500);
    return () => { cancelled = true; clearInterval(iv); };
  }, []);

  function applyR(value: number) {
    setR(value);
    if (debounce.current) clearTimeout(debounce.current);
    debounce.current = setTimeout(async () => {
      const result = await api.setR(value);
      setPStar(result.pStar);
      setMoved(result.moved);
      setCensus(result.census);
      if (result.moved.up + result.moved.down > 0) {
        setTotalMoved(t => ({ up: t.up + result.moved.up, down: t.down + result.moved.down }));
        setFlash(`R = ${result.R} · ${result.moved.up} up · ${result.moved.down} down`);
        if (flashTimer.current) clearTimeout(flashTimer.current);
        flashTimer.current = setTimeout(() => setFlash(null), 3000);
      }
    }, 120);
  }

  async function changeClockSpeed(speed: number) {
    setClockSpeed(speed);
    await api.setClockSpeed(speed);
  }

  async function toggleSurge() {
    const newState = await api.setSurge(!surgeActive);
    setSurgeActive(newState.active);
    // Refresh census to show fillers
    const c = await api.getCensus();
    setCensus(c);
  }

  const waiting = useMemo(
    () => census.filter(e => e.state === 'waiting').sort(
      (a, b) => BAND_RANK[b.currentBand ?? 'GREEN'] - BAND_RANK[a.currentBand ?? 'GREEN']
    ),
    [census]
  );

  const counts = useMemo(() => {
    const c = { RED: 0, YELLOW: 0, GREEN: 0, ABSTAINED: 0 };
    for (const e of waiting) {
      if (e.encounterId === 'P-15') c.ABSTAINED++;
      else c[(e.currentBand ?? 'GREEN') as 'RED' | 'YELLOW' | 'GREEN']++;
    }
    return c;
  }, [waiting]);

  return (
    <div data-surface="clinical" className="min-h-screen flex flex-col bg-[#0A0D14] text-white selection:bg-[#58A6FF]/30 font-sans">
      {/* HEADER */}
      <header className="flex items-center justify-between px-6 py-4 border-b border-white/10 bg-[#0A0D14]/90 backdrop-blur-md sticky top-0 z-40">
        <div className="flex items-center gap-4">
          <div>
            <h1 className="text-[13px] font-bold tracking-widest uppercase text-white/90">Control Panel</h1>
            <p className="text-[11px] font-medium text-white/50 tracking-wide mt-0.5">Simulation & Judge Controls</p>
          </div>
          <div className="flex items-center gap-2 px-3 py-1 bg-white/[0.03] border border-white/10 rounded-full ml-4">
            <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 shadow-[0_0_8px_rgba(16,185,129,0.5)] animate-pulse"></span>
            <span className="text-[10px] font-bold tracking-widest uppercase text-emerald-400">Simulation Online</span>
          </div>
        </div>
        <div className="flex items-center gap-4">
          <Link href="/board" className="text-xs font-medium text-[#58A6FF] hover:text-[#3b8fdc] hover:underline underline-offset-4 transition-colors flex items-center gap-1">
            Open Board <span>→</span>
          </Link>
          <span className="px-2 py-1 rounded-md border border-white/10 bg-white/[0.02] tracking-widest text-[10px] uppercase text-white/50 font-semibold">
            SIMULATED DATA
          </span>
        </div>
      </header>

      {/* MAIN GRID */}
      <main className="flex-1 p-6 max-w-[1600px] w-full mx-auto">
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 items-start">
          
          {/* LEFT COLUMN: Core Interactions */}
          <div className="lg:col-span-8 flex flex-col gap-6">
            
            {/* HERO CONTROL: COST RATIO R */}
            <section className="rounded-xl border border-white/10 bg-[#11141D] shadow-sm flex flex-col overflow-hidden">
              {/* Top Panel */}
              <div className="p-6 border-b border-white/5">
                <div className="flex justify-between items-start mb-6">
                  <div>
                    <h2 className="text-sm font-bold tracking-wider uppercase text-white/90">Cost Ratio R</h2>
                    <p className="text-xs font-medium text-[#58A6FF] mt-1">Escalation bias</p>
                  </div>
                  <div className="text-right flex flex-col items-end">
                    <div className="text-[10px] font-bold tracking-widest uppercase text-white/40 mb-1">Current Value</div>
                    <div className="text-3xl font-bold tabular-nums tracking-tighter text-[#58A6FF]">R = {R}</div>
                    <div className="text-[11px] font-mono text-white/40 mt-1">
                      p* = 1 / (1 + R) = <span className="text-white/80">{pStar.toFixed(4)}</span>
                    </div>
                  </div>
                </div>

                <div className="space-y-1.5 mb-8">
                  <p className="text-[13px] text-white/60">
                    <span className="text-white/90 font-medium">Higher R</span> → missing a case is more costly (threshold lower, escalate more)
                  </p>
                  <p className="text-[13px] text-white/60">
                    <span className="text-white/90 font-medium">Lower R</span> → false alarms are more costly (threshold higher, escalate fewer)
                  </p>
                </div>

                {/* Slider */}
                <div className="px-2">
                  <div className="relative mb-2">
                    <input
                      type="range"
                      min={R_MIN}
                      max={R_MAX}
                      value={R}
                      onChange={e => applyR(Number(e.target.value))}
                      className="w-full h-1.5 accent-[#58A6FF] bg-white/10 rounded-full appearance-none cursor-pointer focus:outline-none focus:ring-2 focus:ring-[#58A6FF]/50"
                      aria-label="Cost ratio R"
                    />
                  </div>
                  <div className="flex justify-between items-start mt-2">
                    <div className="flex flex-col items-start cursor-pointer group" onClick={() => applyR(50)}>
                      <div className="w-0.5 h-2 bg-white/20 mb-1 group-hover:bg-[#58A6FF] transition-colors"></div>
                      <span className="text-[11px] font-mono text-white/40 group-hover:text-[#58A6FF] transition-colors">50</span>
                      <span className="text-[10px] text-white/30 font-medium mt-0.5 group-hover:text-white/60">Aggressive</span>
                    </div>
                    <div className="flex flex-col items-center cursor-pointer group" onClick={() => applyR(100)}>
                      <div className="w-0.5 h-2 bg-white/20 mb-1 group-hover:bg-[#58A6FF] transition-colors"></div>
                      <span className="text-[11px] font-mono text-white/40 group-hover:text-[#58A6FF] transition-colors">100</span>
                      <span className="text-[10px] text-white/30 font-medium mt-0.5 group-hover:text-white/60">District</span>
                    </div>
                    <div className="flex flex-col items-center cursor-pointer group" onClick={() => applyR(500)}>
                      <div className="w-0.5 h-2 bg-white/20 mb-1 group-hover:bg-[#58A6FF] transition-colors"></div>
                      <span className="text-[11px] font-mono text-white/40 group-hover:text-[#58A6FF] transition-colors">500</span>
                      <span className="text-[10px] text-white/30 font-medium mt-0.5 group-hover:text-white/60">Tertiary</span>
                    </div>
                  </div>
                </div>
              </div>

              {/* Stats Strip */}
              <div className="grid grid-cols-3 divide-x divide-white/5 bg-[#0A0D14]">
                <div className="p-4">
                  <div className="text-[10px] font-bold tracking-widest uppercase text-white/40 mb-2">Crossed Up</div>
                  <div className="flex items-end justify-between">
                    <div className="text-2xl font-bold tabular-nums text-amber-500">{moved.up}</div>
                    <div className="text-[11px] text-white/40 font-medium mb-1">This move</div>
                  </div>
                </div>
                <div className="p-4">
                  <div className="text-[10px] font-bold tracking-widest uppercase text-white/40 mb-2">Crossed Down</div>
                  <div className="flex items-end justify-between">
                    <div className="text-2xl font-bold tabular-nums text-white/20">{moved.down}</div>
                    <div className="text-[11px] text-emerald-500/70 font-medium mb-1 flex items-center gap-1">
                      <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5"><rect x="3" y="11" width="18" height="11" rx="2" ry="2"/><path d="M7 11V7a5 5 0 0 1 10 0v4"/></svg>
                      Structurally 0
                    </div>
                  </div>
                </div>
                <div className="p-4">
                  <div className="text-[10px] font-bold tracking-widest uppercase text-white/40 mb-2">Session Total</div>
                  <div className="flex items-end justify-between">
                    <div className="text-2xl font-bold tabular-nums text-white/90">{totalMoved.up + totalMoved.down}</div>
                    <div className="text-[11px] text-white/40 font-medium mb-1 tabular-nums">{totalMoved.up} up · {totalMoved.down} down</div>
                  </div>
                </div>
              </div>
            </section>

            {/* SYSTEM CONSTRAINT ANNOTATION */}
            <div className="flex items-start gap-3 p-4 rounded-xl border border-[#58A6FF]/20 bg-[#58A6FF]/[0.02]">
              <div className="mt-0.5 text-[#58A6FF]">
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round"><circle cx="12" cy="12" r="10"/><line x1="12" y1="16" x2="12" y2="12"/><line x1="12" y1="8" x2="12.01" y2="8"/></svg>
              </div>
              <div>
                <h3 className="text-[11px] font-bold tracking-widest uppercase text-[#58A6FF] mb-1">System Constraint</h3>
                <p className="text-[13px] text-white/70 leading-relaxed font-medium">
                  <span className="text-white">Zero downward moves.</span> De-escalation is not available to the optimiser — Invariant 1 binds the threshold, not the reverse.
                </p>
              </div>
            </div>

            {/* LIVE CENSUS */}
            <section className="rounded-xl border border-white/10 bg-[#11141D] shadow-sm flex flex-col">
              <div className="p-4 border-b border-white/5 flex flex-col sm:flex-row sm:items-center justify-between gap-4">
                <div className="flex items-center gap-4">
                  <h2 className="text-sm font-bold tracking-wider uppercase text-white/90">Live Census</h2>
                  <span className="px-2 py-0.5 rounded text-[10px] font-bold tracking-widest uppercase bg-white/5 text-white/50">{waiting.length} Patients</span>
                </div>
                <div className="flex items-center gap-4 text-[11px] font-bold tracking-widest uppercase tabular-nums">
                  <span className="text-red-500">RED {counts.RED}</span>
                  <span className="text-amber-500">YELLOW {counts.YELLOW}</span>
                  <span className="text-emerald-500">GREEN {counts.GREEN}</span>
                  <span className="text-purple-500">ABSTAINED {counts.ABSTAINED}</span>
                </div>
              </div>
              <div className="p-4 min-h-[200px]">
                <LayoutGroup>
                  <div className="grid grid-cols-3 sm:grid-cols-4 md:grid-cols-5 lg:grid-cols-6 xl:grid-cols-8 gap-3">
                    {waiting.map(e => (
                      <motion.div
                        key={e.encounterId}
                        layout
                        transition={{ type: 'spring', stiffness: 260, damping: 24 }}
                      >
                        <MiniCard e={e} />
                      </motion.div>
                    ))}
                  </div>
                </LayoutGroup>
                {waiting.length === 0 && (
                  <div className="flex items-center justify-center h-32 text-sm text-white/30 font-medium">
                    No active patients in census.
                  </div>
                )}
              </div>
            </section>

          </div>

          {/* RIGHT COLUMN: Supporting Controls */}
          <div className="lg:col-span-4 flex flex-col gap-6">

            {/* SIMULATION STATUS */}
            <section className="rounded-xl border border-white/10 bg-[#11141D] shadow-sm p-5">
              <h2 className="text-[11px] font-bold tracking-widest uppercase text-white/40 mb-4">Simulation Status</h2>
              <div className="space-y-3">
                <div className="flex justify-between items-center border-b border-white/5 pb-2">
                  <span className="text-[13px] text-white/60">Engine</span>
                  <span className="text-[13px] font-medium text-emerald-400 flex items-center gap-1.5">
                    <span className="w-1.5 h-1.5 rounded-full bg-emerald-400"></span> Running
                  </span>
                </div>
                <div className="flex justify-between items-center border-b border-white/5 pb-2">
                  <span className="text-[13px] text-white/60">Patients</span>
                  <span className="text-[13px] font-medium text-white/90 tabular-nums">{waiting.length}</span>
                </div>
                <div className="flex justify-between items-center border-b border-white/5 pb-2">
                  <span className="text-[13px] text-white/60">Arrival Rate</span>
                  <span className={`text-[13px] font-medium tabular-nums ${surgeActive ? 'text-amber-500' : 'text-white/90'}`}>
                    {surgeActive ? '3× Surge' : '1× Baseline'}
                  </span>
                </div>
                <div className="flex justify-between items-center border-b border-white/5 pb-2">
                  <span className="text-[13px] text-white/60">Cost Ratio (R)</span>
                  <span className="text-[13px] font-mono text-[#58A6FF]">{R}</span>
                </div>
                <div className="flex justify-between items-center">
                  <span className="text-[13px] text-white/60">Clock Speed</span>
                  <span className="text-[13px] font-medium text-white/90 tabular-nums">{clockSpeed}×</span>
                </div>
              </div>
            </section>

            {/* SIMULATION CLOCK */}
            <section className="rounded-xl border border-white/10 bg-[#11141D] shadow-sm p-5">
              <div className="flex justify-between items-start mb-4">
                <h2 className="text-[11px] font-bold tracking-widest uppercase text-white/40">Simulation Clock</h2>
                <span className="text-[10px] font-bold tracking-widest uppercase text-white/20">Speed</span>
              </div>
              <div className="flex bg-[#0A0D14] border border-white/5 rounded-lg p-1 mb-3">
                {[1, 10, 30, 60, 180].map(s => (
                  <button
                    key={s}
                    onClick={() => changeClockSpeed(s)}
                    className={`flex-1 py-1.5 text-xs font-semibold rounded-md transition-all ${
                      clockSpeed === s
                        ? 'bg-white/10 text-white shadow-sm'
                        : 'text-white/40 hover:text-white/70 hover:bg-white/[0.02]'
                    }`}
                  >
                    {s}×
                  </button>
                ))}
              </div>
              <div className="flex justify-between items-center text-[11px] text-white/50 font-medium">
                <span>3-hour ED shift</span>
                <span className="tabular-nums">{(180 / clockSpeed).toFixed(1)} mins real-time</span>
              </div>
            </section>

            {/* SURGE CONTROL */}
            <section className="rounded-xl border border-white/10 bg-[#11141D] shadow-sm p-5">
              <h2 className="text-[11px] font-bold tracking-widest uppercase text-white/40 mb-4">Surge Simulation (P6)</h2>
              <div className="space-y-3 mb-5">
                <p className="text-[13px] text-white/70 leading-relaxed font-medium">
                  <span className="text-white">Arrival rate: 3× baseline.</span><br/>
                  Department load reaches the routing layer only. Risk scores remain unchanged.
                </p>
              </div>
              <button
                onClick={toggleSurge}
                className={`w-full py-3 rounded-lg text-[13px] font-bold uppercase tracking-wider transition-all border ${
                  surgeActive
                    ? 'border-amber-500/50 bg-amber-500/10 text-amber-500 hover:bg-amber-500/20'
                    : 'border-white/10 bg-[#0A0D14] text-amber-500 hover:bg-white/[0.02] hover:border-amber-500/30'
                }`}
              >
                {surgeActive ? 'Deactivate Surge' : 'Activate ×3'}
              </button>
            </section>

            {/* VOICE CONTROLS */}
            <section className="rounded-xl border border-white/10 bg-[#11141D] shadow-sm p-5">
              <div className="flex justify-between items-start mb-4">
                <h2 className="text-[11px] font-bold tracking-widest uppercase text-white/40">Voice Controls (P7)</h2>
                <span className="text-[10px] font-bold tracking-widest uppercase text-white/20">Demo Mode</span>
              </div>
              <div className="space-y-4">
                <div>
                  <div className="text-[11px] font-semibold text-white/40 mb-2">Synthetic STT Injection</div>
                  <button
                    onClick={dispatchScriptedVoice}
                    className="w-full py-2.5 rounded-lg text-[13px] font-semibold border border-white/10 bg-[#0A0D14] text-[#58A6FF] hover:bg-white/[0.02] transition-colors"
                  >
                    Inject: "Mild chest discomfort"
                  </button>
                </div>
                <div>
                  <div className="text-[11px] font-semibold text-white/40 mb-2">Audio</div>
                  <button
                    onClick={toggleMute}
                    className={`w-full py-2.5 rounded-lg text-[13px] font-semibold border transition-colors ${
                      muted 
                        ? 'border-red-500/30 bg-red-500/5 text-red-500' 
                        : 'border-white/10 bg-[#0A0D14] text-white/70 hover:bg-white/[0.02]'
                    }`}
                  >
                    {muted ? '🔇 Sound muted' : '🔊 Sound enabled'}
                  </button>
                </div>
              </div>
            </section>

          </div>
        </div>
      </main>
    </div>
  );
}

function MiniCard({ e }: { e: Encounter }) {
  const abstained = e.encounterId === 'P-15';
  const band = e.currentBand;
  
  // Tailwind mapping based on status
  const borderClass = abstained ? 'border-purple-500/30' 
    : band === 'RED' ? 'border-red-500/30'
    : band === 'YELLOW' ? 'border-amber-500/30'
    : 'border-emerald-500/30';

  const stripeClass = abstained ? 'bg-purple-500' 
    : band === 'RED' ? 'bg-red-500'
    : band === 'YELLOW' ? 'bg-amber-500'
    : 'bg-emerald-500';

  const textClass = abstained ? 'text-purple-400' 
    : band === 'RED' ? 'text-red-400'
    : band === 'YELLOW' ? 'text-amber-400'
    : 'text-emerald-400';

  const label = abstained ? 'ABSTAIN' 
    : band === 'RED' ? 'RED'
    : band === 'YELLOW' ? 'YELLOW'
    : 'GREEN';

  return (
    <Link
      href={`/card/${e.encounterId}`}
      className={`block relative overflow-hidden rounded-lg border bg-[#0A0D14] hover:bg-white/[0.02] hover:-translate-y-0.5 transition-all shadow-sm ${borderClass} group`}
      title={e.chiefComplaint ?? ''}
    >
      <div className={`absolute left-0 top-0 bottom-0 w-1 ${stripeClass}`}></div>
      <div className="p-2.5 pl-3">
        <div className="flex justify-between items-start mb-1">
          <div className="text-[11px] font-mono font-medium text-white/60">{e.encounterId}</div>
          <div className={`text-[9px] font-bold tracking-widest uppercase ${textClass}`}>{label}</div>
        </div>
        <div className="text-base font-bold tabular-nums text-white/90">{e.token}</div>
      </div>
    </Link>
  );
}
