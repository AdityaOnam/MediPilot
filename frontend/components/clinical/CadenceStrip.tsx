'use client';

import { useEffect, useState } from 'react';
import type { Cadence } from '@/lib/api/types';
import { formatDuration } from '@/lib/clinical/safeWait';

interface Props {
  cadence: Cadence;
  /** simNow in ms — passed by parent so all cards tick from the same clock */
  simNowMs: number;
  compact?: boolean;
}

/**
 * Three time facts per card (FRONTEND_PLAN §4).
 * Replaces the old SafeWaitRing single-clock model.
 *
 *   re-scored 40s ago        thin, quiet, ambient
 *   re-measure in 12 min     primary
 *   ceiling in 28 min        the one that turns
 *
 * On breach: shows the breach kind by name.
 */
export function CadenceStrip({ cadence, simNowMs, compact = false }: Props) {
  const rescoreAgeSec = Math.max(0, (simNowMs - (new Date(cadence.nextRescoreAt).getTime() - cadence.rescoreSec * 1000)) / 1000);
  const remeasureRemainSec = (new Date(cadence.nextRemeasureAt).getTime() - simNowMs) / 1000;
  const ceilingRemainSec = (new Date(cadence.ceilingBreachesAt).getTime() - simNowMs) / 1000;

  const remeasureBreach = remeasureRemainSec <= 0;
  const ceilingBreach = ceilingRemainSec <= 0;
  const breached = cadence.breached || remeasureBreach || ceilingBreach;

  const breachKind = cadence.breachKind ??
    (ceilingBreach ? 'CEILING_EXCEEDED' : remeasureBreach ? 'REMEASURE_MISSED' : null);

  if (compact) {
    return (
      <div className="flex items-center gap-3 text-xs" style={{ color: 'var(--text-dim)' }}>
        <span title="Model re-scored">↻ {formatDuration(rescoreAgeSec)} ago</span>
        <span title="Re-measure deadline" style={{ color: remeasureBreach ? 'var(--acuity-red)' : 'var(--text)' }}>
          measure {remeasureBreach ? 'OVERDUE' : `in ${formatDuration(remeasureRemainSec)}`}
        </span>
        <span title="Wait ceiling" style={{ color: ceilingBreach ? 'var(--acuity-red)' : 'var(--text-dim)' }}>
          ceil {ceilingBreach ? 'BREACHED' : formatDuration(ceilingRemainSec)}
        </span>
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-3 font-medium">
      <div className="flex items-center gap-3">
        <div className="flex items-center justify-center w-4 h-4 rounded-full bg-white/10 text-white/70">
          <span className="text-[10px]">●</span>
        </div>
        <span className="text-xs text-white/50 w-32">Re-scored</span>
        <span className="text-xs text-white/90">{formatDuration(rescoreAgeSec)} ago</span>
      </div>

      <div className="flex items-center gap-3">
        <div className="flex items-center justify-center w-4 h-4 rounded-full border border-white/20 text-white/30">
          <span className="text-[10px]">○</span>
        </div>
        <span className="text-xs text-white/50 w-32">Next measurement</span>
        <span className="text-xs" style={{ color: remeasureBreach ? '#EF4444' : 'rgba(255,255,255,0.9)' }}>
          {remeasureBreach ? 'OVERDUE' : `in ${formatDuration(remeasureRemainSec)}`}
        </span>
      </div>

      <div className="flex items-center gap-3">
        <div className="flex items-center justify-center w-4 h-4 rounded-full border border-white/20 text-white/30">
          <span className="text-[10px]">○</span>
        </div>
        <span className="text-xs text-white/50 w-32">Cadence ceiling</span>
        <span className="text-xs" style={{ color: ceilingBreach ? '#EF4444' : 'rgba(255,255,255,0.5)' }}>
          {ceilingBreach ? 'EXCEEDED' : `in ${formatDuration(ceilingRemainSec)}`}
        </span>
      </div>
      
      {breached && breachKind && (
        <div className="mt-2 text-xs font-bold text-[#EF4444] uppercase tracking-wide">
          BREACH · {breachKind.replace(/_/g, ' ')}
        </div>
      )}
    </div>
  );
}
