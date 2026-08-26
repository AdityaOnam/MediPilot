'use client';

import Link from 'next/link';
import type { Encounter } from '@/lib/api/types';
import { BandChip } from './BandChip';
import { CadenceStrip } from './CadenceStrip';

interface Props {
  encounter: Encounter;
  simNowMs: number;
  abstained?: boolean;
  /** true if this card just escalated — parent controls the flash */
  justEscalated?: boolean;
  density?: 'comfortable' | 'compact';
}

const BADGE_STYLES: Record<string, { bg: string; fg: string; label: string }> = {
  unaccompanied:   { bg: 'rgba(155,140,255,0.15)', fg: '#B9AEFF', label: 'unaccompanied' },
  inferredAge:     { bg: 'rgba(255,176,32,0.15)',  fg: '#FFC868', label: 'inferred age' },
  zeroHistory:     { bg: 'rgba(88,166,255,0.15)',  fg: '#7CB6FF', label: 'zero history' },
  humanLane:       { bg: 'rgba(146,106,71,0.20)',  fg: '#D0A585', label: 'human lane' },
  pediatric:       { bg: 'rgba(61,214,140,0.15)',  fg: '#7EE0AE', label: 'pediatric' },
  geriatric:       { bg: 'rgba(61,214,140,0.15)',  fg: '#7EE0AE', label: 'geriatric' },
};

function badgesFor(e: Encounter): string[] {
  const b: string[] = [];
  if (!e.assisted) b.push('unaccompanied');
  if (e.ageStratumInferred) b.push('inferredAge');
  if (!e.hasPriorRecord) b.push('zeroHistory');
  if (!e.medicalInfoConsent) b.push('humanLane');
  if (e.ageStratum === 'child' || e.ageStratum === 'infant' || e.ageStratum === 'neonate') b.push('pediatric');
  if (e.ageStratum === 'geriatric') b.push('geriatric');
  return b;
}

export function QueueCard({ encounter, simNowMs, abstained = false, justEscalated = false, density = 'comfortable' }: Props) {
  let badges = badgesFor(encounter);
  if (density === 'compact') {
    badges = badges.filter(b => b === 'unaccompanied' || b === 'pediatric');
  }

  const isBreached = encounter.cadence.breached ||
    new Date(encounter.cadence.ceilingBreachesAt).getTime() < simNowMs ||
    new Date(encounter.cadence.nextRemeasureAt).getTime() < simNowMs;

  const isCompact = density === 'compact';

  return (
    <Link
      href={`/card/${encounter.encounterId}`}
      className={`block rounded-lg border transition-all hover:border-[var(--focus)] ${isCompact ? 'p-2' : 'p-4'}`}
      style={{
        background: 'var(--bg-card)',
        borderColor: justEscalated ? 'var(--acuity-red)' : isBreached ? 'var(--acuity-red)' : 'var(--line)',
        boxShadow: justEscalated ? '0 0 0 2px var(--acuity-red-fill)' : 'none',
      }}
    >
      <div className="flex items-start gap-4">
        <div className="flex flex-col items-center min-w-[64px]">
          <div className={`${isCompact ? 'text-base' : 'text-xl'} font-bold tabular-nums`}>{encounter.token}</div>
          <div className="text-[10px] mt-0.5 uppercase" style={{ color: 'var(--text-dim)' }}>
            {encounter.ageStratum}
          </div>
        </div>

        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 flex-wrap">
            <BandChip band={encounter.currentBand} abstained={abstained} size="sm" />
            {justEscalated && (
              <span
                aria-live="assertive"
                className="text-xs font-bold px-1.5 py-0.5 rounded animate-pulse"
                style={{ color: 'var(--acuity-red)', background: 'var(--acuity-red-fill)' }}
              >
                ▲ ESCALATED
              </span>
            )}
            {badges.map(b => {
              const s = BADGE_STYLES[b];
              return (
                <span
                  key={b}
                  className="text-[10px] px-1.5 py-0.5 rounded font-medium"
                  style={{ background: s.bg, color: s.fg }}
                >
                  {s.label}
                </span>
              );
            })}
          </div>
          <p className="mt-2 text-sm truncate" style={{ color: 'var(--text)' }}>
            {isCompact && encounter.chiefComplaint && encounter.chiefComplaint.length > 40
              ? encounter.chiefComplaint.substring(0, 40) + '...'
              : encounter.chiefComplaint}
          </p>
          <div className="mt-2">
            <CadenceStrip cadence={encounter.cadence} simNowMs={simNowMs} compact={isCompact} />
          </div>
        </div>
      </div>
    </Link>
  );
}
