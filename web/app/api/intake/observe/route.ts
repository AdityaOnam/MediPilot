import { NextRequest, NextResponse } from 'next/server';
import { groqJson, MODEL_OBSERVE } from '@/intake/server/groq';
import { OBSERVE_SYSTEM, observeUser } from '@/intake/server/prompts';
import { validateObserve } from '@/intake/server/validate';

/**
 * Tier B of the red-flag layer, and the source of skip-what's-known.
 *
 * This is the endpoint that carries the paper's central architectural
 * claim: the model reports what was said, and a fixed table decides what
 * it means. Its entire allowed output is a subset of eight observation
 * codes plus a handful of verbatim field values — it is never asked how
 * urgent the patient is, and there is no acuity key it could return.
 *
 * It runs IN PARALLEL with the deterministic tier A scan that already ran
 * in the browser, and can only ADD to what that found. So a red flag is
 * never lost to a timeout, a rate limit, or a missing key: this route
 * failing means we lose the extra catch, not the safety net.
 */
export async function POST(req: NextRequest) {
  let text = '';
  try {
    const body = (await req.json()) as { text?: unknown };
    if (typeof body?.text === 'string') text = body.text;
  } catch {
    // Malformed body — nothing to observe.
  }

  if (!text.trim()) return NextResponse.json({ redFlags: [], fields: {} });

  const raw = await groqJson({
    system: OBSERVE_SYSTEM,
    user: observeUser(text),
    model: MODEL_OBSERVE,
    timeoutMs: 4000,
  });

  return NextResponse.json(validateObserve(raw));
}
