'use client';

import { useState } from 'react';
import { api } from '@/lib/api/client';
import type { Encounter } from '@/lib/api/types';

interface VitalEntryDialogProps {
  encounterId: string;
  onClose: () => void;
  onSubmitted: (e: Encounter) => void;
}

const VITAL_CONFIGS = [
  { code: 'hr', label: 'Heart Rate', unit: 'bpm', min: 30, max: 250 },
  { code: 'rr', label: 'Resp Rate', unit: 'rpm', min: 5, max: 60 },
  { code: 'bp_sys', label: 'Sys BP', unit: 'mmHg', min: 50, max: 250 },
  { code: 'spo2', label: 'SpO₂', unit: '%', min: 50, max: 100 },
  { code: 'temp_c', label: 'Temp', unit: '°C', min: 30, max: 43, step: 0.1 },
  { code: 'gcs', label: 'GCS', unit: '', min: 3, max: 15 },
  { code: 'pain_score', label: 'Pain', unit: '/10', min: 0, max: 10 },
];

export function VitalEntryDialog({ encounterId, onClose, onSubmitted }: VitalEntryDialogProps) {
  const [source, setSource] = useState('nurse');
  const [values, setValues] = useState<Record<string, string>>({});
  const [submitting, setSubmitting] = useState(false);

  const canSubmit = Object.keys(values).length > 0 && !submitting;

  const handleSubmit = async () => {
    if (!canSubmit) return;
    setSubmitting(true);
    try {
      const now = new Date().toISOString();
      let lastEnc: Encounter | null = null;
      for (const [code, valStr] of Object.entries(values)) {
        if (!valStr) continue;
        const value = parseFloat(valStr);
        if (isNaN(value)) continue;
        lastEnc = await api.addMeasurement(encounterId, { code, value, source, takenAt: now });
      }
      if (lastEnc) onSubmitted(lastEnc);
      onClose();
    } catch (e) {
      console.error(e);
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm p-4">
      <div className="bg-[#151923] border border-white/10 rounded-2xl w-full max-w-lg shadow-2xl flex flex-col overflow-hidden animate-in fade-in zoom-in-95 duration-200">
        
        <div className="px-6 py-5 border-b border-white/10 flex items-center justify-between">
          <div>
            <h2 className="text-xl font-semibold text-white tracking-tight">Record Vitals</h2>
            <p className="text-sm text-white/50 mt-1">Enter new measurements for patient</p>
          </div>
          <button onClick={onClose} className="text-white/40 hover:text-white transition-colors p-2">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M18 6L6 18M6 6l12 12"/></svg>
          </button>
        </div>

        <div className="p-6 overflow-y-auto max-h-[60vh]">
          <div className="mb-6">
            <label className="text-xs font-semibold text-white/50 uppercase tracking-widest mb-2 block">Source</label>
            <div className="flex gap-2">
              {['nurse', 'recheck_station', 'device'].map(s => (
                <button
                  key={s}
                  onClick={() => setSource(s)}
                  className={`px-3 py-1.5 rounded-lg text-sm font-medium border transition-colors ${
                    source === s 
                      ? 'bg-[#58A6FF]/20 border-[#58A6FF]/50 text-[#58A6FF]' 
                      : 'bg-white/5 border-white/10 text-white/60 hover:text-white/90 hover:bg-white/10'
                  }`}
                >
                  {s.replace('_', ' ')}
                </button>
              ))}
            </div>
          </div>

          <div className="grid grid-cols-2 gap-4">
            {VITAL_CONFIGS.map(vc => (
              <div key={vc.code} className="bg-white/[0.02] border border-white/5 rounded-xl p-3 focus-within:border-[#58A6FF]/50 focus-within:bg-[#58A6FF]/5 transition-colors">
                <div className="flex justify-between items-end mb-2">
                  <label className="text-xs font-medium text-white/60">{vc.label}</label>
                  <span className="text-[10px] text-white/30 font-medium">{vc.unit}</span>
                </div>
                <input
                  type="number"
                  min={vc.min}
                  max={vc.max}
                  step={vc.step || 1}
                  value={values[vc.code] || ''}
                  onChange={(e) => setValues(v => ({ ...v, [vc.code]: e.target.value }))}
                  placeholder="--"
                  className="w-full bg-transparent text-xl font-semibold text-white placeholder-white/20 outline-none tabular-nums"
                />
              </div>
            ))}
          </div>
        </div>

        <div className="px-6 py-4 border-t border-white/10 bg-black/20 flex justify-end gap-3">
          <button 
            onClick={onClose}
            className="px-4 py-2 text-sm font-medium text-white/70 hover:text-white transition-colors"
          >
            Cancel
          </button>
          <button 
            onClick={handleSubmit}
            disabled={!canSubmit}
            className="px-6 py-2 bg-[#58A6FF] hover:bg-[#468BE6] text-black text-sm font-bold rounded-lg shadow-[0_0_15px_rgba(88,166,255,0.3)] disabled:opacity-50 disabled:shadow-none transition-all"
          >
            {submitting ? 'Saving...' : 'Save Vitals'}
          </button>
        </div>
      </div>
    </div>
  );
}
