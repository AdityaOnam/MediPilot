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

/** Foreground/background pairs that hold up on the warm-paper ward
 *  surface. The previous values were tuned for the dark clinical theme —
 *  #B9AEFF on a 15%-opacity wash reads fine on #0D1117 and disappears on
 *  #FBF7F2 — so each is now a darker ink over a pale tint. */
const BADGE_STYLES: Record<string, { bg: string; fg: string; label: string }> = {
  unaccompanied:   { bg: 'rgba(91,75,196,0.10)',  fg: '#4C3EA8', label: 'unaccompanied' },
  inferredAge:     { bg: 'rgba(154,98,6,0.10)',   fg: '#8A5705', label: 'inferred age' },
  zeroHistory:     { bg: 'rgba(30,90,168,0.10)',  fg: '#1E5AA8', label: 'zero history' },
  humanLane:       { bg: 'rgba(146,106,71,0.14)', fg: '#7A5636', label: 'human lane' },
  pediatric:       { bg: 'rgba(27,122,75,0.10)',  fg: '#166840', label: 'pediatric' },
  geriatric:       { bg: 'rgba(27,122,75,0.10)',  fg: '#166840', label: 'geriatric' },
  awaitingVitals:  { bg: 'rgba(223,66,61,0.10)',  fg: '#B5322D', label: 'at counter' },
};

function badgesFor(e: Encounter): string[] {
  const b: string[] = [];
  // First, because it tells the nurse this band is words-only so far.
  if (e.awaitingVitals) b.push('awaitingVitals');
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
    badges = badges.filter(b => b === 'unaccompanied' || b === 'pediatric' || b === 'awaitingVitals');
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
