'use client';

import { useState } from 'react';
import { api } from '@/lib/api/client';
import type { Encounter, VitalCode, AgeStratum } from '@/lib/api/types';
import { VITALS, STANDARD_VITALS, bandForStratum, normaliseVitalCode, prettyVitalLabel } from '@/lib/clinical/vitals';
import { VitalIcon } from './VitalIcon';

interface VitalEntryDialogProps {
  encounterId: string;
  /** Vitals this presentation owes. Sorted to the front and marked, so a
   *  nurse opening the dialog sees what intake actually asked for. */
  requiredVitals?: VitalCode[];
  ageStratum?: AgeStratum;
  onClose: () => void;
  onSubmitted: (e: Encounter) => void;
}

/** A field the nurse added by hand because this patient needed something
 *  the standard set does not cover (peak flow, urine output, a site-
 *  specific score). Recorded and shown on the card, but NOT fed to the
 *  scoring model — the backend only scores vitals it actually knows.
 *  An unrecognised field silently changing a band would be worse than not
 *  scoring it at all, so it is labelled as unscored in the UI. */
interface CustomField {
  id: number;
  code: string;
  unit: string;
  value: string;
}

export function VitalEntryDialog({
  encounterId,
  requiredVitals = [],
  ageStratum = 'adult',
  onClose,
  onSubmitted,
}: VitalEntryDialogProps) {
  const [source, setSource] = useState('nurse');
  const [values, setValues] = useState<Record<string, string>>({});
  const [customFields, setCustomFields] = useState<CustomField[]>([]);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const required = new Set(requiredVitals);
  // Owed vitals first, then the rest of the standard set.
  const ordered = [...STANDARD_VITALS].sort((a, b) => {
    const ra = required.has(a.code) ? 0 : 1;
    const rb = required.has(b.code) ? 0 : 1;
    return ra - rb;
  });

  const filledCustom = customFields.filter(f => f.code.trim() && f.value.trim());
  const filledStandard = Object.entries(values).filter(([, v]) => v.trim());
  const canSubmit = (filledStandard.length > 0 || filledCustom.length > 0) && !submitting;

  const addCustomField = () =>
    setCustomFields(f => [...f, { id: Date.now() + f.length, code: '', unit: '', value: '' }]);

  const updateCustom = (id: number, patch: Partial<CustomField>) =>
    setCustomFields(f => f.map(x => (x.id === id ? { ...x, ...patch } : x)));

  const removeCustom = (id: number) => setCustomFields(f => f.filter(x => x.id !== id));

  const handleSubmit = async () => {
    if (!canSubmit) return;
    setSubmitting(true);
    setError(null);
    try {
      // One call for the whole set, so the encounter re-scores once against
      // the complete picture rather than once per reading — a patient must
      // never transiently band against a half-entered set of vitals.
      const readings = [
        ...filledStandard
          .map(([code, v]) => ({ code, value: parseFloat(v) })),
        ...filledCustom
          .map(f => ({ code: f.code.trim(), value: parseFloat(f.value), unit: f.unit.trim() || undefined })),
      ].filter(r => !isNaN(r.value));

      if (readings.length === 0) {
        setError('Enter at least one numeric measurement.');
        return;
      }

      const updated = await api.recordVitals({ encounterId, source, readings });
      onSubmitted(updated);
      onClose();
    } catch (e) {
      console.error(e);
      setError(e instanceof Error ? e.message : 'Could not save vitals.');
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div
      data-surface="ward"
      className="fixed inset-0 z-50 flex items-center justify-center p-4"
      style={{ background: 'rgba(28,27,26,0.45)', backdropFilter: 'blur(4px)' }}
    >
      <div
        className="rounded-2xl w-full max-w-lg shadow-2xl flex flex-col overflow-hidden"
        style={{ background: 'var(--bg-raised)', border: '1px solid var(--line)', color: 'var(--text)' }}
      >
        <div className="px-6 py-5 flex items-center justify-between" style={{ borderBottom: '1px solid var(--line)' }}>
          <div>
            <h2 className="text-xl font-semibold tracking-tight">Record Vitals</h2>
            <p className="text-sm mt-1" style={{ color: 'var(--text-dim)' }}>
              {requiredVitals.length > 0
                ? `${requiredVitals.length} requested for this presentation`
                : 'Enter new measurements for this patient'}
            </p>
          </div>
          <button onClick={onClose} className="p-2" style={{ color: 'var(--text-dim)' }} aria-label="Close">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M18 6L6 18M6 6l12 12" /></svg>
          </button>
        </div>

        <div className="p-6 overflow-y-auto max-h-[60vh]">
          <div className="mb-6">
            <label className="text-xs font-semibold uppercase tracking-widest mb-2 block" style={{ color: 'var(--text-dim)' }}>
              Source
            </label>
            <div className="flex gap-2 flex-wrap">
              {['nurse', 'station', 'device'].map(s => (
                <button
                  key={s}
                  onClick={() => setSource(s)}
                  className="px-3 py-1.5 rounded-lg text-sm font-medium capitalize transition-colors"
                  style={
                    source === s
                      ? { background: 'var(--mp-red)', color: '#fff', border: '1px solid var(--mp-red)' }
                      : { background: 'var(--bg-card)', color: 'var(--text-dim)', border: '1px solid var(--line)' }
                  }
                >
                  {s}
                </button>
              ))}
            </div>
          </div>

          <div className="grid grid-cols-2 gap-3">
            {ordered.map(vc => {
              const raw = values[vc.code] ?? '';
              const num = parseFloat(raw);
              const vb = raw !== '' && !isNaN(num) ? bandForStratum(vc.code, num, ageStratum) : undefined;
              const abnormal = vb && vb !== 'normal';
              const severe = vb === 'above' || vb === 'below';
              const tint = severe ? 'var(--acuity-red)' : 'var(--acuity-yellow)';
              const isRequired = required.has(vc.code);

              return (
                <div
                  key={vc.code}
                  className="rounded-xl p-3"
                  style={{
                    background: 'var(--bg-card)',
                    border: `1px solid ${abnormal ? tint : isRequired ? 'var(--mp-red)' : 'var(--line)'}`,
                  }}
                >
                  <div className="flex justify-between items-center mb-2 gap-1">
                    <label
                      className="flex items-center gap-1.5 text-xs font-medium min-w-0"
                      style={{ color: abnormal ? tint : 'var(--text-dim)' }}
                    >
                      <VitalIcon code={vc.code} size={14} />
                      <span className="truncate">{vc.label}</span>
                    </label>
                    <span className="text-[10px] shrink-0" style={{ color: 'var(--text-dim)' }}>{vc.unit}</span>
                  </div>
                  <input
                    type="number"
                    inputMode="decimal"
                    min={vc.min}
                    max={vc.max}
                    step={vc.step || 1}
                    value={raw}
                    onChange={(e) => setValues(v => ({ ...v, [vc.code]: e.target.value }))}
                    placeholder="--"
                    className="w-full bg-transparent text-xl font-semibold outline-none tabular-nums"
                    style={{ color: 'var(--text)' }}
                  />
                  {abnormal && (
                    <p className="text-[10px] mt-1 font-medium" style={{ color: tint }}>
                      {vb} for {ageStratum}
                    </p>
                  )}
                </div>
              );
            })}
          </div>

          {/* Anything the standard set doesn't cover. */}
          <div className="mt-6 pt-5" style={{ borderTop: '1px solid var(--line)' }}>
            <div className="flex items-center justify-between mb-3 gap-3">
              <div>
                <label className="text-xs font-semibold uppercase tracking-widest block" style={{ color: 'var(--text-dim)' }}>
                  Other measurements
                </label>
                <p className="text-[11px] mt-1" style={{ color: 'var(--text-dim)' }}>
                  Recorded on the card. Not used by the scoring model.
                </p>
              </div>
              <button
                onClick={addCustomField}
                className="px-3 py-1.5 rounded-lg text-sm font-medium shrink-0"
                style={{ background: 'var(--bg-card)', border: '1px solid var(--line)', color: 'var(--text)' }}
              >
                + Add field
              </button>
            </div>

            {customFields.length === 0 ? (
              <p className="text-sm italic" style={{ color: 'var(--text-dim)' }}>
                No extra fields. Use “Add field” for anything not listed above.
              </p>
            ) : (
              <div className="space-y-2.5">
                {customFields.map(f => (
                  <div key={f.id} className="flex gap-2 items-center">
                    {/* Generic gauge glyph until the typed name matches a
                        known vital, at which point it swaps to that icon. */}
                    <span
                      className="shrink-0 flex items-center justify-center w-9 h-9 rounded-lg"
                      style={{ background: 'var(--bg-card)', border: '1px solid var(--line)', color: 'var(--text-dim)' }}
                      title={normaliseVitalCode(f.code) ? prettyVitalLabel(f.code) : 'Custom measurement'}
                    >
                      <VitalIcon code={f.code} size={16} />
                    </span>
                    <input
                      type="text"
                      value={f.code}
                      onChange={e => updateCustom(f.id, { code: e.target.value })}
                      placeholder="Measurement name"
                      className="flex-1 min-w-0 rounded-lg px-3 py-2 text-sm outline-none"
                      style={{ background: 'var(--bg-card)', border: '1px solid var(--line)', color: 'var(--text)' }}
                    />
                    <input
                      type="text"
                      value={f.unit}
                      onChange={e => updateCustom(f.id, { unit: e.target.value })}
                      placeholder="Unit"
                      className="w-20 shrink-0 rounded-lg px-3 py-2 text-sm outline-none"
                      style={{ background: 'var(--bg-card)', border: '1px solid var(--line)', color: 'var(--text)' }}
                    />
                    <input
                      type="number"
                      value={f.value}
                      onChange={e => updateCustom(f.id, { value: e.target.value })}
                      placeholder="--"
                      className="w-24 shrink-0 rounded-lg px-3 py-2 text-sm font-semibold outline-none tabular-nums"
                      style={{ background: 'var(--bg-card)', border: '1px solid var(--line)', color: 'var(--text)' }}
                    />
                    <button
                      onClick={() => removeCustom(f.id)}
                      aria-label="Remove field"
                      className="p-2 shrink-0"
                      style={{ color: 'var(--text-dim)' }}
                    >
                      <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M18 6L6 18M6 6l12 12" /></svg>
                    </button>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>

        {error && (
          <div
            className="px-6 py-3 text-sm"
            style={{ borderTop: '1px solid var(--acuity-red)', background: 'var(--acuity-red-fill)', color: 'var(--acuity-red)' }}
          >
            {error}
          </div>
        )}

        <div className="px-6 py-4 flex justify-end gap-3" style={{ borderTop: '1px solid var(--line)', background: 'var(--bg)' }}>
          <button onClick={onClose} className="px-4 py-2 text-sm font-medium" style={{ color: 'var(--text-dim)' }}>
            Cancel
          </button>
          <button
            onClick={handleSubmit}
            disabled={!canSubmit}
            className="px-6 py-2 text-sm font-bold rounded-lg disabled:opacity-40 transition-opacity"
            style={{ background: 'var(--mp-red)', color: '#fff' }}
          >
            {submitting ? 'Saving…' : 'Save Vitals'}
          </button>
        </div>
      </div>
    </div>
  );
}
