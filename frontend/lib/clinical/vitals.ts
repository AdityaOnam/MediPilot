import type { VitalCode, AgeStratum } from '@/lib/api/types';

/**
 * One place that knows what a vital IS — its label, unit, plausible entry
 * range, and the normal band for each age stratum.
 *
 * Before this file the vital entry dialog posted its own lowercase codes
 * ('hr', 'bp_sys', 'temp_c') while the wire type and every renderer used
 * the uppercase VitalCode union ('HR', 'SBP', 'TEMP'). Nothing crashed —
 * the reading was simply stored under a code no lookup matched, so it
 * rendered with the fallback icon, no unit, and no normal-range banding.
 * `normaliseVitalCode` is the single funnel that stops that recurring.
 */

export interface VitalDef {
  code: VitalCode;
  label: string;
  unit: string;
  /** Bounds for the number input — a typo guard, not a clinical range. */
  min: number;
  max: number;
  step?: number;
  /** Shown in the entry dialog's standard grid, in this order. */
  standard: boolean;
}

export const VITALS: Record<VitalCode, VitalDef> = {
  HR:   { code: 'HR',   label: 'Heart Rate',   unit: 'bpm',  min: 20, max: 260, standard: true },
  RR:   { code: 'RR',   label: 'Resp Rate',    unit: '/min', min: 4,  max: 80,  standard: true },
  SBP:  { code: 'SBP',  label: 'Systolic BP',  unit: 'mmHg', min: 40, max: 260, standard: true },
  DBP:  { code: 'DBP',  label: 'Diastolic BP', unit: 'mmHg', min: 20, max: 160, standard: true },
  SPO2: { code: 'SPO2', label: 'SpO₂',    unit: '%',    min: 40, max: 100, standard: true },
  TEMP: { code: 'TEMP', label: 'Temperature',  unit: '°C', min: 28, max: 44, step: 0.1, standard: true },
  GCS:  { code: 'GCS',  label: 'GCS',          unit: '',     min: 3,  max: 15,  standard: true },
  RBS:  { code: 'RBS',  label: 'Blood Glucose', unit: 'mg/dL', min: 10, max: 700, standard: true },
  PAIN: { code: 'PAIN', label: 'Pain Score',   unit: '/10',  min: 0,  max: 10,  standard: true },
};

export const STANDARD_VITALS: VitalDef[] = (Object.keys(VITALS) as VitalCode[])
  .map((c) => VITALS[c])
  .filter((v) => v.standard);

/** Every spelling seen in the wild — the old dialog codes, the backend's
 *  snake_case, and the obvious things a nurse types by hand. */
const ALIASES: Record<string, VitalCode> = {
  hr: 'HR', heart_rate: 'HR', pulse: 'HR', hr_bpm: 'HR',
  rr: 'RR', resp_rate: 'RR', respiratory_rate: 'RR', respirations: 'RR',
  sbp: 'SBP', bp_sys: 'SBP', systolic: 'SBP', systolic_bp: 'SBP', bp_systolic: 'SBP',
  dbp: 'DBP', bp_dia: 'DBP', diastolic: 'DBP', diastolic_bp: 'DBP', bp_diastolic: 'DBP',
  spo2: 'SPO2', sao2: 'SPO2', o2_sat: 'SPO2', oxygen_saturation: 'SPO2', sats: 'SPO2',
  temp: 'TEMP', temp_c: 'TEMP', temperature: 'TEMP', temp_celsius: 'TEMP',
  gcs: 'GCS', glasgow: 'GCS', glasgow_coma_scale: 'GCS',
  rbs: 'RBS', glucose: 'RBS', blood_glucose: 'RBS', blood_sugar: 'RBS', bsl: 'RBS',
  pain: 'PAIN', pain_score: 'PAIN', pain_scale: 'PAIN',
};

/**
 * Map any inbound spelling onto the canonical VitalCode, or return null
 * when it is genuinely something else — a nurse-invented field like "peak
 * flow". Null is a real answer, not a failure: those readings are stored
 * and shown, they just carry no normal range and never reach the scorer.
 */
export function normaliseVitalCode(raw: string): VitalCode | null {
  const key = raw.trim().toLowerCase().replace(/[\s-]+/g, '_');
  if (key.toUpperCase() in VITALS) return key.toUpperCase() as VitalCode;
  return ALIASES[key] ?? null;
}

/** Title-cases a custom code back into something readable on the card. */
export function prettyVitalLabel(code: string): string {
  const known = normaliseVitalCode(code);
  if (known) return VITALS[known].label;
  return code
    .replace(/[_-]+/g, ' ')
    .replace(/\b\w/g, (c) => c.toUpperCase());
}

// ---------------------------------------------------------------------------
// Normal ranges
// ---------------------------------------------------------------------------

type Range = [number, number];

/**
 * Normal ranges by stratum. Paediatric heart and respiratory rates are far
 * from the adult numbers — scoring a 2-year-old's HR of 130 against an
 * adult range would call a normal toddler tachycardic, which is exactly
 * the failure Invariant 3 (always resolve a stratum) exists to prevent.
 */
const RANGES: Partial<Record<VitalCode, Partial<Record<AgeStratum, Range>>>> = {
  HR: {
    neonate: [100, 180], infant: [100, 160], child: [80, 140],
    adolescent: [60, 105], adult: [60, 100], geriatric: [60, 100],
  },
  RR: {
    neonate: [30, 60], infant: [24, 50], child: [18, 34],
    adolescent: [12, 22], adult: [12, 20], geriatric: [12, 22],
  },
  SBP: {
    neonate: [60, 90], infant: [70, 100], child: [85, 115],
    adolescent: [100, 130], adult: [100, 140], geriatric: [105, 150],
  },
  DBP: {
    neonate: [30, 60], infant: [40, 65], child: [50, 75],
    adolescent: [60, 85], adult: [60, 90], geriatric: [60, 90],
  },
  SPO2: {
    neonate: [92, 100], infant: [94, 100], child: [94, 100],
    adolescent: [95, 100], adult: [95, 100], geriatric: [94, 100],
  },
  TEMP: {
    neonate: [36.5, 37.5], infant: [36.5, 37.8], child: [36.4, 37.8],
    adolescent: [36.1, 37.5], adult: [36.1, 37.5], geriatric: [36.0, 37.5],
  },
  GCS: {
    neonate: [15, 15], infant: [15, 15], child: [15, 15],
    adolescent: [15, 15], adult: [15, 15], geriatric: [15, 15],
  },
  RBS: {
    neonate: [45, 110], infant: [60, 120], child: [70, 140],
    adolescent: [70, 140], adult: [70, 140], geriatric: [70, 160],
  },
  PAIN: {
    neonate: [0, 3], infant: [0, 3], child: [0, 3],
    adolescent: [0, 3], adult: [0, 3], geriatric: [0, 3],
  },
};

export type VitalBand = 'below' | 'low' | 'normal' | 'high' | 'above';

/**
 * Where a value sits for this stratum. `low`/`high` are outside normal;
 * `below`/`above` are outside by more than 20% of the range width, which
 * is what the renderer paints red rather than amber.
 */
export function bandForStratum(
  code: string,
  value: number,
  stratum: AgeStratum,
): VitalBand | undefined {
  const canonical = normaliseVitalCode(code);
  if (!canonical) return undefined;
  const range = RANGES[canonical]?.[stratum];
  if (!range) return undefined;

  const [lo, hi] = range;
  if (value >= lo && value <= hi) return 'normal';
  const margin = Math.max((hi - lo) * 0.2, 0.5);
  if (value < lo) return value < lo - margin ? 'below' : 'low';
  return value > hi + margin ? 'above' : 'high';
}

// ---------------------------------------------------------------------------
// Critical thresholds — the RED line, kept separate from the normal range
// ---------------------------------------------------------------------------

/**
 * Where a value stops being "abnormal" and becomes "resuscitation room".
 *
 * These are stated explicitly rather than derived from the normal range,
 * because the two are not the same shape. An earlier version inferred the
 * critical line as "more than 20% of the range width outside normal",
 * which made an adult heart rate of 130 a RED — tachycardic and worth a
 * nurse's attention, certainly, but not on its own a resus call. Anything
 * outside these bounds is; anything merely outside the normal range in
 * `RANGES` above contributes a YELLOW.
 *
 * `null` on either side means there is no critical limit in that
 * direction for that vital.
 */
type CritBounds = [low: number | null, high: number | null];

const CRITICAL: Partial<Record<VitalCode, Partial<Record<AgeStratum, CritBounds>>>> = {
  SPO2: {
    neonate: [88, null], infant: [90, null], child: [90, null],
    adolescent: [92, null], adult: [92, null], geriatric: [90, null],
  },
  GCS: {
    neonate: [13, null], infant: [13, null], child: [13, null],
    adolescent: [13, null], adult: [13, null], geriatric: [13, null],
  },
  RR: {
    neonate: [20, 80], infant: [16, 70], child: [12, 50],
    adolescent: [8, 34], adult: [8, 32], geriatric: [8, 32],
  },
  SBP: {
    neonate: [50, null], infant: [60, null], child: [70, 140],
    adolescent: [85, 190], adult: [90, 220], geriatric: [95, 220],
  },
  HR: {
    neonate: [80, 200], infant: [80, 190], child: [60, 180],
    adolescent: [40, 160], adult: [40, 150], geriatric: [40, 150],
  },
  RBS: {
    neonate: [40, null], infant: [45, 300], child: [50, 350],
    adolescent: [55, 400], adult: [55, 400], geriatric: [60, 400],
  },
  TEMP: {
    neonate: [35.5, 38.5], infant: [35.5, 39.5], child: [35, 40.5],
    adolescent: [35, 41], adult: [35, 41], geriatric: [35, 40],
  },
};

/** True when this reading is critical for the stratum — the RED line. */
export function isCriticalVital(code: string, value: number, stratum: AgeStratum): boolean {
  const canonical = normaliseVitalCode(code);
  if (!canonical) return false;
  const bounds = CRITICAL[canonical]?.[stratum];
  if (!bounds) return false;
  const [low, high] = bounds;
  if (low !== null && value < low) return true;
  if (high !== null && value > high) return true;
  return false;
}

// ---------------------------------------------------------------------------
// Which vitals a presentation actually requires
// ---------------------------------------------------------------------------

/**
 * The vitals the counter must capture before this patient can be scored on
 * anything but their words. Keyed by the intake tree's branch id.
 *
 * This is deliberately a superset per branch rather than a minimal set:
 * an unmeasured vital is an unknown, and the scorer treats unknowns as
 * confidence reducers, so over-asking costs a minute and under-asking
 * costs a band.
 */
const BRANCH_VITALS: Record<string, VitalCode[]> = {
  chest_pain:         ['HR', 'SBP', 'DBP', 'SPO2', 'RR', 'PAIN'],
  breathing:          ['SPO2', 'RR', 'HR', 'TEMP'],
  abdominal:          ['HR', 'SBP', 'TEMP', 'PAIN'],
  neuro:              ['GCS', 'HR', 'SBP', 'RBS', 'SPO2'],
  fever:              ['TEMP', 'HR', 'RR', 'SPO2'],
  trauma:             ['HR', 'SBP', 'SPO2', 'GCS', 'PAIN'],
  bleeding:           ['HR', 'SBP', 'DBP', 'SPO2'],
  gi:                 ['HR', 'SBP', 'TEMP', 'PAIN'],
  obstetric:          ['HR', 'SBP', 'DBP', 'TEMP'],
  poisoning:          ['GCS', 'HR', 'SPO2', 'RR', 'RBS'],
  burn:               ['HR', 'SBP', 'SPO2', 'RR', 'PAIN'],
  allergy:            ['SPO2', 'RR', 'HR', 'SBP'],
  urinary:            ['TEMP', 'HR', 'SBP'],
  mental_behavioural: ['HR', 'SBP', 'RBS', 'TEMP'],
  paeds_general:      ['TEMP', 'HR', 'RR', 'SPO2'],
  other:              ['HR', 'SBP', 'SPO2', 'TEMP'],
};

/** Anything time-critical gets the full observation set regardless of branch. */
const RED_FLAG_VITALS: VitalCode[] = ['HR', 'SBP', 'DBP', 'SPO2', 'RR', 'TEMP', 'GCS'];

export function requiredVitals(input: {
  branch?: string | null;
  redFlagCount?: number;
  ageStratum?: AgeStratum;
}): VitalCode[] {
  const { branch, redFlagCount = 0, ageStratum } = input;

  const base = redFlagCount > 0
    ? RED_FLAG_VITALS
    : (branch && BRANCH_VITALS[branch]) || BRANCH_VITALS.other;

  const set = new Set<VitalCode>(base);

  // The very young and the very old decompensate without the obvious
  // signs, so glucose and temperature are never optional for them.
  if (ageStratum === 'neonate' || ageStratum === 'infant') {
    set.add('TEMP'); set.add('RBS'); set.add('SPO2');
  }
  if (ageStratum === 'geriatric') {
    set.add('TEMP'); set.add('SPO2');
  }

  // Keep the canonical display order rather than insertion order.
  return (Object.keys(VITALS) as VitalCode[]).filter((c) => set.has(c));
}
