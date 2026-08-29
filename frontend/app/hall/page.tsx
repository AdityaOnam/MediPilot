'use client';

import { useEffect, useState } from 'react';
import { api } from '@/lib/api/client';
import type { Encounter } from '@/lib/api/types';
import { Mascot } from '@/components/mascot/Mascot';
import { VideoBackground } from '@/components/ui/VideoBackground';
import dynamic from 'next/dynamic';

const MascotScene = dynamic(() => import('@/components/3d/MascotScene'), {
  ssr: false,
  loading: () => <Mascot pose="resting" size={110} />,
});

/**
 * The public waiting-hall display.
 *
 * Two hard rules, both load-bearing rather than decorative:
 *
 *  1. TOKEN NUMBERS ONLY. No names, and no acuity — not the band, not a
 *     colour that encodes it, and not an ordering derived from it. A room
 *     full of strangers must not be able to work out who the system
 *     thinks is sickest. The waiting grid is therefore sorted by token,
 *     which is arrival order, and never by band.
 *  2. Never imply a promise about when someone will be seen. Waits are
 *     shown as time already elapsed, never as time remaining, because the
 *     queue reorders whenever anyone deteriorates.
 *
 * The board previously showed one undifferentiated grid, so a patient who
 * had just been told "go to Counter 1" had no way to confirm it from the
 * room. Being called is now the loudest thing on the screen.
 */
export default function HallPage() {
  const [encounters, setEncounters] = useState<Encounter[]>([]);
  const [nowMs, setNowMs] = useState(Date.now());

  useEffect(() => {
    let cancelled = false;
    const load = () => api.getCensus().then((list) => { if (!cancelled) setEncounters(list); });
    load();
    const iv = setInterval(load, 5000);
    return () => { cancelled = true; clearInterval(iv); };
  }, []);

  useEffect(() => {
    const iv = setInterval(() => setNowMs(Date.now()), 30000);
    return () => clearInterval(iv);
  }, []);

  const waiting = encounters.filter((e) => e.state === 'waiting');

  // Being called: intake sent them to a named counter and the counter has
  // not recorded their vitals yet. This is the one genuinely actionable
  // thing on the screen, so it gets the top half.
  const called = waiting
    .filter((e) => e.awaitingVitals && e.counter)
    .sort((a, b) => a.token.localeCompare(b.token, undefined, { numeric: true }));

  const calledIds = new Set(called.map((e) => e.encounterId));
  const stillWaiting = waiting
    .filter((e) => !calledIds.has(e.encounterId))
    .sort((a, b) => a.token.localeCompare(b.token, undefined, { numeric: true }));

  const longestWaitMin = waiting.length
    ? Math.round(Math.max(...waiting.map((e) => (nowMs - new Date(e.arrivedAt).getTime()) / 60000)))
    : 0;

  return (
    <div
      data-surface="patient"
      className="min-h-screen flex flex-col relative overflow-hidden"
      style={{ background: 'var(--bg)', color: 'var(--text)' }}
    >
      <VideoBackground src="/media/videos/clips/waiting-ambient.mp4" opacity={0.1} lazy />

      <header className="relative z-10 px-8 pt-8 pb-6">
        <div className="max-w-5xl mx-auto flex items-end justify-between gap-6 flex-wrap">
          <div>
            <h1 className="text-4xl font-bold tracking-tight">Waiting Hall</h1>
            <p className="mt-1 text-sm" style={{ color: 'var(--text-dim)' }}>
              Token numbers only — no names, no acuity displayed
            </p>
          </div>
          <div className="flex items-center gap-7 text-right">
            <div>
              <div className="text-3xl font-bold tabular-nums">{waiting.length}</div>
              <div className="text-[11px] uppercase tracking-wider" style={{ color: 'var(--text-dim)' }}>
                Waiting
              </div>
            </div>
            <div>
              <div className="text-3xl font-bold tabular-nums">{longestWaitMin}m</div>
              <div className="text-[11px] uppercase tracking-wider" style={{ color: 'var(--text-dim)' }}>
                Longest wait so far
              </div>
            </div>
          </div>
        </div>
      </header>

      <main className="relative z-10 flex-1 px-8 pb-4">
        <div className="max-w-5xl mx-auto flex flex-col gap-8">

          {/* Now being called */}
          <section aria-live="polite">
            <h2
              className="text-xs font-semibold uppercase tracking-[0.18em] mb-3"
              style={{ color: 'var(--mp-red)' }}
            >
              Now being called
            </h2>

            {called.length === 0 ? (
              <div
                className="rounded-2xl px-6 py-8 text-center text-base"
                style={{ background: 'var(--bg-card)', border: '1px dashed var(--line)', color: 'var(--text-dim)' }}
              >
                Nobody is being called right now. Please watch this screen.
              </div>
            ) : (
              <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
                {called.map((e, i) => (
                  <div
                    key={e.encounterId}
                    className="rounded-2xl px-6 py-5 flex items-center justify-between gap-4"
                    style={{
                      background: 'var(--bg-raised)',
                      border: '2px solid var(--mp-red)',
                      boxShadow: '0 0 0 6px rgba(223,66,61,0.08)',
                      animation: `callIn 0.35s ease-out ${i * 70}ms both`,
                    }}
                  >
                    <span className="text-5xl font-bold tabular-nums" style={{ color: 'var(--mp-red)' }}>
                      {e.token}
                    </span>
                    <span className="text-right">
                      <span
                        className="block text-[10px] uppercase tracking-wider"
                        style={{ color: 'var(--text-dim)' }}
                      >
                        Please go to
                      </span>
                      <span className="block text-lg font-semibold leading-tight">{e.counter}</span>
                    </span>
                  </div>
                ))}
              </div>
            )}
          </section>

          {/* Everyone else, in arrival order */}
          <section>
            <h2
              className="text-xs font-semibold uppercase tracking-[0.18em] mb-3"
              style={{ color: 'var(--text-dim)' }}
            >
              Waiting · {stillWaiting.length}
            </h2>

            {stillWaiting.length === 0 ? (
              <p className="text-base" style={{ color: 'var(--text-dim)' }}>
                No patients currently waiting.
              </p>
            ) : (
              <div className="flex flex-wrap gap-2.5">
                {stillWaiting.map((e, i) => (
                  <div
                    key={e.encounterId}
                    className="flex items-center justify-center w-[76px] h-[62px] rounded-xl text-xl font-semibold tabular-nums"
                    style={{
                      background: 'var(--bg-card)',
                      border: '1px solid var(--line)',
                      color: 'var(--text)',
                      animation: `fadeIn 0.3s ease-out ${Math.min(i, 20) * 35}ms both`,
                    }}
                  >
                    {e.token}
                  </div>
                ))}
              </div>
            )}
          </section>
        </div>
      </main>

      <footer className="relative z-10 px-8 pb-6 pt-2">
        <div className="max-w-5xl mx-auto flex items-end justify-between gap-6">
          <div>
            <p className="text-base font-medium">
              If anything feels worse, tell the front desk straight away.
            </p>
            <p className="text-xs mt-1" style={{ color: 'var(--text-dim)' }}>
              The order here can change at any time. Waiting longer does not mean you were forgotten.
            </p>
          </div>
          <div className="w-[110px] h-[145px] shrink-0">
            <MascotScene state="idle" className="w-full h-full" fallbackPose="resting" />
          </div>
        </div>
      </footer>

      <style jsx>{`
        @keyframes fadeIn {
          from { opacity: 0; transform: translateY(8px); }
          to { opacity: 1; transform: translateY(0); }
        }
        @keyframes callIn {
          from { opacity: 0; transform: scale(0.96); }
          to { opacity: 1; transform: scale(1); }
        }
      `}</style>
    </div>
  );
}
