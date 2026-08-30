import { NextRequest, NextResponse } from 'next/server';
import { groqJson, MODEL_FAST } from '@/intake/server/groq';
import { MATCH_SYSTEM, matchUser } from '@/intake/server/prompts';
import { validateMatch } from '@/intake/server/validate';

interface MatchBody {
  questionPrompt?: unknown;
  patientText?: unknown;
  options?: unknown;
}

interface Opt {
  value: string;
  label: { en: string; hi: string };
}

function parseOptions(raw: unknown): Opt[] {
  if (!Array.isArray(raw)) return [];
  return raw.flatMap((o): Opt[] => {
    if (!o || typeof o !== 'object') return [];
    const rec = o as Record<string, unknown>;
    const label = rec.label as Record<string, unknown> | undefined;
    if (typeof rec.value !== 'string') return [];
    return [{
      value: rec.value,
      label: {
        en: typeof label?.en === 'string' ? label.en : rec.value,
        hi: typeof label?.hi === 'string' ? label.hi : '',
      },
    }];
  });
}

/**
 * Tier 2 of the matcher — a spoken answer that the local matcher could not
 * place, against this question's option list.
 *
 * The model is a picker, not a clinician: its entire allowed output is one
 * of the `value` strings it was handed, or null. validateMatch enforces
 * that against THIS request's options, so a hallucinated option is
 * discarded rather than entering the tree. Fails soft to null, which the
 * kiosk renders as "please pick one of the choices below".
 */
export async function POST(req: NextRequest) {
  let body: MatchBody = {};
  try {
    body = (await req.json()) as MatchBody;
  } catch {
    return NextResponse.json({ matched: null });
  }

  const options = parseOptions(body.options);
  const patientText = typeof body.patientText === 'string' ? body.patientText : '';
  const questionPrompt = typeof body.questionPrompt === 'string' ? body.questionPrompt : '';

  if (!options.length || !patientText.trim()) {
    return NextResponse.json({ matched: null });
  }

  const raw = await groqJson({
    system: MATCH_SYSTEM,
    user: matchUser(questionPrompt, patientText, options),
    model: MODEL_FAST,
    timeoutMs: 3000,
  });

  return NextResponse.json({
    matched: validateMatch(raw, options.map((o) => o.value)),
  });
}
