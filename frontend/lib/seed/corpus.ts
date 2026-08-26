/**
 * The authoritative P-01…P-20 demonstration corpus from §14 of the R2 system plan.
 * Each record exists to make exactly one behaviour visible. Do NOT invent new records.
 * All data is synthetic — nothing here is clinical guidance.
 */

import type { Encounter, Measurement, Cadence, Band, AgeStratum } from '../api/types';

function iso(minAgo: number): string {
  return new Date(Date.now() - minAgo * 60_000).toISOString();
}

function cadenceFor(band: Band | 'ABSTAINED', arrivedMinAgo: number): Cadence {
  const table = {
    RED:       { rescoreSec: 60,  remeasureSec: 300,  ceilingSec: 0 },
    YELLOW:    { rescoreSec: 300, remeasureSec: 1800, ceilingSec: 3600 },
    GREEN:     { rescoreSec: 300, remeasureSec: 3600, ceilingSec: 7200 },
    ABSTAINED: { rescoreSec: 300, remeasureSec: 1800, ceilingSec: 900 },
  };
  const c = table[band];
  const now = new Date();
  return {
    ...c,
    nextRescoreAt: new Date(now.getTime() + c.rescoreSec * 1000).toISOString(),
    nextRemeasureAt: new Date(now.getTime() + c.remeasureSec * 1000).toISOString(),
    ceilingBreachesAt: new Date(now.getTime() + (c.ceilingSec - arrivedMinAgo * 60) * 1000).toISOString(),
    breached: false,
  };
}

function vitals(readings: Partial<Record<string, [number | null, string, string]>>): Measurement[] {
  const result: Measurement[] = [];
  for (const [code, tuple] of Object.entries(readings)) {
    if (!tuple) continue;
    const [value, source, validity] = tuple;
    result.push({
      code: code as Measurement['code'],
      value,
      unit: code === 'TEMP' ? '°C' : code === 'SPO2' ? '%' : code === 'PAIN' ? '/10' : code === 'GCS' ? '/15' : 'mmHg',
      takenAt: iso(2),
      source: source as Measurement['source'],
      validity: validity as Measurement['validity'],
    });
  }
  return result;
}

function enc(
  id: string,
  token: string,
  opts: {
    name?: string;
    age?: number | null;
    stratum: AgeStratum;
    stratumInferred?: boolean;
    sex?: 'M' | 'F' | 'O' | null;
    complaint: string;
    arrivedMinAgo: number;
    band: Band | null;
    humanBand?: Band | null;
    measurements: Measurement[];
    assisted?: boolean;
    humanAssistance?: boolean;
    consent?: boolean;
    hasPrior?: boolean;
    state?: Encounter['state'];
    arrivalMode?: Encounter['arrivalMode'];
  }
): Encounter {
  return {
    encounterId: id,
    token,
    displayName: opts.name ?? null,
    ageYears: opts.age ?? null,
    ageStratum: opts.stratum,
    ageStratumInferred: opts.stratumInferred ?? false,
    sex: opts.sex ?? null,
    chiefComplaint: opts.complaint,
    arrivedAt: iso(opts.arrivedMinAgo),
    arrivalMode: opts.arrivalMode ?? 'walk-in',
    humanAssignedBand: opts.humanBand ?? null,
    currentBand: opts.band,
    measurements: opts.measurements,
    cadence: cadenceFor(opts.band ?? 'ABSTAINED', opts.arrivedMinAgo),
    hasPriorRecord: opts.hasPrior ?? false,
    assisted: opts.assisted ?? true,
    humanAssistanceRequested: opts.humanAssistance ?? false,
    medicalInfoConsent: opts.consent ?? true,
    state: opts.state ?? 'waiting',
    lastScoredAt: iso(1),
  };
}

export const CORPUS: Encounter[] = [
  // P-01: Adult crushing chest pain — Red at the door, red-flag fires before model
  enc('P-01', '201', {
    name: 'Rajesh Kumar', age: 52, stratum: 'adult', sex: 'M',
    complaint: 'Crushing chest pain, diaphoretic, radiating to left arm',
    arrivedMinAgo: 8, band: 'RED', humanBand: 'RED',
    measurements: vitals({ HR: [112, 'station', 'fresh'], SBP: [168, 'station', 'fresh'], DBP: [98, 'station', 'fresh'], RR: [24, 'station', 'fresh'], SPO2: [94, 'device', 'fresh'], TEMP: [37.1, 'station', 'fresh'] }),
    arrivalMode: 'ambulance',
  }),

  // P-02: Minor laceration — Green that stays Green (negative control)
  enc('P-02', '202', {
    name: 'Ananya Sharma', age: 28, stratum: 'adult', sex: 'F',
    complaint: 'Minor laceration on forearm, controlled bleeding',
    arrivedMinAgo: 45, band: 'GREEN',
    measurements: vitals({ HR: [72, 'station', 'fresh'], SBP: [118, 'station', 'fresh'], DBP: [76, 'station', 'fresh'], RR: [16, 'station', 'fresh'], SPO2: [99, 'device', 'fresh'], TEMP: [36.8, 'station', 'fresh'] }),
  }),

  // P-03: 3yo paediatric — age stratification
  enc('P-03', '203', {
    name: 'Arjun Mehta', age: 3, stratum: 'child', sex: 'M',
    complaint: '38.5°C fever, tachypnoeic, poor feeding since morning',
    arrivedMinAgo: 22, band: 'YELLOW',
    measurements: vitals({ HR: [142, 'station', 'fresh'], RR: [38, 'station', 'fresh'], SPO2: [96, 'device', 'fresh'], TEMP: [38.5, 'station', 'fresh'] }),
  }),

  // P-04: 75yo geriatric — same temp, different meaning
  enc('P-04', '204', {
    name: 'Kamala Devi', age: 75, stratum: 'geriatric', sex: 'F',
    complaint: '38.5°C fever, mildly confused, unremarkable HR',
    arrivedMinAgo: 20, band: 'YELLOW',
    measurements: vitals({ HR: [78, 'station', 'fresh'], RR: [20, 'station', 'fresh'], SPO2: [95, 'device', 'fresh'], TEMP: [38.5, 'station', 'fresh'], GCS: [13, 'nurse', 'fresh'] }),
  }),

  // P-05: The hero case — mild chest discomfort, deteriorates at min 18
  enc('P-05', '205', {
    name: 'Vikram Patel', age: 45, stratum: 'adult', sex: 'M',
    complaint: 'Mild chest discomfort, "probably just acidity"',
    arrivedMinAgo: 18, band: 'YELLOW',
    measurements: vitals({ HR: [88, 'station', 'fresh'], SBP: [134, 'station', 'fresh'], DBP: [86, 'station', 'fresh'], RR: [20, 'station', 'fresh'], SPO2: [96, 'device', 'fresh'], TEMP: [37.0, 'station', 'fresh'] }),
  }),

  // P-06: Elderly afebrile sepsis — atypical presentation
  enc('P-06', '206', {
    name: 'Suresh Rao', age: 78, stratum: 'geriatric', sex: 'M',
    complaint: 'Confusion, lethargy, no fever, no localising signs',
    arrivedMinAgo: 30, band: 'YELLOW',
    measurements: vitals({ HR: [96, 'station', 'fresh'], SBP: [92, 'station', 'fresh'], DBP: [58, 'station', 'fresh'], RR: [22, 'station', 'fresh'], SPO2: [93, 'device', 'fresh'], TEMP: [36.4, 'station', 'fresh'], GCS: [12, 'nurse', 'fresh'] }),
  }),

  // P-07: Epigastric pain — ambiguous (gastritis vs inferior MI)
  enc('P-07', '207', {
    name: 'Priya Nair', age: 55, stratum: 'adult', sex: 'F',
    complaint: 'Epigastric burning, nausea, could be gastritis or inferior MI',
    arrivedMinAgo: 15, band: 'YELLOW',
    measurements: vitals({ HR: [84, 'station', 'fresh'], SBP: [142, 'station', 'fresh'], DBP: [88, 'station', 'fresh'], RR: [18, 'station', 'fresh'], SPO2: [97, 'device', 'fresh'], TEMP: [37.0, 'station', 'fresh'] }),
  }),

  // P-08: SpO2 bias case — normal reading but dark skin tone
  enc('P-08', '208', {
    name: 'Dayo Okonkwo', age: 34, stratum: 'adult', sex: 'M',
    complaint: 'Dyspnoea, distressed appearance, SpO2 reads 96%',
    arrivedMinAgo: 12, band: 'YELLOW',
    measurements: vitals({ HR: [104, 'station', 'fresh'], RR: [26, 'station', 'fresh'], SPO2: [96, 'device', 'fresh'], TEMP: [37.2, 'station', 'fresh'] }),
  }),

  // P-09: Stale vitals — freshness contract demonstration
  enc('P-09', '209', {
    name: 'Meena Gupta', age: 42, stratum: 'adult', sex: 'F',
    complaint: 'Abdominal pain, vitals taken 3 hours ago',
    arrivedMinAgo: 180, band: 'GREEN',
    measurements: vitals({ HR: [76, 'station', 'expired'], SBP: [120, 'station', 'expired'], RR: [16, 'station', 'expired'], SPO2: [98, 'device', 'expired'], TEMP: [37.0, 'station', 'expired'] }),
  }),

  // P-10: Sensor loss mid-wait
  enc('P-10', '210', {
    name: 'Anil Verma', age: 60, stratum: 'adult', sex: 'M',
    complaint: 'Chest tightness, cardiac monitor dropped out',
    arrivedMinAgo: 25, band: 'YELLOW',
    measurements: vitals({ HR: [null, 'device', 'expired'], SBP: [148, 'station', 'discounted'], RR: [22, 'nurse', 'fresh'], SPO2: [null, 'device', 'expired'] }),
  }),

  // P-11: Zero history, first visit
  enc('P-11', '211', {
    name: 'Farhan Sheikh', age: 38, stratum: 'adult', sex: 'M',
    complaint: 'Severe headache, photophobia, neck stiffness',
    arrivedMinAgo: 10, band: 'YELLOW',
    measurements: vitals({ HR: [92, 'station', 'fresh'], SBP: [156, 'station', 'fresh'], RR: [18, 'station', 'fresh'], SPO2: [98, 'device', 'fresh'], TEMP: [38.8, 'station', 'fresh'] }),
    hasPrior: false,
  }),

  // P-12: Rich prior history via ABHA
  enc('P-12', '212', {
    name: 'Lakshmi Iyer', age: 62, stratum: 'adult', sex: 'F',
    complaint: 'Recurrent chest pain, known CAD, on anticoagulants',
    arrivedMinAgo: 14, band: 'YELLOW',
    measurements: vitals({ HR: [80, 'station', 'fresh'], SBP: [138, 'station', 'fresh'], RR: [18, 'station', 'fresh'], SPO2: [97, 'device', 'fresh'], TEMP: [36.9, 'station', 'fresh'] }),
    hasPrior: true,
  }),

  // P-13: Language barrier
  enc('P-13', '213', {
    name: 'Thanh Nguyen', age: 50, stratum: 'adult', sex: 'M',
    complaint: 'Abdominal distension, speaks neither Hindi nor English',
    arrivedMinAgo: 35, band: 'YELLOW',
    measurements: vitals({ HR: [88, 'station', 'fresh'], SBP: [126, 'station', 'fresh'], RR: [20, 'station', 'fresh'], SPO2: [97, 'device', 'fresh'], TEMP: [37.4, 'station', 'fresh'] }),
  }),

  // P-14: Nurse override — rigid abdomen found on exam
  enc('P-14', '214', {
    name: 'Ravi Shankar', age: 48, stratum: 'adult', sex: 'M',
    complaint: 'Abdominal pain, initially Yellow, nurse finds rigid abdomen',
    arrivedMinAgo: 28, band: 'YELLOW', humanBand: 'YELLOW',
    measurements: vitals({ HR: [98, 'station', 'fresh'], SBP: [108, 'station', 'fresh'], DBP: [68, 'station', 'fresh'], RR: [24, 'station', 'fresh'], SPO2: [96, 'device', 'fresh'], TEMP: [37.8, 'station', 'fresh'] }),
  }),

  // P-15: OOD — abstains out loud, Yellow floor
  enc('P-15', '215', {
    name: 'Meera Nair', age: 29, stratum: 'adult', sex: 'F',
    complaint: 'Unusual presentation unlike anything in local distribution',
    arrivedMinAgo: 12, band: null,
    measurements: vitals({ HR: [110, 'station', 'fresh'], SBP: [100, 'station', 'fresh'], RR: [28, 'station', 'fresh'], SPO2: [94, 'device', 'fresh'], TEMP: [36.2, 'station', 'fresh'] }),
  }),

  // P-16: Unaccompanied, unknown age, non-responsive
  enc('P-16', '216', {
    age: null, stratum: 'adult', stratumInferred: true, sex: null,
    complaint: 'Found unresponsive near entrance, no ID, age unknown',
    arrivedMinAgo: 5, band: 'RED', humanBand: 'RED',
    measurements: vitals({ HR: [56, 'station', 'fresh'], SBP: [84, 'station', 'fresh'], RR: [10, 'station', 'fresh'], SPO2: [88, 'device', 'fresh'], GCS: [6, 'nurse', 'fresh'] }),
    assisted: false, humanAssistance: false,
    arrivalMode: 'brought-by-bystander',
  }),

  // P-17: Declines to share medical history
  enc('P-17', '217', {
    name: 'Deepa Iyer', age: 35, stratum: 'adult', sex: 'F',
    complaint: 'Palpitations, anxiety, declines to share medical history',
    arrivedMinAgo: 40, band: 'GREEN',
    measurements: vitals({ HR: [102, 'station', 'fresh'], SBP: [128, 'station', 'fresh'], RR: [18, 'station', 'fresh'], SPO2: [99, 'device', 'fresh'], TEMP: [36.7, 'station', 'fresh'] }),
    consent: false,
  }),

  // P-18: Active labour — red flag on narrative alone
  enc('P-18', '218', {
    name: 'Sunita Devi', age: 26, stratum: 'adult', sex: 'F',
    complaint: 'Active labour, contractions 3 min apart, vitals unremarkable',
    arrivedMinAgo: 3, band: 'RED', humanBand: 'RED',
    measurements: vitals({ HR: [92, 'station', 'fresh'], SBP: [122, 'station', 'fresh'], RR: [20, 'station', 'fresh'], SPO2: [99, 'device', 'fresh'], TEMP: [37.0, 'station', 'fresh'] }),
    arrivalMode: 'ambulance',
  }),

  // P-19: Stoic patient — denies pain, vitals disagree
  enc('P-19', '219', {
    name: 'Harish Reddy', age: 68, stratum: 'geriatric', sex: 'M',
    complaint: '"I\'m fine" — but tachycardic, hypertensive, diaphoretic',
    arrivedMinAgo: 16, band: 'YELLOW',
    measurements: vitals({ HR: [118, 'station', 'fresh'], SBP: [178, 'station', 'fresh'], DBP: [104, 'station', 'fresh'], RR: [24, 'station', 'fresh'], SPO2: [93, 'device', 'fresh'], TEMP: [37.0, 'station', 'fresh'], PAIN: [2, 'patient', 'fresh'] }),
  }),

  // P-20: Two rechecks missed under load — wait-ceiling breach
  enc('P-20', '220', {
    name: 'Pooja Singh', age: 32, stratum: 'adult', sex: 'F',
    complaint: 'Ankle sprain, Green, but two rechecks missed under surge',
    arrivedMinAgo: 130, band: 'GREEN',
    measurements: vitals({ HR: [74, 'station', 'discounted'], SBP: [116, 'station', 'discounted'], RR: [14, 'station', 'discounted'], SPO2: [99, 'device', 'discounted'], TEMP: [36.6, 'station', 'discounted'] }),
  }),
];
