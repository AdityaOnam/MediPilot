import type { AgeStratum } from './types';

/**
 * Six-stratum resolution (Invariant 3 — age is never assumed before a
 * threshold applies). Mirrors the bands in
 * backend/config/age_strata.yaml so a patient
 * scored by the kiosk and by the orchestrator's own fallback classifier
 * land in the same stratum.
 */
export function resolveStratum(ageYears: number | null): AgeStratum {
  if (ageYears === null || Number.isNaN(ageYears)) return 'adult'; // caller marks inferred
  if (ageYears < 28 / 365.25) return 'neonate';
  if (ageYears < 1) return 'infant';
  if (ageYears < 12) return 'child';
  if (ageYears < 18) return 'adolescent';
  if (ageYears < 65) return 'adult';
  return 'geriatric';
}

export const PAEDIATRIC_STRATA: AgeStratum[] = ['neonate', 'infant', 'child'];
