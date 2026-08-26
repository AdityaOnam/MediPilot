'use client';

import { useEffect, useRef, useState } from 'react';
import { motion, LayoutGroup } from 'motion/react';
import { api } from '@/lib/api/client';
import type { Encounter, StreamEvent, SurgeState } from '@/lib/api/types';
import { BAND_RANK } from '@/lib/api/types';
import { QueueCard } from '@/components/clinical/QueueCard';

export default function BoardPage() {
  const [encounters, setEncounters] = useState<Encounter[]>([]);
  const [simNowMs, setSimNowMs] = useState(Date.now());
  const [justEscalated, setJustEscalated] = useState<Record<string, number>>({});
  const [lastEvent, setLastEvent] = useState<StreamEvent | null>(null);
  const [surgeState, setSurgeState] = useState<SurgeState | null>(null);
  const [alerts, setAlerts] = useState<Extract<StreamEvent, { type: 'escalation' | 'breach' }>[]>([]);
  const escalationTimers = useRef<Record<string, ReturnType<typeof setTimeout>>>({});

  // Initial load + polling.
  useEffect(() => {
    let cancelled = false;
    const refresh = () => {
      api.getCensus().then(list => { if (!cancelled) setEncounters(list); });
      api.getSurge().then(s => { if (!cancelled) setSurgeState(s); });
    };
    refresh();
    const iv = setInterval(refresh, 1000);
    return () => { cancelled = true; clearInterval(iv); };
  }, []);

  // Local sim-clock tick for display cadence updates.
  useEffect(() => {
    const iv = setInterval(() => setSimNowMs(Date.now()), 1000);
    return () => clearInterval(iv);
  }, []);

  // Subscribe to stream — flash escalated cards for 20 s and maintain alert feed.
  useEffect(() => {
    const unsub = api.subscribe((event) => {
      setLastEvent(event);
      if (event.type === 'escalation' || event.type === 'breach') {
        setAlerts(prev => {
          const next = [event, ...prev];
          if (next.length > 20) next.pop();
          return next;
        });
      }
      if (event.type === 'surge') {
        api.getSurge().then(setSurgeState);
      }
      if (event.type === 'escalation') {
        const id = event.encounterId;
        setJustEscalated(prev => ({ ...prev, [id]: Date.now() }));
        if (escalationTimers.current[id]) clearTimeout(escalationTimers.current[id]);
        escalationTimers.current[id] = setTimeout(() => {
          setJustEscalated(prev => {
            const next = { ...prev };
            delete next[id];
            return next;
          });
        }, 20000);
      }
    });
    return () => {
      unsub();
      for (const t of Object.values(escalationTimers.current)) clearTimeout(t);
    };
  }, []);

  const waiting = encounters.filter(e => e.state === 'waiting');
  const abstained = waiting.filter(e => e.encounterId === 'P-15');
  const breaches = waiting.filter(e => e.cadence.breached && !abstained.includes(e));
  const triaged = waiting
    .filter(e => !abstained.includes(e) && !breaches.includes(e))
    .sort((a, b) => {
      const rankDiff = BAND_RANK[b.currentBand ?? 'GREEN'] - BAND_RANK[a.currentBand ?? 'GREEN']!;
      if (rankDiff !== 0) return rankDiff;
      return new Date(a.arrivedAt).getTime() - new Date(b.arrivedAt).getTime();
    });

  const longestWaitMin = Math.max(0, ...waiting.map(e => (simNowMs - new Date(e.arrivedAt).getTime()) / 60000));

  const isCompact = waiting.length > 18;

  return (
    <div data-surface="clinical" className="min-h-screen p-6" style={{ background: 'var(--bg)', color: 'var(--text)' }}>
      <header className="flex items-center justify-between mb-6 pb-4 border-b" style={{ borderColor: 'var(--line)' }}>
        <div className="flex items-baseline gap-6">
          <h1 className="text-2xl font-bold">Nurse Board</h1>
          <div className="flex items-baseline gap-4 text-sm" style={{ color: 'var(--text-dim)' }}>
            <span>Waiting: <span className="text-[var(--text)] font-semibold tabular-nums">{waiting.length}</span></span>
            <span>Longest wait: <span className="text-[var(--text)] font-semibold tabular-nums">{Math.round(longestWaitMin)}m</span></span>
            <span>Breaches: <span className="text-[var(--acuity-red)] font-semibold tabular-nums">{breaches.length}</span></span>
            <span>Abstained: <span className="text-[var(--acuity-abstained)] font-semibold tabular-nums">{abstained.length}</span></span>
          </div>
        </div>
        <div className="flex items-center gap-3">
          <span className="text-xs" style={{ color: 'var(--text-dim)' }}>medipilot-v0.3-demo</span>
          <span className="px-2 py-0.5 rounded text-xs border" style={{ borderColor: 'var(--line)', color: 'var(--text-dim)' }}>SIMULATED DATA</span>
        </div>
      </header>

      {surgeState?.active && (
        <div className="mb-6 p-4 rounded-lg border font-medium" style={{ borderColor: 'var(--acuity-yellow)', background: 'var(--acuity-yellow-fill)', color: 'var(--text)' }}>
          <div className="flex justify-between items-start">
            <div>
              <h2 className="text-lg font-bold" style={{ color: 'var(--acuity-yellow)' }}>⚠ Surge mode · {surgeState.multiplier}× arrivals</h2>
              <p className="text-sm mt-1">Department load reaches the routing layer only. Risk scores are unchanged.</p>
            </div>
            <details className="text-sm">
              <summary className="cursor-pointer hover:underline" style={{ color: 'var(--acuity-yellow)' }}>[what this means]</summary>
              <div className="mt-2 text-xs p-3 rounded" style={{ background: 'rgba(0,0,0,0.2)' }}>
                <div className="font-semibold mb-1">Stretched cadences:</div>
                <ul className="list-disc pl-4 mb-2">
                  {surgeState.stretched.map(s => (
                    <li key={s.band}>{s.band} re-measure: {s.fromSec / 60}m → {s.toSec / 60}m</li>
                  ))}
                </ul>
                <div className="font-semibold mb-1">Forbidden relaxations:</div>
                <ul className="list-disc pl-4 text-[var(--acuity-red)]">
                  {surgeState.refusals.map((r, i) => <li key={i}>{r}</li>)}
                </ul>
              </div>
            </details>
          </div>
        </div>
      )}

      {alerts.length > 0 && (
        <div className="mb-6 p-4 rounded-lg border" style={{ borderColor: 'var(--line)', background: 'var(--bg-card)' }}>
          <h2 className="text-sm font-semibold uppercase tracking-wider mb-2" style={{ color: 'var(--text-dim)' }}>Recent Alerts</h2>
          <div className="max-h-32 overflow-y-auto pr-2 flex flex-col gap-1 text-sm" aria-live="polite">
            {alerts.map((a, i) => (
              <div key={i} className="flex gap-3 py-1 border-b last:border-0" style={{ borderColor: 'var(--line)' }}>
                <span className="w-16 tabular-nums" style={{ color: 'var(--text-dim)' }}>{a.encounterId}</span>
                {a.type === 'escalation' ? (
                  <span style={{ color: 'var(--acuity-red)' }}>▲ Escalated {a.from} → {a.to} (cause: {a.cause})</span>
                ) : a.type === 'breach' ? (
                  <span style={{ color: 'var(--acuity-yellow)' }}>⚠ Breach: {a.kind}</span>
                ) : null}
              </div>
            ))}
          </div>
        </div>
      )}

      <LayoutGroup>
        {(breaches.length > 0 || abstained.length > 0) && (
          <section className="mb-8">
            <h2 className="text-sm font-semibold mb-3 uppercase tracking-wider" style={{ color: 'var(--acuity-red)' }}>
              Needs Your Eyes · {breaches.length + abstained.length}
            </h2>
            <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
              {abstained.map(e => (
                <motion.div
                  key={e.encounterId}
                  layout
                  layoutId={e.encounterId}
                  transition={{ type: 'spring', stiffness: 320, damping: 30, mass: 0.7 }}
                >
                  <QueueCard encounter={e} simNowMs={simNowMs} abstained density="comfortable" />
                </motion.div>
              ))}
              {breaches.map(e => (
                <motion.div
                  key={e.encounterId}
                  layout
                  layoutId={e.encounterId}
                  transition={{ type: 'spring', stiffness: 320, damping: 30, mass: 0.7 }}
                >
                  <QueueCard
                    encounter={e}
                    simNowMs={simNowMs}
                    justEscalated={!!justEscalated[e.encounterId]}
                    density="comfortable"
                  />
                </motion.div>
              ))}
            </div>
          </section>
        )}

        <section>
          <h2 className="text-sm font-semibold mb-3 uppercase tracking-wider" style={{ color: 'var(--text-dim)' }}>
            Queue · {triaged.length}
          </h2>
          <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
            {triaged.map(e => (
              <motion.div
                key={e.encounterId}
                layout
                layoutId={e.encounterId}
                transition={{ type: 'spring', stiffness: 320, damping: 30, mass: 0.7 }}
              >
                <QueueCard
                  encounter={e}
                  simNowMs={simNowMs}
                  justEscalated={!!justEscalated[e.encounterId]}
                  density="comfortable"
                />
              </motion.div>
            ))}
            {triaged.length === 0 && (
              <p className="text-sm py-6 text-center col-span-full" style={{ color: 'var(--text-dim)' }}>No patients in queue.</p>
            )}
          </div>
        </section>
      </LayoutGroup>
    </div>
  );
}
