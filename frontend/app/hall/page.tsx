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

export default function HallPage() {
  const [encounters, setEncounters] = useState<Encounter[]>([]);

  useEffect(() => {
    api.getCensus().then(setEncounters);
    const interval = setInterval(() => {
      api.getCensus().then(setEncounters);
    }, 10000);
    return () => clearInterval(interval);
  }, []);

  const waiting = encounters.filter(e => e.state === 'waiting');

  return (
    <div data-surface="patient" className="min-h-screen flex flex-col relative overflow-hidden" style={{ background: 'var(--bg)', color: 'var(--text)' }}>
      {/* Ambient video background */}
      <VideoBackground src="/media/videos/clips/waiting-ambient.mp4" opacity={0.12} lazy />

      <header className="relative z-10 text-center mb-10 pt-8 px-8">
        <h1 className="text-4xl font-bold">Waiting Hall</h1>
        <p className="mt-2" style={{ color: 'var(--text-dim)' }}>Token numbers only — no names, no acuity displayed</p>
        <span className="inline-block mt-3 px-3 py-1 text-xs font-medium rounded border" style={{ borderColor: 'var(--line)', color: 'var(--text-dim)' }}>
          SIMULATED DATA
        </span>
      </header>

      <div className="relative z-10 flex-1 flex flex-col items-center justify-center px-8">
        <div className="grid grid-cols-4 sm:grid-cols-5 gap-4 max-w-2xl">
          {waiting.map((e, i) => (
            <div
              key={e.encounterId}
              className="flex items-center justify-center w-20 h-20 rounded-lg border text-2xl font-bold glow-teal"
              style={{
                borderColor: 'var(--line)',
                background: 'var(--bg-card)',
                animation: `fadeIn 0.3s ease-out ${i * 50}ms both`,
              }}
            >
              {e.token}
            </div>
          ))}
        </div>
        {waiting.length === 0 && (
          <p className="text-xl" style={{ color: 'var(--text-dim)' }}>No patients currently waiting</p>
        )}
      </div>

      <footer className="relative z-10 text-center text-sm mt-8 pb-6 px-8" style={{ color: 'var(--text-dim)' }}>
        <p className="mb-4">If anything feels worse, inform the front desk immediately.</p>
        <div className="absolute right-8 bottom-0 w-[120px] h-[160px]">
          <MascotScene state="idle" className="w-full h-full" fallbackPose="resting" />
        </div>
      </footer>

      {/* Staggered fade-in keyframe */}
      <style jsx>{`
        @keyframes fadeIn {
          from { opacity: 0; transform: translateY(8px); }
          to { opacity: 1; transform: translateY(0); }
        }
      `}</style>
    </div>
  );
}
