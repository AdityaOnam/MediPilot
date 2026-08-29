import { NextRequest, NextResponse } from 'next/server';
import { groqJson, MODEL_FAST } from '@/intake/server/groq';
import { CLASSIFY_SYSTEM, classifyUser } from '@/intake/server/prompts';
import { validateBranch } from '@/intake/server/validate';

/**
 * Complaint text -> one of 16 branch ids.
 *
 * Only reached when the browser's own keyword classifier
 * (intake/tree/localClassify.ts) had no confident hit, so this sits on the
 * exception path. Fails soft to 'other' — a real branch with real
 * questions, never a dead end.
 */
export async function POST(req: NextRequest) {
  let text = '';
  try {
    const body = (await req.json()) as { text?: unknown };
    if (typeof body?.text === 'string') text = body.text;
  } catch {
    // Malformed body — treated the same as an unclassifiable complaint.
  }

  if (!text.trim()) return NextResponse.json({ branch: 'other' });

  const raw = await groqJson({
    system: CLASSIFY_SYSTEM,
    user: classifyUser(text),
    model: MODEL_FAST,
    timeoutMs: 4000,
  });

  return NextResponse.json({ branch: validateBranch(raw) });
}
