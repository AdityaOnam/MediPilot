import { BRANCH_IDS, OBSERVATION_CODES, VOLUNTEERED_FIELDS } from './prompts';

/**
 * Shape validation for everything that comes back from the model.
 *
 * The prompt ASKS for a closed vocabulary; this file is what ENFORCES it.
 * Nothing downstream ever sees a value that was not on the allowed list,
 * so a hallucinated branch, option or observation code cannot enter the
 * tree — it is discarded here, silently, and the caller's fail-soft
 * default applies instead.
 *
 * Pure functions with no I/O, so they can be checked by fixtures without
 * a Groq key (see app/api/intake/selftest).
 */

function asRecord(raw: unknown): Record<string, unknown> | null {
  return raw && typeof raw === 'object' && !Array.isArray(raw)
    ? (raw as Record<string, unknown>)
    : null;
}

/** Unknown or missing branch -> 'other', which is a real branch with real
 *  questions rather than a dead end. */
export function validateBranch(raw: unknown): string {
  const obj = asRecord(raw);
  const branch = obj?.branch;
  return typeof branch === 'string' && (BRANCH_IDS as readonly string[]).includes(branch)
    ? branch
    : 'other';
}

/** Anything that is not one of the option values offered for THIS question
 *  reads as NONE. */
export function validateMatch(raw: unknown, allowedValues: string[]): string | null {
  const obj = asRecord(raw);
  const matched = obj?.matched;
  return typeof matched === 'string' && allowedValues.includes(matched) ? matched : null;
}

export interface ObserveResult {
  redFlags: string[];
  fields: Record<string, string>;
}

export function validateObserve(raw: unknown): ObserveResult {
  const obj = asRecord(raw);
  if (!obj) return { redFlags: [], fields: {} };

  const observations = Array.isArray(obj.observations) ? obj.observations : [];
  const redFlags = Array.from(
    new Set(
      observations.filter(
        (c): c is string =>
          typeof c === 'string' && (OBSERVATION_CODES as readonly string[]).includes(c),
      ),
    ),
  );

  const fieldsIn = asRecord(obj.fields) ?? {};
  const fields: Record<string, string> = {};
  for (const key of VOLUNTEERED_FIELDS) {
    const v = fieldsIn[key];
    // Only a non-empty string counts. A null, an empty string or a
    // fabricated "none" must never cause us to skip asking the question.
    if (typeof v === 'string' && v.trim()) fields[key] = v.trim();
  }

  return { redFlags, fields };
}
