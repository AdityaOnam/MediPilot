'use client';

import { useState } from 'react';
import type { Explanation, Factor } from '@/lib/api/types';

interface Props {
  explanation: Explanation;
}

/**
 * Three channels (DESIGN_SYSTEM §8, system plan §12).
 * Channel 1 is open by default because a nurse reading fast should see the
 * strongest factors + the one arguing against — that opposing factor is
 * mandatory, and its absence in the model output is treated as an abstention
 * upstream, not by the UI.
 *
 * Channels 2 and 3 sit behind a tap so the whole card stays absorbable in
 * seconds by someone already managing several patients.
 */
export function ExplanationChannels({ explanation }: Props) {
  const [openC2, setOpenC2] = useState(false);
  const [openC3, setOpenC3] = useState(false);

  const supports = explanation.channel1.filter(f => f.direction === 'supports');
  const opposes = explanation.channel1.filter(f => f.direction === 'opposes');

  return (
    <div className="space-y-3">
      {/* Channel 1 — always open */}
      <div className="p-4 rounded-lg border" style={{ borderColor: 'var(--line)', background: 'var(--bg-card)' }}>
        <h3 className="text-xs font-semibold uppercase tracking-wider mb-3" style={{ color: 'var(--text-dim)' }}>
          Channel 1 · What drove this
        </h3>

        <div>
          <p className="text-[10px] uppercase mb-1" style={{ color: 'var(--acuity-yellow)' }}>Argues For</p>
          <ul className="space-y-1.5">
            {supports.map((f, i) => <FactorRow key={i} f={f} />)}
          </ul>
        </div>

        {opposes.length > 0 ? (
          <div className="mt-3 pt-3 border-t" style={{ borderColor: 'var(--line)' }}>
            <p className="text-[10px] uppercase mb-1" style={{ color: 'var(--acuity-green)' }}>Argues Against</p>
            <ul className="space-y-1.5">
              {opposes.map((f, i) => <FactorRow key={i} f={f} />)}
            </ul>
          </div>
        ) : (
          <div className="mt-3 pt-3 border-t text-xs" style={{ borderColor: 'var(--line)', color: 'var(--text-dim)' }}>
            No opposing factor supplied — treated upstream as abstention, not an empty list.
          </div>
        )}
      </div>

      {/* Channel 2 — collapsible */}
      <div className="rounded-lg border" style={{ borderColor: 'var(--line)', background: 'var(--bg-card)' }}>
        <button
          onClick={() => setOpenC2(v => !v)}
          className="w-full flex items-center justify-between p-4 text-left"
          aria-expanded={openC2}
        >
          <h3 className="text-xs font-semibold uppercase tracking-wider" style={{ color: 'var(--text-dim)' }}>
            Channel 2 · What was considered and did not move it
          </h3>
          <span aria-hidden style={{ color: 'var(--text-dim)' }}>{openC2 ? '▾' : '▸'}</span>
        </button>
        {openC2 && (
          <div className="px-4 pb-4">
            <ul className="space-y-1">
              {explanation.channel2.considered.map((c, i) => (
                <li key={i} className="text-sm flex items-center gap-2" style={{ color: 'var(--text-dim)' }}>
                  <span aria-hidden>·</span>{c}
                </li>
              ))}
            </ul>

            {explanation.channel2.discounts.length > 0 && (
              <div className="mt-3 pt-3 border-t" style={{ borderColor: 'var(--line)' }}>
                <p className="text-[10px] uppercase mb-2" style={{ color: 'var(--acuity-yellow)' }}>
                  Reliability discounts applied (reassuring answers only)
                </p>
                <ul className="space-y-1.5">
                  {explanation.channel2.discounts.map((d, i) => (
                    <li key={i} className="text-sm p-2 rounded" style={{ background: 'var(--bg-raised)', color: 'var(--text)' }}>
                      <span className="font-medium">{d.label}</span>
                      <span className="text-xs ml-2" style={{ color: 'var(--text-dim)' }}>({d.factor})</span>
                    </li>
                  ))}
                </ul>
              </div>
            )}
          </div>
        )}
      </div>

      {/* Channel 3 — collapsible */}
      <div className="rounded-lg border" style={{ borderColor: 'var(--line)', background: 'var(--bg-card)' }}>
        <button
          onClick={() => setOpenC3(v => !v)}
          className="w-full flex items-center justify-between p-4 text-left"
          aria-expanded={openC3}
        >
          <h3 className="text-xs font-semibold uppercase tracking-wider" style={{ color: 'var(--text-dim)' }}>
            Channel 3 · What was said & what happened since
          </h3>
          <span aria-hidden style={{ color: 'var(--text-dim)' }}>{openC3 ? '▾' : '▸'}</span>
        </button>
        {openC3 && (
          <div className="px-4 pb-4 space-y-3">
            {explanation.channel3.narrative.length > 0 && (
              <div>
                <p className="text-[10px] uppercase mb-1" style={{ color: 'var(--text-dim)' }}>Narrative</p>
                <ul className="space-y-1">
                  {explanation.channel3.narrative.map((n, i) => (
                    <li key={i} className="text-sm">
                      <span className="italic">"{n.phrase}"</span>
                      <span className="text-xs ml-2" style={{ color: 'var(--text-dim)' }}>→ {n.triggered}</span>
                    </li>
                  ))}
                </ul>
              </div>
            )}
            {explanation.channel3.timeline.length > 0 && (
              <div>
                <p className="text-[10px] uppercase mb-1" style={{ color: 'var(--text-dim)' }}>Timeline</p>
                <ul className="space-y-1">
                  {explanation.channel3.timeline.map((t, i) => (
                    <li key={i} className="text-sm flex gap-2" style={{ color: 'var(--text-dim)' }}>
                      <span className="tabular-nums">{new Date(t.at).toLocaleTimeString()}</span>
                      <span>{t.kind}</span>
                      <span>—</span>
                      <span>{t.detail}</span>
                    </li>
                  ))}
                </ul>
              </div>
            )}
            {explanation.channel3.narrative.length === 0 && explanation.channel3.timeline.length === 0 && (
              <p className="text-sm" style={{ color: 'var(--text-dim)' }}>No narrative or timeline events yet.</p>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

function FactorRow({ f }: { f: Factor }) {
  const glyph = f.direction === 'supports' ? '▸' : '▹';
  const color = f.direction === 'supports' ? 'var(--acuity-yellow)' : 'var(--acuity-green)';
  return (
    <li className="text-sm flex items-start gap-2">
      <span style={{ color }} aria-hidden className="mt-0.5">{glyph}</span>
      <span className="flex-1">{f.label}</span>
      <span className="text-xs px-1.5 py-0.5 rounded" style={{ background: 'var(--bg-raised)', color: 'var(--text-dim)' }}>
        {f.source}
      </span>
    </li>
  );
}
