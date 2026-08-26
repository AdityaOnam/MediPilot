/**
 * Live adapter — talks to the Python orchestrator at NEXT_PUBLIC_API_BASE.
 *
 * The orchestrator emits the frontend contract natively in camelCase,
 * so this adapter is a thin fetch + EventSource wrapper with no field mapping.
 */

import type {
  MediPilotApi,
  SiteConfig,
  Encounter,
  ScoreResponse,
  RecheckTask,
  OverrideRecord,
  SurgeState,
  RControlResponse,
  DecisionInput,
  StreamEvent,
} from '../types';

const BASE = process.env.NEXT_PUBLIC_API_BASE ?? 'http://localhost:8000';

async function get<T>(path: string): Promise<T> {
  const res = await fetch(`${BASE}${path}`);
  if (!res.ok) {
    const body = await res.text().catch(() => '');
    throw new Error(`GET ${path} ${res.status}: ${body}`);
  }
  return res.json();
}

async function post<T>(path: string, body?: unknown): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: body !== undefined ? JSON.stringify(body) : undefined,
  });
  if (!res.ok) {
    const text = await res.text().catch(() => '');
    throw new Error(`POST ${path} ${res.status}: ${text}`);
  }
  return res.json();
}

export function createLiveAdapter(): MediPilotApi {
  return {
    getConfig: () => get<SiteConfig>('/v1/config'),

    getCensus: () => get<Encounter[]>('/v1/census'),

    getEncounter: (id: string) => get<Encounter>(`/v1/encounter/${id}`),

    score: (id: string) => post<ScoreResponse>('/v1/score', { encounterId: id }),

    getRechecks: () => get<RecheckTask[]>('/v1/rechecks'),

    decide: (input: DecisionInput) => post<OverrideRecord>('/v1/decision', input),

    getSurge: () => get<SurgeState>('/v1/surge'),

    setSurge: (active: boolean) => post<SurgeState>('/v1/surge', { active }),

    getAudit: (since?: string) => {
      const qs = since ? `?since=${encodeURIComponent(since)}` : '';
      return get<OverrideRecord[]>(`/v1/audit${qs}`);
    },

    setR: (R: number) => post<RControlResponse>('/v1/control/r', { R }),

    setClockSpeed: (speed: number) =>
      post<{ simTime: string; speed: number }>('/v1/control/clock', { speed }),

    submitIntake: (data) => post<IntakeResponse>('/v1/intake/submit', data),

    structureText: (text: string, language: string) => 
      post<StructureResponse>('/v1/structure', { text, language }),

    addMeasurement: (encounterId: string, measurement: { code: string; value: number; source: string; takenAt: string }) =>
      post<Encounter>(`/v1/encounter/${encounterId}/measurement`, measurement),

    transcribe: async (audio: Blob) => {
      const fd = new FormData();
      fd.append('file', audio, 'audio.webm');
      const res = await fetch(`${BASE}/v1/speech/transcribe`, {
        method: 'POST',
        body: fd
      });
      if (!res.ok) throw new Error('Transcription failed');
      return res.json();
    },

    subscribe: (handler: (e: StreamEvent) => void) => {
      const es = new EventSource(`${BASE}/v1/stream`);

      es.onmessage = (msg) => {
        try {
          const event = JSON.parse(msg.data) as StreamEvent;
          handler(event);
        } catch {
          // ignore malformed events
        }
      };

      es.onerror = () => {
        // EventSource reconnects automatically
      };

      return () => {
        es.close();
      };
    },
  };
}
