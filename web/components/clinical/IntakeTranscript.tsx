'use client';

import { useState } from 'react';
import type { IntakeAnswer } from '@/lib/api/types';

interface Props {
  answers: IntakeAnswer[];
  language?: string | null;
  branch?: string | null;
}

/**
 * What the patient actually said at the kiosk.
 *
 * This is the least familiar input a nurse will meet on this card � the R2
 * plan calls narrative evidence exactly that (�12, Channel 3) and gives it
 * its own space rather than folding it into a feature list. So it is a
 * conversation here, in the order it was asked, not a field dump.
 *
 * Rendering rules that matter:
 *  - The question is shown, not just the answer. "yes" on its own is not a
 *    clinical fact; "Are you sweating? � yes" is.
 *  - Nothing is summarised or re-worded. A nurse deciding whether to trust
 *    this needs the patient's own words, and a paraphrase is a claim.
 *  - No acuity, no scoring, no interpretation. This panel reports; the
 *    card's other channels are where meaning gets attached.
 */
export function IntakeTranscript({ answers, language, branch }: Props) {
  const [open, setOpen] = useState(false);

  if (!answers || answers.length === 0) {
    return (
      <div className="p-4 rounded-xl text-xs" style={{ background: 'var(--bg-card)', border: '1px solid var(--line)', color: 'var(--text-dim)' }}>
        No kiosk conversation on file � this encounter was seeded or entered by staff.
      </div>
    );
  }

  const FIRST = 4;
  const shown = open ? answers : answers.slice(0, FIRST);
  const hidden = answers.length - shown.length;

  return (
    <div className="rounded-xl overflow-hidden" style={{ background: 'var(--bg-card)', border: '1px solid var(--line)' }}>
      <div
        className="px-4 py-2.5 flex items-center justify-between gap-3"
        style={{ background: 'var(--bg-raised)', borderBottom: '1px solid var(--line)' }}
      >
        <span className="text-[10px] font-bold uppercase tracking-widest" style={{ color: 'var(--text-dim)' }}>
          What the patient said
        </span>
        <span className="flex items-center gap-2 text-[10px]" style={{ color: 'var(--text-dim)' }}>
          {branch && (
            <span className="px-1.5 py-0.5 rounded font-mono" style={{ background: 'var(--bg)', border: '1px solid var(--line)' }}>
              {branch}
            </span>
          )}
          {language && <span className="uppercase">{language === 'hi' ? '?????' : 'EN'}</span>}
          <span className="tabular-nums">{answers.length} answers</span>
        </span>
      </div>

      <ol className="divide-y" style={{ borderColor: 'var(--line)' }}>
        {shown.map((a, i) => (
          <li key={a.id + i} className="px-4 py-2.5 flex gap-3">
            <span
              className="shrink-0 w-5 h-5 rounded-full flex items-center justify-center text-[10px] font-bold tabular-nums mt-0.5"
              style={{ background: 'var(--bg-raised)', color: 'var(--text-dim)', border: '1px solid var(--line)' }}
            >
              {i + 1}
            </span>
            <div className="min-w-0">
              <p className="text-[11px] leading-snug" style={{ color: 'var(--text-dim)' }}>
                {a.question}
              </p>
              <p className="text-sm font-medium mt-0.5 break-words" style={{ color: 'var(--text)' }}>
                {a.answer}
              </p>
            </div>
          </li>
        ))}
      </ol>

      {hidden > 0 && (
        <button
          onClick={() => setOpen(true)}
          className="w-full px-4 py-2.5 text-[11px] font-semibold"
          style={{ borderTop: '1px solid var(--line)', color: 'var(--text-dim)', background: 'var(--bg-raised)' }}
        >
          Show {hidden} more {hidden === 1 ? 'answer' : 'answers'}
        </button>
      )}
      {open && answers.length > FIRST && (
        <button
          onClick={() => setOpen(false)}
          className="w-full px-4 py-2.5 text-[11px] font-semibold"
          style={{ borderTop: '1px solid var(--line)', color: 'var(--text-dim)', background: 'var(--bg-raised)' }}
        >
          Collapse
        </button>
      )}
    </div>
  );
}
