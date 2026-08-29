import type { Question } from '../tree/types';

/**
 * Tier 2 — the Groq picker, behind /api/intake/match. Only reached when
 * tier 1 scored below ACCEPT_THRESHOLD, so the cost and latency of a
 * network call sit on the exception path.
 *
 * The route's output vocabulary is closed by construction: anything the
 * model returns that is not one of the option values is read as NONE
 * here, so a hallucinated option cannot enter the tree.
 */
export async function matchRemote(
  transcript: string,
  question: Question,
  signal?: AbortSignal,
): Promise<string | null> {
  const options = question.options ?? [];
  if (options.length === 0) return null;

  try {
    const res = await fetch('/api/intake/match', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        questionPrompt: question.prompt.en,
        patientText: transcript,
        options: options.map((o) => ({ value: o.value, label: o.label })),
      }),
      signal,
    });
    if (!res.ok) return null;
    const data = (await res.json()) as { matched?: string | null };
    const matched = data?.matched ?? null;
    // Closed vocabulary enforced on this side too — never trust the wire.
    return options.some((o) => o.value === matched) ? matched : null;
  } catch {
    // Fail soft (Part 6). A dead network degrades the conversation to
    // "please pick one below"; it never blocks the patient.
    return null;
  }
}
