import type { RedFlag } from '../api/types';

const RED_FLAG_PATTERNS: { pattern: RegExp; observation: string }[] = [
  { pattern: /crush(ing)?\s+(chest|substernal)\s*pain/i, observation: 'Crushing chest pain' },
  { pattern: /active\s+labo(u)?r/i, observation: 'Active labour' },
  { pattern: /contraction.{0,20}(2|3)\s*min/i, observation: 'Contractions < 4 min apart' },
  { pattern: /unresponsive/i, observation: 'Unresponsive patient' },
  { pattern: /GCS\s*(of\s*)?[3-8]\b/i, observation: 'GCS ≤ 8' },
  { pattern: /status\s*epilepticus/i, observation: 'Status epilepticus' },
  { pattern: /massive\s*(haemorrhage|hemorrhage|bleed)/i, observation: 'Massive haemorrhage' },
  { pattern: /airway\s*(obstruct|comprom)/i, observation: 'Airway compromise' },
  { pattern: /anaphyla/i, observation: 'Anaphylaxis' },
  { pattern: /cardiac\s*arrest/i, observation: 'Cardiac arrest' },
  { pattern: /strok(e|ing).{0,20}(onset|acute|sudden)/i, observation: 'Acute stroke presentation' },
  { pattern: /spo2.{0,10}(8[0-9]|7\d)\s*%/i, observation: 'SpO₂ < 90%' },
  { pattern: /radiat(ing|es?)\s+to\s+(left\s+)?arm/i, observation: 'Pain radiating to arm' },
];

export function scanRedFlags(narrative: string): RedFlag[] {
  const flags: RedFlag[] = [];
  for (const { pattern, observation } of RED_FLAG_PATTERNS) {
    if (pattern.test(narrative)) {
      flags.push({ observation, mapsTo: 'RED', lockedDownward: true });
    }
  }
  return flags;
}

export function hasRedFlags(narrative: string): boolean {
  return RED_FLAG_PATTERNS.some(({ pattern }) => pattern.test(narrative));
}
