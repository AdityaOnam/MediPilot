'use client';

/**
 * One component for all five voice-cycle phases (Part 2 of the plan).
 * Purely presentational — `useSpeech` (B4) drives `phase` and `level`;
 * until then it renders a static idle/speaking orb so the screens that
 * embed it are visually complete ahead of the mic wiring.
 */
export type MicPhase = 'idle' | 'speaking' | 'arming' | 'listening' | 'settling' | 'matching';

const PHASE_LABEL: Record<MicPhase, { en: string; hi: string }> = {
  idle: { en: '', hi: '' },
  speaking: { en: 'Speaking…', hi: 'बोल रहा हूं…' },
  arming: { en: 'One moment…', hi: 'एक पल…' },
  listening: { en: 'Listening…', hi: 'सुन रहा हूं…' },
  settling: { en: 'Got it…', hi: 'समझ गया…' },
  matching: { en: 'Checking…', hi: 'जांच रहा हूं…' },
};

export function MicOrb({
  phase,
  level = 0,
  lang,
}: {
  phase: MicPhase;
  /** 0..1 RMS level, used once useSpeech (B4) drives real audio. */
  level?: number;
  lang: 'en' | 'hi';
}) {
  const label = PHASE_LABEL[phase][lang];
  const isActive = phase === 'listening' || phase === 'speaking';
  const scale = 1 + Math.min(level, 1) * 0.18;

  return (
    <div className="flex flex-col items-center gap-3 py-4">
      <div
        className="relative flex items-center justify-center rounded-full transition-transform duration-100"
        style={{
          width: 88,
          height: 88,
          transform: `scale(${isActive ? scale : 1})`,
          background: phase === 'listening' ? 'var(--mp-red)' : 'var(--bg-raised)',
          border: `2px solid ${phase === 'listening' ? 'var(--mp-red)' : 'var(--line)'}`,
          opacity: phase === 'idle' ? 0.4 : 1,
        }}
      >
        <MicGlyph active={phase === 'listening'} />
        {phase === 'listening' && (
          <span
            className="absolute inset-0 rounded-full animate-ping"
            style={{ border: '2px solid var(--mp-red)', opacity: 0.35 }}
          />
        )}
      </div>
      {label && (
        <span className="text-sm" style={{ color: 'var(--text-dim)' }}>
          {label}
        </span>
      )}
    </div>
  );
}

function MicGlyph({ active }: { active: boolean }) {
  return (
    <svg width="30" height="30" viewBox="0 0 24 24" fill="none" aria-hidden="true">
      <rect x="9" y="2" width="6" height="12" rx="3" stroke={active ? 'white' : 'currentColor'} strokeWidth="1.6" />
      <path
        d="M5 11a7 7 0 0 0 14 0M12 18v3"
        stroke={active ? 'white' : 'currentColor'}
        strokeWidth="1.6"
        strokeLinecap="round"
      />
    </svg>
  );
}
