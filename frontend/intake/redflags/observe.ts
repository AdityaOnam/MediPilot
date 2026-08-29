export interface ObserveResponse {
  redFlags: string[];
  fields: Record<string, string>;
}

const EMPTY: ObserveResponse = { redFlags: [], fields: {} };

/**
 * Tier B — asks /api/intake/observe what the patient's own words
 * described. Runs on every free-text answer, in parallel with the
 * deterministic tier A scan that has already completed synchronously in
 * engine.ts.
 *
 * Because tier A has already run, a failure here costs the extra catch,
 * never the safety net — so this resolves to an empty result on any
 * error rather than surfacing one to the patient.
 */
export async function observeRemote(text: string, signal?: AbortSignal): Promise<ObserveResponse> {
  if (!text.trim()) return EMPTY;
  try {
    const res = await fetch('/api/intake/observe', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ text }),
      signal,
    });
    if (!res.ok) return EMPTY;
    const data = (await res.json()) as Partial<ObserveResponse>;
    return {
      redFlags: Array.isArray(data.redFlags) ? data.redFlags.filter((c) => typeof c === 'string') : [],
      fields: data.fields && typeof data.fields === 'object' ? data.fields : {},
    };
  } catch {
    return EMPTY;
  }
}
