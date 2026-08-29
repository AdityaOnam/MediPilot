import type { Measurement, AgeStratum } from '@/lib/api/types';
import { VitalIcon } from './VitalIcon';
import { normaliseVitalCode, prettyVitalLabel, VITALS } from '@/lib/clinical/vitals';

interface Props {
  m: Measurement;
  stratum: AgeStratum;
  stratumInferred: boolean;
}

export function VitalChip({ m, stratum, stratumInferred }: Props) {
  const expired = m.validity === 'expired';
  const canonical = normaliseVitalCode(m.code);
  const label = prettyVitalLabel(m.code);
  const unit = m.unit || (canonical ? VITALS[canonical].unit : '');

  // A reading the nurse invented ("peak flow") has no normal range, so it
  // is shown neutrally rather than being coloured as if it were normal.
  const custom = !canonical;

  let bandColor = 'var(--text-dim)';
  if (!expired && m.bandForStratum) {
    if (m.bandForStratum === 'high' || m.bandForStratum === 'above' || m.bandForStratum === 'below') {
      bandColor = 'var(--acuity-red)';
    } else if (m.bandForStratum === 'low') {
      bandColor = 'var(--acuity-yellow)';
    } else {
      bandColor = 'var(--acuity-green)';
    }
  }

  const msAgo = Date.now() - new Date(m.takenAt).getTime();
  const secAgo = Math.max(0, Math.floor(msAgo / 1000));
  const minAgo = Math.floor(secAgo / 60);
  const timeAgo = minAgo > 0 ? `${minAgo}m ago` : `${secAgo}s ago`;

  return (
    <div
      className="p-4 rounded-xl flex flex-col gap-3"
      style={{
        background: 'var(--bg-card)',
        border: `1px solid ${expired ? 'var(--acuity-red)' : 'var(--line)'}`,
      }}
    >
      <div className="flex justify-between items-start gap-2">
        <div
          className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wider min-w-0"
          style={{ color: expired ? 'var(--acuity-red)' : bandColor }}
        >
          {/* Per-vital glyph, or the neutral gauge for a nurse-added field. */}
          <VitalIcon code={m.code} size={15} />
          <span className="truncate" style={{ color: 'var(--text-dim)' }}>{label}</span>
        </div>
        <div
          className="flex items-center gap-1.5 px-2 py-0.5 rounded text-[10px] font-bold uppercase tracking-wider shrink-0"
          style={{
            background: 'var(--bg-raised)',
            border: '1px solid var(--line)',
            color: expired ? 'var(--acuity-red)' : bandColor,
          }}
        >
          <span className="w-1.5 h-1.5 rounded-full" style={{ background: expired ? 'var(--acuity-red)' : bandColor }} />
          {m.validity}
        </div>
      </div>

      <div className="flex items-baseline gap-1 mt-1">
        <div className="text-3xl font-semibold tabular-nums" style={{ color: 'var(--text)' }}>
          {expired || m.value === null ? '—' : m.value}
        </div>
        {!expired && m.value !== null && unit && (
          <div className="text-sm font-medium" style={{ color: 'var(--text-dim)' }}>{unit}</div>
        )}
      </div>

      <div className="flex flex-col gap-1 mt-1 pt-3" style={{ borderTop: '1px solid var(--line)' }}>
        <div className="flex items-center justify-between text-xs" style={{ color: 'var(--text-dim)' }}>
          <span className="capitalize">{m.source.replace(/[-_]/g, ' ')}</span>
          <span>{timeAgo}</span>
        </div>

        {m.bandForStratum && !expired && (
          <div className="text-[11px] font-medium" style={{ color: 'var(--text-dim)' }}>
            {m.bandForStratum} for {stratum}{stratumInferred ? ' (inferred)' : ''}
          </div>
        )}

        {custom && (
          <div className="text-[11px] font-medium" style={{ color: 'var(--text-dim)' }}>
            Nurse-recorded · not scored
          </div>
        )}
      </div>
    </div>
  );
}
