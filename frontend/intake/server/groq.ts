/**
 * The one place the kiosk talks to Groq. A plain fetch to the
 * OpenAI-compatible endpoint — no SDK, so no new dependency.
 *
 * SERVER ONLY. `GROQ_API_KEY` has no NEXT_PUBLIC_ prefix, so Next will not
 * inline it into client bundles — importing this from a client component
 * would silently read `undefined` and every call would fail soft. Import
 * it only from files under app/api/.
 *
 * Every function here FAILS SOFT (Part 6 of the plan). A missing key, a
 * timeout, a 429, malformed JSON — all resolve to `null`, and each caller
 * turns that into a benign default: classify -> 'other', match -> NONE,
 * observe -> nothing added. A dead network degrades the conversation; it
 * never blocks a patient, and it never discards a red flag, because the
 * deterministic tier A already ran in the browser before we got here.
 */

const GROQ_URL = 'https://api.groq.com/openai/v1/chat/completions';

/**
 * Two models rather than one, chosen from our own bake-off in
 * Backend/MediPilot/Metrics/structurer_bakeoff_table.md:
 *
 *   gpt-oss-120b  F1 0.962, red_flags_missed 0   <- the safety-critical path
 *   gpt-oss-20b   F1 0.816, red_flags_missed 4   <- fine where a miss is benign
 *
 * Observation extraction is where a miss costs something, so it gets the
 * bigger model. Option-matching and branch-classification failures fall
 * back to "please pick one below" and the `other` branch respectively,
 * which are recoverable, so they get the faster one.
 */
export const MODEL_FAST = process.env.MEDIPILOT_GROQ_MODEL_FAST ?? 'openai/gpt-oss-20b';
export const MODEL_OBSERVE = process.env.MEDIPILOT_GROQ_MODEL_OBSERVE ?? 'openai/gpt-oss-120b';

/** Rehearsal switch from the plan's risk table — forces every tier-2 call
 *  to behave as if the network were down, so a demo run can be rehearsed
 *  without burning free-tier quota. */
export function intakeOffline(): boolean {
  return process.env.MEDIPILOT_INTAKE_OFFLINE === '1';
}

export function groqConfigured(): boolean {
  return !!process.env.GROQ_API_KEY && !intakeOffline();
}

export interface GroqJsonArgs {
  system: string;
  user: string;
  model: string;
  timeoutMs: number;
}

/**
 * Asks for a JSON object and returns it parsed, or null. Callers must
 * still validate the SHAPE — this only guarantees "some JSON object came
 * back in time", never that its contents are legal.
 */
export async function groqJson(args: GroqJsonArgs): Promise<unknown | null> {
  const key = process.env.GROQ_API_KEY;
  if (!key || intakeOffline()) return null;

  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), args.timeoutMs);

  try {
    const res = await fetch(GROQ_URL, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Authorization: `Bearer ${key}`,
      },
      body: JSON.stringify({
        model: args.model,
        temperature: 0,
        max_tokens: 400,
        response_format: { type: 'json_object' },
        messages: [
          { role: 'system', content: args.system },
          { role: 'user', content: args.user },
        ],
      }),
      signal: controller.signal,
    });

    if (!res.ok) return null;

    const data = (await res.json()) as {
      choices?: { message?: { content?: string } }[];
    };
    const content = data?.choices?.[0]?.message?.content;
    if (!content) return null;

    return JSON.parse(content);
  } catch {
    // Timeout, abort, network error, or unparseable content.
    return null;
  } finally {
    clearTimeout(timer);
  }
}
