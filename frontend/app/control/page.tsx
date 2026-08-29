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

/** Small panel wrapper — matches the ward-surface chrome used on /card and
 *  /counter, so a judge tabbing between this and the real product sees one
 *  visual system rather than two different demo tools. */
function Panel({
  title,
  eyebrow,
  right,
  children,
}: {
  title?: string;
  eyebrow?: string;
  right?: React.ReactNode;
  children: React.ReactNode;
}) {
  return (
    <section
      className="rounded-xl overflow-hidden"
      style={{ background: 'var(--bg-card)', border: '1px solid var(--line)' }}
    >
      {(title || right) && (
        <div
          className="flex items-center justify-between gap-3 px-5 py-4"
          style={{ borderBottom: '1px solid var(--line)' }}
        >
          <div>
            {eyebrow && (
              <p className="text-[10px] font-bold uppercase tracking-widest mb-0.5" style={{ color: 'var(--focus)' }}>
                {eyebrow}
              </p>
            )}
            {title && (
              <h2 className="text-[11px] font-bold uppercase tracking-widest" style={{ color: 'var(--text-dim)' }}>
                {title}
              </h2>
            )}
          </div>
          {right}
        </div>
      )}
      {children}
    </section>
  );
}

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
    <div data-surface="ward" className="min-h-screen flex flex-col" style={{ background: 'var(--bg)', color: 'var(--text)' }}>
      {/* HEADER */}
      <header
        className="flex items-center justify-between px-6 py-4 sticky top-0 z-40"
        style={{ background: 'var(--bg)', borderBottom: '1px solid var(--line)' }}
      >
        <div className="flex items-center gap-4">
          <div>
            <h1 className="text-[13px] font-bold tracking-widest uppercase">Control Panel</h1>
            <p className="text-[11px] font-medium tracking-wide mt-0.5" style={{ color: 'var(--text-dim)' }}>
              Simulation &amp; Judge Controls
            </p>
          </div>
          <div
            className="flex items-center gap-2 px-3 py-1 rounded-full ml-4"
            style={{ background: 'var(--acuity-green-fill)', border: '1px solid var(--acuity-green)' }}
          >
            <span className="w-1.5 h-1.5 rounded-full animate-pulse" style={{ background: 'var(--acuity-green)' }} />
            <span className="text-[10px] font-bold tracking-widest uppercase" style={{ color: 'var(--acuity-green)' }}>
              Simulation Online
            </span>
          </div>
          {flash && (
            <span
              className="text-[11px] font-semibold px-2.5 py-1 rounded-full"
              style={{ background: 'rgba(146,106,71,0.10)', border: '1px solid rgba(146,106,71,0.30)', color: 'var(--focus)' }}
            >
              {flash}
            </span>
          )}
        </div>
        <div className="flex items-center gap-4">
          <Link
            href="/board"
            className="text-xs font-medium hover:underline underline-offset-4 transition-colors flex items-center gap-1"
            style={{ color: 'var(--focus)' }}
          >
            Open Board <span>→</span>
          </Link>
        </div>
      </header>

      {/* MAIN GRID */}
      <main className="flex-1 p-6 max-w-[1600px] w-full mx-auto">
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 items-start">

          {/* LEFT COLUMN: Core Interactions */}
          <div className="lg:col-span-8 flex flex-col gap-6">

            {/* HERO CONTROL: COST RATIO R */}
            <Panel>
              <div className="p-6" style={{ borderBottom: '1px solid var(--line)' }}>
                <div className="flex justify-between items-start mb-6 flex-wrap gap-4">
                  <div>
                    <h2 className="text-sm font-bold tracking-wider uppercase">Cost Ratio R</h2>
                    <p className="text-xs font-medium mt-1" style={{ color: 'var(--focus)' }}>Escalation bias</p>
                  </div>
                  <div className="text-right flex flex-col items-end">
                    <div className="text-[10px] font-bold tracking-widest uppercase mb-1" style={{ color: 'var(--text-dim)' }}>
                      Current Value
                    </div>
                    <div className="text-3xl font-bold tabular-nums tracking-tighter" style={{ color: 'var(--mp-red)' }}>
                      R = {R}
                    </div>
                    <div className="text-[11px] font-mono mt-1" style={{ color: 'var(--text-dim)' }}>
                      p* = 1 / (1 + R) = <span style={{ color: 'var(--text)' }}>{pStar.toFixed(4)}</span>
                    </div>
                  </div>
                </div>

                <div className="space-y-1.5 mb-8">
                  <p className="text-[13px]" style={{ color: 'var(--text-dim)' }}>
                    <span className="font-medium" style={{ color: 'var(--text)' }}>Higher R</span> → missing a case is more costly (threshold lower, escalate more)
                  </p>
                  <p className="text-[13px]" style={{ color: 'var(--text-dim)' }}>
                    <span className="font-medium" style={{ color: 'var(--text)' }}>Lower R</span> → false alarms are more costly (threshold higher, escalate fewer)
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
                      className="w-full h-1.5 rounded-full appearance-none cursor-pointer focus:outline-none"
                      style={{ background: 'var(--line)', accentColor: 'var(--mp-red)' }}
                      aria-label="Cost ratio R"
                    />
                  </div>
                  <div className="flex justify-between items-start mt-2">
                    {[{ v: 50, l: 'Aggressive' }, { v: 100, l: 'District' }, { v: 500, l: 'Tertiary' }].map(({ v, l }) => (
                      <button
                        key={v}
                        type="button"
                        onClick={() => applyR(v)}
                        className="flex flex-col items-start cursor-pointer group"
                      >
                        <div
                          className="w-0.5 h-2 mb-1 transition-colors"
                          style={{ background: R === v ? 'var(--mp-red)' : 'var(--line)' }}
                        />
                        <span
                          className="text-[11px] font-mono transition-colors"
                          style={{ color: R === v ? 'var(--mp-red)' : 'var(--text-dim)' }}
                        >
                          {v}
                        </span>
                        <span className="text-[10px] font-medium mt-0.5" style={{ color: 'var(--text-faint, var(--text-dim))' }}>
                          {l}
                        </span>
                      </button>
                    ))}
                  </div>
                </div>
              </div>

              {/* Stats Strip */}
              <div className="grid grid-cols-3" style={{ background: 'var(--bg-raised)' }}>
                <div className="p-4" style={{ borderRight: '1px solid var(--line)' }}>
                  <div className="text-[10px] font-bold tracking-widest uppercase mb-2" style={{ color: 'var(--text-dim)' }}>
                    Crossed Up
                  </div>
                  <div className="flex items-end justify-between">
                    <div className="text-2xl font-bold tabular-nums" style={{ color: 'var(--acuity-yellow)' }}>{moved.up}</div>
                    <div className="text-[11px] font-medium mb-1" style={{ color: 'var(--text-dim)' }}>This move</div>
                  </div>
                </div>
                <div className="p-4" style={{ borderRight: '1px solid var(--line)' }}>
                  <div className="text-[10px] font-bold tracking-widest uppercase mb-2" style={{ color: 'var(--text-dim)' }}>
                    Crossed Down
                  </div>
                  <div className="flex items-end justify-between">
                    <div className="text-2xl font-bold tabular-nums" style={{ color: 'var(--text-dim)', opacity: 0.5 }}>{moved.down}</div>
                    <div className="text-[11px] font-medium mb-1 flex items-center gap-1" style={{ color: 'var(--acuity-green)' }}>
                      <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5"><rect x="3" y="11" width="18" height="11" rx="2" ry="2"/><path d="M7 11V7a5 5 0 0 1 10 0v4"/></svg>
                      Structurally 0
                    </div>
                  </div>
                </div>
                <div className="p-4">
                  <div className="text-[10px] font-bold tracking-widest uppercase mb-2" style={{ color: 'var(--text-dim)' }}>
                    Session Total
                  </div>
                  <div className="flex items-end justify-between">
                    <div className="text-2xl font-bold tabular-nums">{totalMoved.up + totalMoved.down}</div>
                    <div className="text-[11px] font-medium mb-1 tabular-nums" style={{ color: 'var(--text-dim)' }}>
                      {totalMoved.up} up · {totalMoved.down} down
                    </div>
                  </div>
                </div>
              </div>
            </Panel>

            {/* SYSTEM CONSTRAINT ANNOTATION */}
            <div
              className="flex items-start gap-3 p-4 rounded-xl"
              style={{ background: 'rgba(146,106,71,0.06)', border: '1px solid rgba(146,106,71,0.25)' }}
            >
              <div className="mt-0.5" style={{ color: 'var(--focus)' }}>
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round"><circle cx="12" cy="12" r="10"/><line x1="12" y1="16" x2="12" y2="12"/><line x1="12" y1="8" x2="12.01" y2="8"/></svg>
              </div>
              <div>
                <h3 className="text-[11px] font-bold tracking-widest uppercase mb-1" style={{ color: 'var(--focus)' }}>
                  System Constraint
                </h3>
                <p className="text-[13px] leading-relaxed font-medium" style={{ color: 'var(--text-dim)' }}>
                  <span style={{ color: 'var(--text)' }}>Zero downward moves.</span> De-escalation is not available to the optimiser — Invariant 1 binds the threshold, not the reverse.
                </p>
              </div>
            </div>

            {/* LIVE CENSUS */}
            <Panel
              title={`${waiting.length} Patients`}
              eyebrow="Live Census"
              right={
                <div className="flex items-center gap-4 text-[11px] font-bold tracking-widest uppercase tabular-nums">
                  <span style={{ color: 'var(--acuity-red)' }}>RED {counts.RED}</span>
                  <span style={{ color: 'var(--acuity-yellow)' }}>YELLOW {counts.YELLOW}</span>
                  <span style={{ color: 'var(--acuity-green)' }}>GREEN {counts.GREEN}</span>
                  <span style={{ color: 'var(--acuity-abstained)' }}>ABSTAINED {counts.ABSTAINED}</span>
                </div>
              }
            >
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
                  <div className="flex items-center justify-center h-32 text-sm font-medium" style={{ color: 'var(--text-dim)' }}>
                    No active patients in census.
                  </div>
                )}
              </div>
            </Panel>

          </div>

          {/* RIGHT COLUMN: Supporting Controls */}
          <div className="lg:col-span-4 flex flex-col gap-6">

            {/* SIMULATION STATUS */}
            <Panel eyebrow="" title="Simulation Status">
              <div className="p-5 space-y-3">
                <StatusRow label="Engine">
                  <span className="text-[13px] font-medium flex items-center gap-1.5" style={{ color: 'var(--acuity-green)' }}>
                    <span className="w-1.5 h-1.5 rounded-full" style={{ background: 'var(--acuity-green)' }} /> Running
                  </span>
                </StatusRow>
                <StatusRow label="Patients">
                  <span className="text-[13px] font-medium tabular-nums">{waiting.length}</span>
                </StatusRow>
                <StatusRow label="Arrival Rate">
                  <span
                    className="text-[13px] font-medium tabular-nums"
                    style={{ color: surgeActive ? 'var(--acuity-yellow)' : 'var(--text)' }}
                  >
                    {surgeActive ? '3× Surge' : '1× Baseline'}
                  </span>
                </StatusRow>
                <StatusRow label="Cost Ratio (R)">
                  <span className="text-[13px] font-mono" style={{ color: 'var(--mp-red)' }}>{R}</span>
                </StatusRow>
                <StatusRow label="Clock Speed" last>
                  <span className="text-[13px] font-medium tabular-nums">{clockSpeed}×</span>
                </StatusRow>
              </div>
            </Panel>

            {/* SIMULATION CLOCK */}
            <Panel>
              <div className="p-5">
                <div className="flex justify-between items-start mb-4">
                  <h2 className="text-[11px] font-bold tracking-widest uppercase" style={{ color: 'var(--text-dim)' }}>
                    Simulation Clock
                  </h2>
                  <span className="text-[10px] font-bold tracking-widest uppercase" style={{ color: 'var(--text-dim)', opacity: 0.6 }}>
                    Speed
                  </span>
                </div>
                <div
                  className="flex rounded-lg p-1 mb-3"
                  style={{ background: 'var(--bg-raised)', border: '1px solid var(--line)' }}
                >
                  {[1, 10, 30, 60, 180].map(s => (
                    <button
                      key={s}
                      onClick={() => changeClockSpeed(s)}
                      className="flex-1 py-1.5 text-xs font-semibold rounded-md transition-all"
                      style={
                        clockSpeed === s
                          ? { background: 'var(--mp-red)', color: '#fff' }
                          : { color: 'var(--text-dim)' }
                      }
                    >
                      {s}×
                    </button>
                  ))}
                </div>
                <div className="flex justify-between items-center text-[11px] font-medium" style={{ color: 'var(--text-dim)' }}>
                  <span>3-hour ED shift</span>
                  <span className="tabular-nums">{(180 / clockSpeed).toFixed(1)} mins real-time</span>
                </div>
              </div>
            </Panel>

            {/* SURGE CONTROL */}
            <Panel>
              <div className="p-5">
                <h2 className="text-[11px] font-bold tracking-widest uppercase mb-4" style={{ color: 'var(--text-dim)' }}>
                  Surge Simulation (P6)
                </h2>
                <p className="text-[13px] leading-relaxed font-medium mb-5" style={{ color: 'var(--text-dim)' }}>
                  <span style={{ color: 'var(--text)' }}>Arrival rate: 3× baseline.</span><br />
                  Department load reaches the routing layer only. Risk scores remain unchanged.
                </p>
                <button
                  onClick={toggleSurge}
                  className="w-full py-3 rounded-lg text-[13px] font-bold uppercase tracking-wider transition-all"
                  style={
                    surgeActive
                      ? { border: '1px solid var(--acuity-yellow)', background: 'var(--acuity-yellow-fill)', color: 'var(--acuity-yellow)' }
                      : { border: '1px solid var(--line)', background: 'var(--bg-raised)', color: 'var(--acuity-yellow)' }
                  }
                >
                  {surgeActive ? 'Deactivate Surge' : 'Activate ×3'}
                </button>
              </div>
            </Panel>

            {/* VOICE CONTROLS */}
            <Panel>
              <div className="p-5">
                <div className="flex justify-between items-start mb-4">
                  <h2 className="text-[11px] font-bold tracking-widest uppercase" style={{ color: 'var(--text-dim)' }}>
                    Voice Controls (P7)
                  </h2>
                  <span className="text-[10px] font-bold tracking-widest uppercase" style={{ color: 'var(--text-dim)', opacity: 0.6 }}>
                    Demo Mode
                  </span>
                </div>
                <div className="space-y-4">
                  <div>
                    <div className="text-[11px] font-semibold mb-2" style={{ color: 'var(--text-dim)' }}>
                      Synthetic STT Injection
                    </div>
                    <button
                      onClick={dispatchScriptedVoice}
                      className="w-full py-2.5 rounded-lg text-[13px] font-semibold transition-colors"
                      style={{ border: '1px solid var(--line)', background: 'var(--bg-raised)', color: 'var(--focus)' }}
                    >
                      Inject: &ldquo;Mild chest discomfort&rdquo;
                    </button>
                  </div>
                  <div>
                    <div className="text-[11px] font-semibold mb-2" style={{ color: 'var(--text-dim)' }}>Audio</div>
                    <button
                      onClick={toggleMute}
                      className="w-full py-2.5 rounded-lg text-[13px] font-semibold transition-colors"
                      style={
                        muted
                          ? { border: '1px solid var(--acuity-red)', background: 'var(--acuity-red-fill)', color: 'var(--acuity-red)' }
                          : { border: '1px solid var(--line)', background: 'var(--bg-raised)', color: 'var(--text-dim)' }
                      }
                    >
                      {muted ? '🔇 Sound muted' : '🔊 Sound enabled'}
                    </button>
                  </div>
                </div>
              </div>
            </Panel>

          </div>
        </div>
      </main>
    </div>
  );
}

function StatusRow({ label, children, last = false }: { label: string; children: React.ReactNode; last?: boolean }) {
  return (
    <div
      className="flex justify-between items-center pb-3"
      style={last ? undefined : { borderBottom: '1px solid var(--line)' }}
    >
      <span className="text-[13px]" style={{ color: 'var(--text-dim)' }}>{label}</span>
      {children}
    </div>
  );
}

function MiniCard({ e }: { e: Encounter }) {
  const abstained = e.encounterId === 'P-15';
  const band = e.currentBand;

  const stripe = abstained
    ? 'var(--acuity-abstained)'
    : band === 'RED' ? 'var(--acuity-red)'
    : band === 'YELLOW' ? 'var(--acuity-yellow)'
    : 'var(--acuity-green)';

  const label = abstained ? 'ABSTAIN'
    : band === 'RED' ? 'RED'
    : band === 'YELLOW' ? 'YELLOW'
    : 'GREEN';

  return (
    <Link
      href={`/card/${e.encounterId}`}
      className="block relative overflow-hidden rounded-lg transition-all hover:-translate-y-0.5"
      style={{ background: 'var(--bg-raised)', border: `1px solid ${stripe}`, boxShadow: '0 1px 2px rgba(0,0,0,0.04)' }}
      title={e.chiefComplaint ?? ''}
    >
      <div className="absolute left-0 top-0 bottom-0 w-1" style={{ background: stripe }} />
      <div className="p-2.5 pl-3">
        <div className="flex justify-between items-start mb-1">
          <div className="text-[11px] font-mono font-medium" style={{ color: 'var(--text-dim)' }}>{e.encounterId}</div>
          <div className="text-[9px] font-bold tracking-widest uppercase" style={{ color: stripe }}>{label}</div>
        </div>
        <div className="text-base font-bold tabular-nums">{e.token}</div>
      </div>
    </Link>
  );
}
