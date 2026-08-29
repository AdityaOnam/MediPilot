import type { AbstentionReason } from '@/lib/api/types';

interface Props {
  reason: AbstentionReason;
  /**
   * Enforcement of Invariant 5 in the type system.
   * An abstained encounter has NO Green code path anywhere.
   */
  effectiveBand: 'YELLOW';
  unmetReviewBreach?: boolean;
}

const REASON_TEXT: Record<AbstentionReason, string> = {
  CONFORMAL_SET_TOO_WIDE: 'Conformal set too wide — the model cannot pick a band with the required coverage.',
  OUT_OF_DISTRIBUTION:    'Unlike anything in local data — this patient is outside the training distribution.',
  MISSING_CRITICAL_FIELDS: 'Critical fields missing — the model refuses to score without them.',
};

/**
 * Replaces the AcuityCard entirely (DESIGN_SYSTEM §8).
 * Hatched violet border, NEEDS YOUR EYES, no numbers, stated reason.
 *
 * There is no Green code path in this component (Invariant 5).
 * Abstained patients hold at a Yellow floor. Past 15 minutes unreviewed they
 * leave the queue and enter a breach list as an UNMET_REVIEW breach — not
 * left sitting quietly in a queue nobody is looking at.
 */
export function AbstentionCard({ reason, effectiveBand, unmetReviewBreach }: Props) {
  if (process.env.NODE_ENV !== 'production' && (effectiveBand as string) === 'GREEN') {
    throw new Error('AbstentionCard was passed GREEN. Invariant 5 leaked. See BACKEND_INTEGRATION_LOG §3.');
  }

  return (
    <div className="rounded-xl p-5" style={{ border: '1px solid var(--acuity-yellow)', background: 'var(--acuity-yellow-fill)' }}>
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-2 text-[var(--acuity-yellow)] font-semibold text-sm tracking-wide">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5"><path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"/><line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/></svg>
          NEEDS YOUR EYES
        </div>
        <span className="text-[10px] font-bold uppercase tracking-wider text-[var(--acuity-yellow)] opacity-70">Attention</span>
      </div>
      
      <h3 className="text-[var(--text)] text-sm font-medium mb-1">
        {reason.replace(/_/g, ' ')}
      </h3>
      <p className="text-[var(--text-dim)] text-sm mb-6 leading-relaxed">
        {REASON_TEXT[reason]}
      </p>

      <div className="border-t border-[var(--acuity-yellow)] opacity-60 pt-4">
        <p className="text-[11px] font-semibold text-[var(--text-dim)] uppercase tracking-wider mb-2">
          Current automated state
        </p>
        <div className="flex items-baseline gap-2 mb-1">
          <span className="w-2 h-2 rounded-full" style={{ background: 'var(--acuity-yellow)' }} />
          <span className="text-sm font-medium text-[var(--text)]">Holding at Yellow floor</span>
        </div>
        <p className="text-xs text-[var(--text-dim)] pl-4">
          No automated band is displayed. Nothing on this card should be interpreted as a recommendation.
        </p>
      </div>

      {unmetReviewBreach && (
        <div className="mt-5 pt-4 border-t border-red-500/20 flex items-center gap-2">
          <span className="px-2 py-0.5 bg-red-500/10 text-red-400 border border-red-500/20 rounded text-xs font-bold uppercase">
            Unmet Review Breach
          </span>
          <span className="text-xs text-[var(--text-dim)]">Unreviewed past 15 min.</span>
        </div>
      )}
    </div>
  );
}
