'use client';

import { useEffect, useRef } from 'react';
import { speak, cancelSpeech } from '../voice/tts';
import type { Lang } from '../tree/types';

/**
 * Shared layout for every intake screen, and the one place the
 * mount -> speak -> (arm -> listen, once B4 lands) cycle lives — so no
 * screen can forget to talk (Part 5 of the plan). `spokenText` is the
 * exact words also shown on screen; pass a shorter version explicitly
 * when the two must differ (consent legalese), never silently.
 */
export function Screen({
  lang,
  spokenText,
  title,
  subtitle,
  children,
  onBack,
  wide = false,
}: {
  lang: Lang;
  /** What MediPilot says aloud on mount. Pass '' to stay silent
   *  (e.g. a screen the patient just navigated back to manually). */
  spokenText: string;
  title?: string;
  subtitle?: string;
  children: React.ReactNode;
  onBack?: () => void;
  wide?: boolean;
}) {
  const spokenRef = useRef<string | null>(null);

  useEffect(() => {
    // Re-speak only when the text actually changes, not on every re-render
    // (a parent state update while the same question is on screen must not
    // restart the utterance).
    if (spokenRef.current === spokenText) return;
    spokenRef.current = spokenText;
    if (spokenText) speak(spokenText, lang);
    return () => cancelSpeech();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [spokenText, lang]);

  return (
    <div
      data-surface="patient"
      className="min-h-screen flex flex-col"
      style={{ background: 'var(--bg)', color: 'var(--text)' }}
    >
      <div className={`mx-auto w-full flex-1 flex flex-col px-6 py-10 ${wide ? 'max-w-2xl' : 'max-w-md'}`}>
        {onBack && (
          <button
            type="button"
            onClick={onBack}
            className="self-start mb-6 text-sm opacity-60 hover:opacity-100 transition-opacity"
          >
            ← {lang === 'hi' ? 'वापस' : 'Back'}
          </button>
        )}

        {title && (
          <h1 className="text-2xl font-semibold leading-snug mb-2" style={{ color: 'var(--text)' }}>
            {title}
          </h1>
        )}
        {subtitle && (
          <p className="text-base mb-8" style={{ color: 'var(--text-dim)' }}>
            {subtitle}
          </p>
        )}

        <div className="flex-1 flex flex-col justify-center gap-4">{children}</div>
      </div>
    </div>
  );
}
