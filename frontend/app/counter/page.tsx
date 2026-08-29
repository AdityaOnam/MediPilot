'use client';

import { useEffect, useMemo, useState } from 'react';
import Link from 'next/link';
import { api } from '@/lib/api/client';
import type { Encounter, Band, VitalCode } from '@/lib/api/types';
import { VITALS, STANDARD_VITALS, normaliseVitalCode, bandForStratum, prettyVitalLabel } from '@/lib/clinical/vitals';
import { VitalIcon } from '@/components/clinical/VitalIcon';
import { BandChip } from '@/components/clinical/BandChip';
import { stratumLabel } from '@/lib/clinical/ageBands';

/**
 * The vitals counter — the physical station intake sends patients to.
 *
 * The kiosk tells the patient "go to Counter 3, they will take these
 * measurements". This is the screen at Counter 3. Staff pull the token up,
 * see exactly which vitals that presentation owes (the intake branch
 * decided them, not the person at the desk), enter them, and the patient's
 * band is recomputed against their age stratum.
 *
 * Deliberately NOT the same screen as /card: the person here is taking
 * measurements, not making a triage decision. There is no override
 * control, no band picker, and no way to send anyone home.
 */

type Draft = Record<string, string>;
interface CustomRow { id: number; code: string; unit: string; value: string }

const SOURCES = [
  { value: 'station', label: 'Station device', hint: 'Instrumented bay, timestamped at source' },
  { value: 'nurse', label: 'Nurse', hint: 'Taken by hand at the counter' },
  { value: 'device', label: 'Portable device', hint: 'Handheld monitor' },
];

export default function CounterPage() {
  const [census, setCensus] = useState<Encounter[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [query, setQuery] = useState('');
  const [draft, setDraft] = useState<Draft>({});
  const [custom, setCustom] = useState<CustomRow[]>([]);
  const [source, setSource] = useState('station');
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState<{ token: string; from: Band | null; to: Band | null } | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    const refresh = () => api.getCensus().then(list => { if (!cancelled) setCensus(list); });
    refresh();
    const iv = setInterval(refresh, 2000);
    return () => { cancelled = true; clearInterval(iv); };
  }, []);

  const waiting = census.filter(e => e.state === 'waiting');
  const awaiting = waiting.filter(e => e.awaitingVitals);
  const selected = selectedId ? census.find(e => e.encounterId === selectedId) ?? null : null;

  const matches = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return [];
    return waiting.filter(e =>
      e.token.toLowerCase().includes(q) ||
      e.encounterId.toLowerCase().includes(q) ||
      (e.chiefComplaint ?? '').toLowerCase().includes(q),
    ).slice(0, 6);
  }, [query, waiting]);

  // Which vitals this patient owes. Falls back to the standard set for a
  // corpus patient who never went through intake, so the counter is still
  // usable for a walk-up recheck.
  const owed: VitalCode[] = selected?.requiredVitals?.length
    ? selected.requiredVitals
    : STANDARD_VITALS.map(v => v.code);

  function pick(e: Encounter) {
    setSelectedId(e.encounterId);
    setQuery('');
    setDraft({});
    setCustom([]);
    setResult(null);
    setError(null);
  }

  async function submit() {
    if (!selected) return;
    const readings = [
      ...Object.entries(draft)
        .filter(([, v]) => v.trim() !== '')
        .map(([code, v]) => ({ code, value: Number(v) })),
      ...custom
        .filter(c => c.code.trim() && c.value.trim() !== '')
        .map(c => ({ code: c.code.trim(), value: Number(c.value), unit: c.unit.trim() || undefined })),
    ].filter(r => Number.isFinite(r.value));

    if (readings.length === 0) {
      setError('Enter at least one measurement.');
      return;
    }

    setBusy(true);
    setError(null);
    const before = selected.currentBand;
    try {
      const updated = await api.recordVitals({
        encounterId: selected.encounterId,
        source,
        readings,
      });
      setResult({ token: updated.token, from: before, to: updated.currentBand });
      setDraft({});
      setCustom([]);
      setCensus(c => c.map(e => (e.encounterId === updated.encounterId ? updated : e)));
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Could not save the measurements.');
    } finally {
      setBusy(false);
    }
  }

  const filledCount =
    Object.values(draft).filter(v => v.trim() !== '').length +
    custom.filter(c => c.code.trim() && c.value.trim() !== '').length;

  return (
    <div data-surface="ward" className="min-h-screen" style={{ background: 'var(--bg)', color: 'var(--text)' }}>
      <header
        className="sticky top-0 z-30 px-6 py-4 border-b"
        style={{ background: 'var(--bg)', borderColor: 'var(--line)' }}
      >
        <div className="max-w-6xl mx-auto flex items-center justify-between gap-6">
          <div className="flex items-baseline gap-4">
            <h1 className="text-xl font-semibold">Vitals Counter</h1>
            <span className="text-sm" style={{ color: 'var(--text-dim)' }}>
              {awaiting.length} waiting for measurement
            </span>
          </div>
          <Link
            href="/board"
            className="text-sm font-medium hover:underline"
            style={{ color: 'var(--focus)' }}
          >
            Nurse Board →
          </Link>
        </div>
      </header>

      <main className="max-w-6xl mx-auto p-6 grid gap-6 lg:grid-cols-12">
        {/* -- Queue of patients still owing vitals -------------------- */}
        <aside className="lg:col-span-4 flex flex-col gap-4">
          <div>
            <label className="text-xs font-semibold uppercase tracking-wider block mb-2" style={{ color: 'var(--text-dim)' }}>
              Find by token
            </label>
            <input
              value={query}
              onChange={e => setQuery(e.target.value)}
              placeholder="e.g. 204"
              className="w-full px-4 py-3 rounded-xl outline-none text-lg tabular-nums"
              style={{ background: 'var(--bg-raised)', border: '1px solid var(--line)', color: 'var(--text)' }}
            />
            {matches.length > 0 && (
              <div className="mt-2 flex flex-col gap-1">
                {matches.map(e => (
                  <button
                    key={e.encounterId}
                    onClick={() => pick(e)}
                    className="text-left px-3 py-2 rounded-lg text-sm hover:opacity-80 transition-opacity"
                    style={{ background: 'var(--bg-raised)', border: '1px solid var(--line)' }}
                  >
                    <span className="font-semibold tabular-nums">{e.token}</span>
                    <span className="ml-2" style={{ color: 'var(--text-dim)' }}>
                      {e.chiefComplaint ?? '—'}
                    </span>
                  </button>
                ))}
              </div>
            )}
          </div>

          <div>
            <h2 className="text-xs font-semibold uppercase tracking-wider mb-2" style={{ color: 'var(--text-dim)' }}>
              Awaiting vitals · {awaiting.length}
            </h2>
            <div className="flex flex-col gap-2">
              {awaiting.map(e => (
                <button
                  key={e.encounterId}
                  onClick={() => pick(e)}
                  className="text-left p-3 rounded-xl transition-colors"
                  style={{
                    background: 'var(--bg-card)',
                    border: `1px solid ${e.encounterId === selectedId ? 'var(--focus)' : 'var(--line)'}`,
                  }}
                >
                  <div className="flex items-center justify-between gap-2">
                    <span className="text-lg font-bold tabular-nums">{e.token}</span>
                    <BandChip band={e.currentBand} size="sm" />
                  </div>
                  <p className="text-xs mt-1 truncate" style={{ color: 'var(--text-dim)' }}>
                    {e.chiefComplaint ?? '—'}
                  </p>
                  <div className="flex gap-1 mt-2" style={{ color: 'var(--text-dim)' }}>
                    {(e.requiredVitals ?? []).slice(0, 8).map(c => (
                      <VitalIcon key={c} code={c} size={14} />
                    ))}
                  </div>
                </button>
              ))}
              {awaiting.length === 0 && (
                <p className="text-sm py-4" style={{ color: 'var(--text-dim)' }}>
                  Nobody is waiting for measurement.
                </p>
              )}
            </div>
          </div>
        </aside>

        {/* -- Entry form --------------------------------------------- */}
        <section className="lg:col-span-8">
          {!selected ? (
            <div
              className="rounded-2xl p-10 text-center"
              style={{ background: 'var(--bg-card)', border: '1px dashed var(--line)' }}
            >
              <p style={{ color: 'var(--text-dim)' }}>
                Select a token to record measurements.
              </p>
            </div>
          ) : (
            <div className="flex flex-col gap-5">
              <div
                className="rounded-2xl p-5"
                style={{ background: 'var(--bg-card)', border: '1px solid var(--line)' }}
              >
                <div className="flex items-start justify-between gap-4 flex-wrap">
                  <div>
                    <div className="flex items-baseline gap-3">
                      <span className="text-3xl font-bold tabular-nums">{selected.token}</span>
                      <BandChip band={selected.currentBand} size="sm" />
                    </div>
                    <p className="mt-2 text-sm" style={{ color: 'var(--text-dim)' }}>
                      {stratumLabel(selected.ageStratum, selected.ageStratumInferred)}
                      {selected.sex ? ` · ${selected.sex}` : ''}
                      {selected.counter ? ` · sent to ${selected.counter}` : ''}
                    </p>
                    <p className="mt-2 text-base">{selected.chiefComplaint ?? '—'}</p>
                  </div>
                  <button
                    onClick={() => setSelectedId(null)}
                    className="text-sm hover:underline"
                    style={{ color: 'var(--text-dim)' }}
                  >
                    Clear
                  </button>
                </div>
              </div>

              {result && (
                <div
                  className="rounded-xl px-4 py-3 text-sm font-medium flex items-center gap-3 flex-wrap"
                  style={{
                    background: result.from !== result.to ? 'var(--acuity-red-fill)' : 'var(--acuity-green-fill)',
                    color: result.from !== result.to ? 'var(--acuity-red)' : 'var(--acuity-green)',
                    border: `1px solid ${result.from !== result.to ? 'var(--acuity-red)' : 'var(--acuity-green)'}`,
                  }}
                >
                  Recorded for token {result.token}.
                  {result.from !== result.to
                    ? ` Escalated ${result.from} → ${result.to}.`
                    : ` Band unchanged (${result.to}).`}
                </div>
              )}

              {/* Source */}
              <div>
                <label className="text-xs font-semibold uppercase tracking-wider block mb-2" style={{ color: 'var(--text-dim)' }}>
                  Source
                </label>
                <div className="flex gap-2 flex-wrap">
                  {SOURCES.map(s => (
                    <button
                      key={s.value}
                      onClick={() => setSource(s.value)}
                      title={s.hint}
                      className="px-3 py-2 rounded-lg text-sm font-medium transition-colors"
                      style={
                        source === s.value
                          ? { background: 'var(--mp-red)', color: '#fff', border: '1px solid var(--mp-red)' }
                          : { background: 'var(--bg-raised)', color: 'var(--text-dim)', border: '1px solid var(--line)' }
                      }
                    >
                      {s.label}
                    </button>
                  ))}
                </div>
              </div>

              {/* Required vitals */}
              <div>
                <h3 className="text-xs font-semibold uppercase tracking-wider mb-2" style={{ color: 'var(--text-dim)' }}>
                  Required for this presentation · {owed.length}
                </h3>
                <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
                  {owed.map(code => {
                    const def = VITALS[code];
                    const raw = draft[code] ?? '';
                    const num = Number(raw);
                    const vb = raw !== '' && Number.isFinite(num)
                      ? bandForStratum(code, num, selected.ageStratum)
                      : undefined;
                    const abnormal = vb && vb !== 'normal';
                    const severe = vb === 'above' || vb === 'below';

                    return (
                      <div
                        key={code}
                        className="rounded-xl p-3"
                        style={{
                          background: 'var(--bg-card)',
                          border: `1px solid ${abnormal ? (severe ? 'var(--acuity-red)' : 'var(--acuity-yellow)') : 'var(--line)'}`,
                        }}
                      >
                        <div className="flex items-center justify-between mb-2">
                          <span
                            className="flex items-center gap-1.5 text-xs font-semibold"
                            style={{ color: abnormal ? (severe ? 'var(--acuity-red)' : 'var(--acuity-yellow)') : 'var(--text-dim)' }}
                          >
                            <VitalIcon code={code} size={14} />
                            {def.label}
                          </span>
                          <span className="text-[10px]" style={{ color: 'var(--text-dim)' }}>{def.unit}</span>
                        </div>
                        <input
                          type="number"
                          inputMode="decimal"
                          min={def.min}
                          max={def.max}
                          step={def.step ?? 1}
                          value={raw}
                          onChange={e => setDraft(d => ({ ...d, [code]: e.target.value }))}
                          placeholder="—"
                          className="w-full bg-transparent text-2xl font-semibold outline-none tabular-nums"
                          style={{ color: 'var(--text)' }}
                        />
                        {abnormal && (
                          <p
                            className="text-[10px] mt-1 font-medium"
                            style={{ color: severe ? 'var(--acuity-red)' : 'var(--acuity-yellow)' }}
                          >
                            {vb} for {selected.ageStratum}
                          </p>
                        )}
                      </div>
                    );
                  })}
                </div>
              </div>

              {/* Anything else */}
              <div>
                <div className="flex items-center justify-between mb-2">
                  <div>
                    <h3 className="text-xs font-semibold uppercase tracking-wider" style={{ color: 'var(--text-dim)' }}>
                      Other measurements
                    </h3>
                    <p className="text-[11px] mt-0.5" style={{ color: 'var(--text-dim)' }}>
                      Shown on the card. Not used by the scoring model.
                    </p>
                  </div>
                  <button
                    onClick={() => setCustom(c => [...c, { id: Date.now() + c.length, code: '', unit: '', value: '' }])}
                    className="px-3 py-1.5 rounded-lg text-sm font-medium"
                    style={{ background: 'var(--bg-raised)', border: '1px solid var(--line)', color: 'var(--text)' }}
                  >
                    + Add field
                  </button>
                </div>

                {custom.length > 0 && (
                  <div className="flex flex-col gap-2">
                    {custom.map(row => (
                      <div key={row.id} className="flex gap-2 items-center">
                        <span
                          className="shrink-0 flex items-center justify-center w-9 h-9 rounded-lg"
                          style={{ background: 'var(--bg-raised)', border: '1px solid var(--line)', color: 'var(--text-dim)' }}
                          title={normaliseVitalCode(row.code) ? prettyVitalLabel(row.code) : 'Custom measurement'}
                        >
                          <VitalIcon code={row.code} size={16} />
                        </span>
                        <input
                          value={row.code}
                          onChange={e => setCustom(c => c.map(x => x.id === row.id ? { ...x, code: e.target.value } : x))}
                          placeholder="Measurement name"
                          className="flex-1 min-w-0 px-3 py-2 rounded-lg text-sm outline-none"
                          style={{ background: 'var(--bg-raised)', border: '1px solid var(--line)', color: 'var(--text)' }}
                        />
                        <input
                          value={row.unit}
                          onChange={e => setCustom(c => c.map(x => x.id === row.id ? { ...x, unit: e.target.value } : x))}
                          placeholder="Unit"
                          className="w-20 shrink-0 px-3 py-2 rounded-lg text-sm outline-none"
                          style={{ background: 'var(--bg-raised)', border: '1px solid var(--line)', color: 'var(--text)' }}
                        />
                        <input
                          type="number"
                          value={row.value}
                          onChange={e => setCustom(c => c.map(x => x.id === row.id ? { ...x, value: e.target.value } : x))}
                          placeholder="—"
                          className="w-24 shrink-0 px-3 py-2 rounded-lg text-sm font-semibold outline-none tabular-nums"
                          style={{ background: 'var(--bg-raised)', border: '1px solid var(--line)', color: 'var(--text)' }}
                        />
                        <button
                          onClick={() => setCustom(c => c.filter(x => x.id !== row.id))}
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

              {error && (
                <p className="text-sm" style={{ color: 'var(--acuity-red)' }}>{error}</p>
              )}

              <div className="flex items-center gap-4">
                <button
                  onClick={submit}
                  disabled={busy || filledCount === 0}
                  className="px-6 py-3 rounded-xl font-semibold disabled:opacity-40 transition-opacity"
                  style={{ background: 'var(--mp-red)', color: '#fff' }}
                >
                  {busy ? 'Saving…' : `Record ${filledCount || ''} measurement${filledCount === 1 ? '' : 's'}`}
                </button>
                <Link
                  href={`/card/${selected.encounterId}`}
                  className="text-sm font-medium hover:underline"
                  style={{ color: 'var(--focus)' }}
                >
                  Open full card →
                </Link>
              </div>

              <p className="text-xs leading-relaxed max-w-2xl" style={{ color: 'var(--text-dim)' }}>
                Recording vitals can raise this patient&apos;s band. It can never lower it —
                a band only moves down when a nurse overrides it on the card, which writes
                a signed record.
              </p>
            </div>
          )}
        </section>
      </main>
    </div>
  );
}
