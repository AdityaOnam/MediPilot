import type { Measurement, AgeStratum } from '@/lib/api/types';

interface Props {
  m: Measurement;
  stratum: AgeStratum;
  stratumInferred: boolean;
}

function VitalIcon({ code }: { code: string }) {
  const c = code.toUpperCase();
  if (c === 'HR') {
    return (
      <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
        <path d="M19 14c1.49-1.46 3-3.21 3-5.5A5.5 5.5 0 0 0 16.5 3c-1.76 0-3 .5-4.5 2-1.5-1.5-2.74-2-4.5-2A5.5 5.5 0 0 0 2 8.5c0 2.3 1.5 4.05 3 5.5l7 7Z"/>
      </svg>
    );
  }
  if (c === 'SBP' || c === 'DBP') {
    return (
      <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
        <path d="M22 12h-4l-3 9L9 3l-3 9H2"/>
      </svg>
    );
  }
  if (c === 'SPO2') {
    return (
      <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
        <path d="M12 22a7 7 0 0 0 7-7c0-2-1-3.9-3-5.5s-3.5-4-4-6.5c-.5 2.5-2 4.9-4 6.5C6 11.1 5 13 5 15a7 7 0 0 0 7 7z"/>
      </svg>
    );
  }
  if (c === 'TEMP') {
    return (
      <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
        <path d="M14 14.76V3.5a2.5 2.5 0 0 0-5 0v11.26a4.5 4.5 0 1 0 5 0z"/>
      </svg>
    );
  }
  if (c === 'RR') {
    return (
      <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
        <path d="M9.59 4.59A2 2 0 1 1 11 8H2m10.59 11.41A2 2 0 1 0 14 16H2m15.73-8.27A2.5 2.5 0 1 1 19.5 12H2"/>
      </svg>
    );
  }
  // Default generic icon
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
      <circle cx="12" cy="12" r="10"/><path d="M12 16v-4"/><path d="M12 8h.01"/>
    </svg>
  );
}

export function VitalChip({ m, stratum, stratumInferred }: Props) {
  const expired = m.validity === 'expired';
  const discounted = m.validity === 'discounted';

  let bandColor = 'var(--text-dim)';
  if (!expired && m.bandForStratum) {
    if (m.bandForStratum === 'high' || m.bandForStratum === 'above' || m.bandForStratum === 'below') {
      bandColor = '#EF4444'; // Red
    } else if (m.bandForStratum === 'low') {
      bandColor = '#F59E0B'; // Amber
    } else {
      bandColor = '#10B981'; // Green
    }
  }

  const msAgo = Date.now() - new Date(m.takenAt).getTime();
  const secAgo = Math.floor(msAgo / 1000);
  const minAgo = Math.floor(secAgo / 60);
  const timeAgo = minAgo > 0 ? `${minAgo}m ago` : `${secAgo}s ago`;

  return (
    <div className="p-4 rounded-xl border border-white/10 bg-white/[0.02] flex flex-col gap-3 hover:bg-white/[0.03] transition-colors">
      <div className="flex justify-between items-start">
        <div className="flex items-center gap-2 text-white/50 text-xs font-semibold uppercase tracking-wider">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5"><path d="M22 12h-4l-3 9L9 3l-3 9H2"/></svg>
          {m.code}
        </div>
        <div className="flex items-center gap-1.5 px-2 py-0.5 rounded text-[10px] font-bold uppercase tracking-wider bg-white/5 border border-white/10" style={{ color: expired ? '#EF4444' : bandColor }}>
          <span className="w-1.5 h-1.5 rounded-full" style={{ backgroundColor: expired ? '#EF4444' : bandColor }} />
          {m.validity}
        </div>
      </div>

      <div className="flex items-baseline gap-1 mt-1">
        <div className="text-3xl font-semibold tabular-nums text-white/90">
          {expired || m.value === null ? '—' : m.value}
        </div>
        {!expired && m.value !== null && (
          <div className="text-sm font-medium text-white/40">
            {m.unit}
          </div>
        )}
      </div>

      <div className="flex flex-col gap-1 mt-1 border-t border-white/10 pt-3">
        <div className="flex items-center justify-between text-xs text-white/50">
          <span className="capitalize">{m.source.replace(/-/g, ' ')}</span>
          <span>{timeAgo}</span>
        </div>
        
        {m.bandForStratum && !expired && (
          <div className="text-[11px] text-white/40 font-medium">
            {m.bandForStratum} for {stratum}{stratumInferred ? ' (inferred)' : ''}
          </div>
        )}
      </div>
    </div>
  );
}
