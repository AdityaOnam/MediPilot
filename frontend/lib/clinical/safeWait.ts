import type { Band, Cadence, BreachKind } from '../api/types';

export const CADENCE_TABLE: Record<Band | 'ABSTAINED', { rescoreSec: number; remeasureSec: number; ceilingSec: number }> = {
  RED:       { rescoreSec: 60,   remeasureSec: 300,  ceilingSec: 0 },
  YELLOW:    { rescoreSec: 300,  remeasureSec: 1800, ceilingSec: 3600 },
  GREEN:     { rescoreSec: 300,  remeasureSec: 3600, ceilingSec: 7200 },
  ABSTAINED: { rescoreSec: 300,  remeasureSec: 1800, ceilingSec: 900 },
};

export const SURGE_CADENCE_TABLE: Record<Band | 'ABSTAINED', { rescoreSec: number; remeasureSec: number; ceilingSec: number }> = {
  RED:       CADENCE_TABLE.RED,
  YELLOW:    { rescoreSec: 300,  remeasureSec: 2700, ceilingSec: 3600 },
  GREEN:     { rescoreSec: 300,  remeasureSec: 5400, ceilingSec: 7200 },
  ABSTAINED: CADENCE_TABLE.ABSTAINED,
};

export interface CadenceState {
  rescoreAge: number;
  remeasureRemaining: number;
  ceilingRemaining: number;
  breached: boolean;
  breachKind: BreachKind | null;
}

export function computeCadenceState(cadence: Cadence, now: string): CadenceState {
  const t = new Date(now).getTime();
  const rescoreAge = Math.max(0, (t - new Date(cadence.nextRescoreAt).getTime() + cadence.rescoreSec * 1000) / 1000);
  const remeasureRemaining = Math.max(0, (new Date(cadence.nextRemeasureAt).getTime() - t) / 1000);
  const ceilingRemaining = Math.max(0, (new Date(cadence.ceilingBreachesAt).getTime() - t) / 1000);

  const breached = cadence.breached || remeasureRemaining <= 0 || ceilingRemaining <= 0;
  let breachKind: BreachKind | null = cadence.breachKind ?? null;
  if (!breachKind && breached) {
    breachKind = ceilingRemaining <= 0 ? 'CEILING_EXCEEDED' : 'REMEASURE_MISSED';
  }

  return { rescoreAge, remeasureRemaining, ceilingRemaining, breached, breachKind };
}

export function formatDuration(seconds: number): string {
  if (seconds <= 0) return '0s';
  const m = Math.floor(seconds / 60);
  const s = Math.floor(seconds % 60);
  if (m === 0) return `${s}s`;
  if (s === 0) return `${m}m`;
  return `${m}m ${s}s`;
}
