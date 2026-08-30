'use client';

import type { Lang } from '../tree/types';
import type { MicPhase } from '../voice/useSpeech';

/**
 * Persistent voice controls (Part 2: "always three ways to answer").
 * Mute, and a tap-to-skip-the-reading affordance for a literate patient
 * who finds full dictation slow — the reading is the default, not a wall.
 */
export function VoiceBar({
  lang,
  phase,
  muted,
  onToggleMute,
  onSkip,
  onStop,
  onRetry,
  micDenied = false,
}: {
  lang: Lang;
  phase: MicPhase;
  muted: boolean;
  onToggleMute: () => void;
  onSkip: () => void;
  onStop: () => void;
  /** Re-open the mic for this same question. */
  onRetry?: () => void;
  /** Suppresses the retry offer when there is no microphone to reopen. */
  micDenied?: boolean;
}) {
  const canSkip = phase === 'speaking' || phase === 'arming';
  const canStop = phase === 'listening' || phase === 'settling';
  // Offered once the mic has closed on this question without advancing —
  // the manual escape hatch after the two automatic retries are spent, so
  // a patient is never left with a dead mic and no way to reopen it.
  const canRetry =
    !!onRetry && !muted && !micDenied && (phase === 'idle' || phase === 'matching');

  return (
    <div className="flex items-center justify-center gap-3 mt-2">
      <button
        type="button"
        onClick={onToggleMute}
        className="px-3 py-2 rounded-full text-xs"
        style={{ background: 'var(--bg-raised)', border: '1px solid var(--line)', color: 'var(--text-dim)' }}
      >
        {muted
          ? lang === 'hi' ? '🔇 आवाज़ बंद' : '🔇 Sound off'
          : lang === 'hi' ? '🔈 आवाज़ चालू' : '🔈 Sound on'}
      </button>

      {canSkip && (
        <button
          type="button"
          onClick={onSkip}
          className="px-3 py-2 rounded-full text-xs"
          style={{ background: 'var(--bg-raised)', border: '1px solid var(--line)', color: 'var(--text-dim)' }}
        >
          {lang === 'hi' ? 'पढ़ना छोड़ें' : 'Skip the reading'}
        </button>
      )}

      {canRetry && (
        <button
          type="button"
          onClick={onRetry}
          className="px-3 py-2 rounded-full text-xs"
          style={{ background: 'var(--bg-raised)', border: '1px solid var(--mp-red)', color: 'var(--mp-red)' }}
        >
          {lang === 'hi' ? '🎤 फिर से बोलें' : '🎤 Speak again'}
        </button>
      )}

      {canStop && (
        <button
          type="button"
          onClick={onStop}
          className="px-3 py-2 rounded-full text-xs"
          style={{ background: 'var(--bg-raised)', border: '1px solid var(--line)', color: 'var(--text-dim)' }}
        >
          {lang === 'hi' ? 'माइक बंद करें' : 'Stop the mic'}
        </button>
      )}
    </div>
  );
}
