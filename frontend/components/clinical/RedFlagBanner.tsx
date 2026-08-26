import type { RedFlag } from '@/lib/api/types';

interface Props {
  flags: RedFlag[];
}

/**
 * Leading position on the card (DESIGN_SYSTEM §8).
 * Red-flag Red is NOT system-overridable downward by any later model output —
 * only a clinician can move it, with a reason. That claim is shown in the UI
 * as the `lockedDownward` label so a judge can see the invariant.
 */
export function RedFlagBanner({ flags }: Props) {
  if (flags.length === 0) return null;

  return (
    <div
      className="p-4 rounded-lg border"
      style={{
        borderColor: 'var(--acuity-red)',
        background: 'var(--acuity-red-fill)',
      }}
    >
      <div className="flex items-center gap-2 mb-2">
        <span className="text-lg" style={{ color: 'var(--acuity-red)' }} aria-hidden>▲</span>
        <h3 className="text-xs font-bold uppercase tracking-wider" style={{ color: 'var(--acuity-red)' }}>
          Red Flag — Leading Factor
        </h3>
      </div>
      {flags.map((f, i) => (
        <div key={i} className="text-sm" style={{ color: 'var(--text)' }}>
          <div className="font-medium">{f.observation}</div>
          <div className="text-xs mt-1" style={{ color: 'var(--text-dim)' }}>
            Fixed table → RED · locked, not system-overridable downward
          </div>
        </div>
      ))}
    </div>
  );
}
