'use client';

import { useEffect, useState } from 'react';
import { BigButton, ContinueBar, TextField } from './controls';
import type { Lang, Question } from '../tree/types';
import { STR, t } from '../strings';

/**
 * Renders any question `kind` from tree data — adding a question is a row
 * edit in tree/branches/*, never a component edit (Part 1).
 *
 * `voiceText` carries the live transcript from useSpeech into the
 * free-text field so the answer writes itself as the patient speaks, the
 * way Google Translate's voice input does. Tapping and typing stay fully
 * available on every kind: voice is a convenience, never a requirement.
 */
export function QuestionCard({
  lang,
  question,
  onSubmit,
  voiceText,
  highlightValue,
}: {
  lang: Lang;
  question: Question;
  onSubmit: (value: string) => void;
  voiceText?: string;
  /** Option value the voice matcher just picked, flashed before it
   *  auto-submits so the patient sees what was understood. */
  highlightValue?: string | null;
}) {
  const [text, setText] = useState('');
  const [scale, setScale] = useState(5);

  // Live transcript overwrites the field while the patient is speaking.
  useEffect(() => {
    if (voiceText !== undefined && voiceText !== '') setText(voiceText);
  }, [voiceText]);

  // A new question starts clean — the previous answer's text must never
  // leak into it.
  useEffect(() => {
    setText('');
    setScale(5);
  }, [question.id]);

  /**
   * What a numeric control should display right now.
   *
   * Numeric questions show what the voice matcher heard, the same way a
   * choice question flashes the option it picked — without this the
   * slider sat at its default until the screen advanced, so a patient who
   * said "seven" got no confirmation before it submitted.
   *
   * Derived rather than copied into state on an effect, so the value the
   * Continue button submits is always the value on screen. Mirroring it
   * left a window during the settle delay where the display said 7 and a
   * tap on Continue would have submitted the old 5.
   */
  const heard = highlightValue != null && highlightValue !== '' ? Number(highlightValue) : NaN;
  const shownScale = Number.isFinite(heard) ? heard : scale;
  const shownText = Number.isFinite(heard) ? String(heard) : text;

  if (question.kind === 'yes_no') {
    // Both neutral — tapping either submits immediately, so there is no
    // selected state to represent. Leaving "Yes" on BigButton's default
    // ("primary") made it render solid red before any answer was given,
    // on every yes/no question in the tree. `highlighted` still flashes
    // whichever one the voice matcher just picked.
    return (
      <div className="grid grid-cols-2 gap-3">
        <BigButton variant="secondary" onClick={() => onSubmit('yes')} highlighted={highlightValue === 'yes'}>
          {lang === 'hi' ? 'हां' : 'Yes'}
        </BigButton>
        <BigButton variant="secondary" onClick={() => onSubmit('no')} highlighted={highlightValue === 'no'}>
          {lang === 'hi' ? 'नहीं' : 'No'}
        </BigButton>
      </div>
    );
  }

  if (question.kind === 'choice' && question.options) {
    return (
      <div className="flex flex-col gap-3">
        {question.options.map((opt) => (
          <BigButton
            key={opt.value}
            variant="secondary"
            onClick={() => onSubmit(opt.value)}
            highlighted={highlightValue === opt.value}
          >
            {t(lang, opt.label)}
          </BigButton>
        ))}
      </div>
    );
  }

  if (question.kind === 'scale_0_10') {
    return (
      <div>
        <div className="flex items-center justify-center gap-4 mb-6">
          <span
            className="text-6xl font-bold tabular-nums transition-transform"
            style={{
              color: 'var(--mp-red)',
              transform: Number.isFinite(heard) ? 'scale(1.12)' : 'scale(1)',
            }}
          >
            {shownScale}
          </span>
        </div>
        <input
          type="range"
          min={0}
          max={10}
          value={shownScale}
          onChange={(e) => setScale(Number(e.target.value))}
          className="w-full"
        />
        <div className="flex justify-between text-xs mt-1" style={{ color: 'var(--text-dim)' }}>
          <span>{lang === 'hi' ? 'दर्द नहीं' : 'No pain'}</span>
          <span>{lang === 'hi' ? 'सबसे तेज' : 'Worst possible'}</span>
        </div>
        <ContinueBar label={t(lang, STR.continue)} onContinue={() => onSubmit(String(shownScale))} />
      </div>
    );
  }

  if (question.kind === 'number') {
    return (
      <div>
        <input
          type="number"
          inputMode="numeric"
          value={shownText}
          onChange={(e) => setText(e.target.value)}
          className="w-full px-5 py-4 rounded-2xl text-2xl text-center outline-none"
          style={{
            background: 'var(--bg-raised)',
            color: 'var(--text)',
            border: `1px solid ${Number.isFinite(heard) ? 'var(--mp-red)' : 'var(--line)'}`,
          }}
        />
        <ContinueBar
          label={t(lang, STR.continue)}
          disabled={!shownText.trim()}
          onContinue={() => onSubmit(shownText.trim())}
        />
      </div>
    );
  }

  // free_text
  return (
    <div>
      <TextField
        value={text}
        onChange={setText}
        placeholder={t(lang, STR.tapToAnswer)}
        onSubmit={() => text.trim() && onSubmit(text.trim())}
      />
      <ContinueBar label={t(lang, STR.continue)} disabled={!text.trim()} onContinue={() => onSubmit(text.trim())} />
    </div>
  );
}
