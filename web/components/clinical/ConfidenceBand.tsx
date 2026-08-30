import type { Band, ConfidenceReducer } from '@/lib/api/types';

interface Props {
  confidence: 'high' | 'moderate' | 'low';
  conformalSet: Band[];
  coverage?: number;
  reducers?: ConfidenceReducer[];
}

/**
 * Conformal set is the message — the WIDTH is what the nurse reads.
 * A wide set is a genuine claim of ambiguity, not a display quirk.
 *
 * `reducers` name the specific reasons confidence is low:
 * missing-field, stale-reading, inferred-stratum, sensor-disagreement,
 * out-of-distribution. Naming them is how we detect them being wrong.
 */
export function ConfidenceBand({ confidence, conformalSet, coverage = 0.9, reducers }: Props) {
  const wide = conformalSet.length >= 2;

  const confColor = confidence === 'high' ? '#10B981' : confidence === 'moderate' ? '#F59E0B' : '#EF4444';

  return (
    <div className="p-4 rounded-xl border border-[var(--line)] bg-[var(--bg-card)]">
      <h3 className="text-xs font-semibold text-[var(--text-dim)] uppercase tracking-wider mb-4">
        Model Confidence
      </h3>
      
      <div className="flex flex-col gap-4">
        <div className="flex items-center gap-3">
          <div className="px-2.5 py-1 rounded-md text-[11px] font-bold uppercase tracking-wide border"
               style={{ color: confColor, borderColor: `${confColor}40`, backgroundColor: `${confColor}10` }}>
            {confidence}
          </div>
          <p className="text-xs text-[var(--text-dim)]">
            True level falls in conformal set {Math.round(coverage * 10)} times in 10.
          </p>
        </div>

        <div className="flex items-center gap-3">
          <span className="text-xs font-medium text-[var(--text-dim)]">Set:</span>
          <div className="flex items-center gap-1.5 font-mono text-sm text-[var(--text-dim)]">
            {'{'}
            {conformalSet.map((b, i) => (
              <span key={i} className="text-[var(--text)] font-semibold">{b}</span>
            ))}
            {'}'}
          </div>
          {wide && <span className="text-xs text-[#F59E0B] font-medium ml-2">Ambiguous</span>}
        </div>

        {reducers && reducers.length > 0 && (
          <div className="pt-3 border-t border-[var(--line)]">
            <span className="text-[11px] font-medium text-[var(--text-dim)] uppercase tracking-wider block mb-2">
              Reduced By
            </span>
            <div className="flex flex-wrap gap-2">
              {reducers.map(r => (
                <span key={r} className="inline-flex items-center gap-1.5 px-2 py-1 rounded bg-[var(--bg-raised)] border border-[var(--line)] text-[11px] text-[var(--text-dim)] capitalize">
                  <span className="w-1.5 h-1.5 rounded-full bg-[#F59E0B]" />
                  {r.replace(/-/g, ' ')}
                </span>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
