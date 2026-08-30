import type { AgeStratum } from '../api/types';

export interface StratumDef {
  stratum: AgeStratum;
  minDays: number;
  maxDays: number;
  label: string;
}

export const AGE_STRATA: StratumDef[] = [
  { stratum: 'neonate',    minDays: 0,      maxDays: 27,     label: 'Neonate (< 28 d)' },
  { stratum: 'infant',     minDays: 28,     maxDays: 364,    label: 'Infant (28 d – 1 y)' },
  { stratum: 'child',      minDays: 365,    maxDays: 4379,   label: 'Child (1–12 y)' },
  { stratum: 'adolescent', minDays: 4380,   maxDays: 6569,   label: 'Adolescent (12–18 y)' },
  { stratum: 'adult',      minDays: 6570,   maxDays: 23724,  label: 'Adult (18–65 y)' },
  { stratum: 'geriatric',  minDays: 23725,  maxDays: Infinity, label: 'Geriatric (65+ y)' },
];

export function resolveStratum(ageYears: number | null): { stratum: AgeStratum; inferred: boolean } {
  if (ageYears === null) {
    return { stratum: 'adult', inferred: true };
  }
  const days = Math.round(ageYears * 365.25);
  const match = AGE_STRATA.find(s => days >= s.minDays && days <= s.maxDays);
  return { stratum: match?.stratum ?? 'adult', inferred: false };
}

export function stratumLabel(stratum: AgeStratum, inferred: boolean): string {
  const def = AGE_STRATA.find(s => s.stratum === stratum);
  const base = def?.label ?? stratum;
  return inferred ? `${base} (inferred — widest-safety)` : base;
}
