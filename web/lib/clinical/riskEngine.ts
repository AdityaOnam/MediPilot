import type {
  Band, AgeStratum, Measurement, Factor, ConfidenceReducer, RedFlag,
} from '@/lib/api/types';
import { BAND_RANK } from '@/lib/api/types';
import { bandForStratum, normaliseVitalCode, isCriticalVital, VITALS, requiredVitals } from './vitals';

/**
 * The triage risk engine for patients who arrived through /intake.
 *
 * The seeded corpus patients (P-01…P-20) carry a hand-authored probability
 * so the demo's board is reproducible. A patient who walks through intake
 * has no such entry — and the mock's lookup fell back to `?? 0`, so every
 * real intake landed on the board as GREEN no matter what they said. This
 * module is what replaces that zero.
 *
 * Three properties it must have, in order of importance:
 *
 *  1. ESCALATE-ONLY (Invariant 1). `combine` takes the max of every
 *     contributing band and never the min, and a red flag is terminal.
 *     Fresh evidence can raise a band; it can never lower one.
 *  2. DETERMINISTIC. No model call, no randomness. The same inputs give
 *     the same band every time, and `factors` explains which rule fired.
 *  3. HONEST ABOUT UNKNOWNS. A vital that was never measured is a
 *     confidence reducer, never a reassuring "normal". Absence of evidence
 *     is not evidence of absence — see `missing` below.
 */

export interface RiskInput {
  ageStratum: AgeStratum;
  ageStratumInferred?: boolean;
  /** Intake red-flag codes (the 8 ObservationCodes), already deduplicated. */
  redFlagCodes?: string[];
  /** 0–10, as the patient stated it. Never inferred from adjectives. */
  painScore?: number | null;
  measurements?: Measurement[];
  /** Intake tree branch, used to decide which vitals were owed. */
  branch?: string | null;
  /** Human floor — the engine may go above it, never below. */
  humanAssignedBand?: Band | null;
}

export interface RiskResult {
  band: Band;
  /** Monotone with band, used only for ordering and the score readout. */
  probability: number;
  confidence: 'high' | 'moderate' | 'low';
  confidenceReducedBy: ConfidenceReducer[];
  factors: Factor[];
  redFlags: RedFlag[];
  /** Vitals this presentation owed that have not been measured yet. */
  missingVitals: string[];
  inputsUsed: string[];
}

/** Human-readable text for each of the eight intake observation codes. */
const RED_FLAG_TEXT: Record<string, string> = {
  altered_consciousness: 'Altered level of consciousness',
  active_labour_or_bleeding_pregnancy: 'Active labour or bleeding in pregnancy',
  chest_pain_with_sweating_radiation_breathlessness:
    'Chest pain with sweating, radiation or breathlessness',
  difficulty_speaking_full_sentences: 'Cannot speak in full sentences',
  sudden_onesided_weakness_facial_droop_speech_change:
    'Sudden one-sided weakness, facial droop or speech change',
  uncontrolled_bleeding_or_penetrating_injury:
    'Uncontrolled bleeding or penetrating injury',
  poisoning_overdose_or_snakebite: 'Poisoning, overdose or snakebite',
  infant_not_feeding_floppy_inconsolable: 'Infant not feeding, floppy or inconsolable',
};

function maxBand(a: Band, b: Band): Band {
  return BAND_RANK[a] >= BAND_RANK[b] ? a : b;
}

/** Monotone probability per band — ordering only, never shown as a percentage. */
const BAND_PROBABILITY: Record<Band, number> = { RED: 0.88, YELLOW: 0.09, GREEN: 0.004 };

export function computeRisk(input: RiskInput): RiskResult {
  const {
    ageStratum,
    ageStratumInferred = false,
    redFlagCodes = [],
    painScore = null,
    measurements = [],
    branch = null,
    humanAssignedBand = null,
  } = input;

  const factors: Factor[] = [];
  const reducers: ConfidenceReducer[] = [];
  const inputsUsed: string[] = [];
  let band: Band = 'GREEN';

  // -- 1. Red flags. Terminal, and locked downward by construction. -------
  const redFlags: RedFlag[] = redFlagCodes.map((code) => ({
    observation: RED_FLAG_TEXT[code] ?? code,
    mapsTo: 'RED' as const,
    lockedDownward: true as const,
    matchedObservations: [code],
  }));

  if (redFlags.length > 0) {
    band = 'RED';
    inputsUsed.push('intake red-flag table');
    for (const f of redFlags) {
      factors.push({
        label: f.observation,
        direction: 'supports',
        magnitude: 1,
        source: 'rule',
      });
    }
  }

  // -- 2. Measured vitals -------------------------------------------------
  const seen = new Set<string>();
  for (const m of measurements) {
    if (m.value === null) continue;
    // An expired reading is MISSING, not a stale number (Invariant 4).
    if (m.validity === 'expired') {
      reducers.push('stale-reading');
      continue;
    }

    const canonical = normaliseVitalCode(m.code);
    if (!canonical) continue; // nurse-invented field — recorded, never scored
    seen.add(canonical);

    const vb = m.bandForStratum ?? bandForStratum(canonical, m.value, ageStratum);
    if (!vb || vb === 'normal') continue;

    // Outside the normal range is a YELLOW contribution. Past the explicit
    // critical bound for this stratum it is a RED. The two are separate
    // tables on purpose — see the note on CRITICAL in vitals.ts.
    const critical = isCriticalVital(canonical, m.value, ageStratum);
    const severe = vb === 'above' || vb === 'below';
    const contribution: Band = critical ? 'RED' : 'YELLOW';

    band = maxBand(band, contribution);
    inputsUsed.push(`${canonical} ${m.value}${VITALS[canonical].unit}`);
    factors.push({
      label: `${VITALS[canonical].label} ${vb} for ${ageStratum} (${m.value}${VITALS[canonical].unit})${critical ? ' — critical' : ''}`,
      direction: 'supports',
      magnitude: critical ? 1 : severe ? 0.7 : 0.5,
      source: 'gbdt',
    });

    if (m.validity === 'discounted') reducers.push('stale-reading');
  }

  // -- 3. Self-reported pain ---------------------------------------------
  // Skipped entirely once a PAIN reading has been taken at the counter.
  // Both are the patient's own number, but the later one was given to a
  // person who asked directly; carrying both produced cards that argued
  // "pain 8/10 is high" and "pain 0/10 is reassuring" in the same breath.
  const painMeasured = seen.has('PAIN');
  if (!painMeasured && typeof painScore === 'number') {
    inputsUsed.push(`self-reported pain ${painScore}/10`);
    if (painScore >= 8) {
      band = maxBand(band, 'YELLOW');
      factors.push({
        label: `Severe self-reported pain (${painScore}/10)`,
        direction: 'supports',
        magnitude: 0.6,
        source: 'text',
      });
    } else if (painScore <= 2) {
      // Recorded as arguing the other way, but it moves nothing — a low
      // pain score has no de-escalating authority on its own.
      factors.push({
        label: `Low self-reported pain (${painScore}/10)`,
        direction: 'opposes',
        magnitude: 0.2,
        source: 'text',
      });
    }
  }

  // -- 4. Stratum ---------------------------------------------------------
  if (ageStratum === 'neonate' || ageStratum === 'infant') {
    band = maxBand(band, 'YELLOW');
    factors.push({
      label: `${ageStratum} — decompensates without warning signs`,
      direction: 'supports',
      magnitude: 0.55,
      source: 'rule',
    });
    inputsUsed.push(`age stratum ${ageStratum}`);
  }
  if (ageStratumInferred) reducers.push('inferred-stratum');

  // -- 5. What was never measured ----------------------------------------
  const owed = requiredVitals({
    branch,
    redFlagCount: redFlags.length,
    ageStratum,
  });
  const missingVitals = owed.filter((c) => !seen.has(c));
  if (missingVitals.length > 0) reducers.push('missing-field');

  // -- 6. Human floor (Invariant 1) --------------------------------------
  if (humanAssignedBand) band = maxBand(band, humanAssignedBand);

  // -- Confidence ---------------------------------------------------------
  const uniqueReducers = [...new Set(reducers)];
  let confidence: RiskResult['confidence'] = 'high';
  if (missingVitals.length >= owed.length) confidence = 'low';
  else if (uniqueReducers.length >= 2 || missingVitals.length > 0) confidence = 'moderate';

  if (factors.length === 0) {
    factors.push({
      label: 'No deranged vital, red flag or severe pain recorded',
      direction: 'opposes',
      magnitude: 0.3,
      source: 'rule',
    });
  }

  return {
    band,
    probability: BAND_PROBABILITY[band],
    confidence,
    confidenceReducedBy: uniqueReducers,
    factors: factors.sort((a, b) => b.magnitude - a.magnitude),
    redFlags,
    missingVitals,
    inputsUsed,
  };
}
