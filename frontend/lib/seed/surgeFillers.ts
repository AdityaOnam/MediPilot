import type { Encounter, Band, AgeStratum, Measurement } from '../api/types';
import { CADENCE_TABLE } from '../clinical/safeWait';

function iso(minAgo: number): string {
  return new Date(Date.now() - minAgo * 60_000).toISOString();
}

function cadenceFor(band: Band, arrivedMinAgo: number) {
  const c = CADENCE_TABLE[band];
  const now = new Date();
  return {
    ...c,
    nextRescoreAt: new Date(now.getTime() + c.rescoreSec * 1000).toISOString(),
    nextRemeasureAt: new Date(now.getTime() + c.remeasureSec * 1000).toISOString(),
    ceilingBreachesAt: new Date(now.getTime() + (c.ceilingSec - arrivedMinAgo * 60) * 1000).toISOString(),
    breached: false,
  };
}

function fillerEnc(
  id: string,
  token: string,
  band: Band,
  complaint: string,
  arrivedMinAgo: number,
  measurements: Measurement[]
): Encounter {
  return {
    encounterId: id,
    token,
    displayName: null,
    ageYears: 30,
    ageStratum: 'adult',
    ageStratumInferred: false,
    sex: 'M',
    chiefComplaint: complaint,
    arrivedAt: iso(arrivedMinAgo),
    arrivalMode: 'walk-in',
    humanAssignedBand: null,
    currentBand: band,
    measurements,
    cadence: cadenceFor(band, arrivedMinAgo),
    hasPriorRecord: false,
    assisted: true,
    humanAssistanceRequested: false,
    medicalInfoConsent: true,
    state: 'waiting',
    lastScoredAt: iso(1),
  };
}

export function generateSurgeFillers(): Encounter[] {
  // 10 filler patients to push the queue above 18
  // 2 Yellow, 8 Green
  const normalVitals = (minAgo: number): Measurement[] => [
    { code: 'HR', value: 75, unit: 'bpm', takenAt: iso(minAgo - 1), source: 'station', validity: 'fresh' },
    { code: 'SBP', value: 120, unit: 'mmHg', takenAt: iso(minAgo - 1), source: 'station', validity: 'fresh' },
    { code: 'RR', value: 16, unit: 'rpm', takenAt: iso(minAgo - 1), source: 'station', validity: 'fresh' },
    { code: 'SPO2', value: 98, unit: '%', takenAt: iso(minAgo - 1), source: 'device', validity: 'fresh' },
    { code: 'TEMP', value: 36.8, unit: '°C', takenAt: iso(minAgo - 1), source: 'station', validity: 'fresh' }
  ];

  return [
    fillerEnc('F-01', '301', 'YELLOW', 'Moderate abdominal pain, ongoing for 4 hours', 4, normalVitals(4)),
    fillerEnc('F-02', '302', 'YELLOW', 'Dizzy spell, fell down stairs, no LOC', 3, normalVitals(3)),
    fillerEnc('F-03', '303', 'GREEN', 'Laceration on left hand, bleeding stopped', 5, normalVitals(5)),
    fillerEnc('F-04', '304', 'GREEN', 'Cough and cold symptoms x3 days', 4, normalVitals(4)),
    fillerEnc('F-05', '305', 'GREEN', 'Twisted ankle playing football', 3, normalVitals(3)),
    fillerEnc('F-06', '306', 'GREEN', 'Skin rash on both arms, itchy', 3, normalVitals(3)),
    fillerEnc('F-07', '307', 'GREEN', 'Minor dog bite, superficial', 2, normalVitals(2)),
    fillerEnc('F-08', '308', 'GREEN', 'Earache since yesterday', 2, normalVitals(2)),
    fillerEnc('F-09', '309', 'GREEN', 'Renewing prescription, ran out', 1, normalVitals(1)),
    fillerEnc('F-10', '310', 'GREEN', 'Sore throat, mild fever at home', 1, normalVitals(1)),
  ];
}
