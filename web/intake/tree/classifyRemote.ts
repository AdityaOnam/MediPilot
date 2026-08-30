import type { BranchId } from './types';

/**
 * Tier 2 of branch selection — only called when localClassify() had no
 * confident keyword hit, so the network round-trip sits on the exception
 * path. Resolves to null on any failure, which leaves the patient in
 * whatever branch the local pass already chose (`other` at worst).
 */
export async function classifyRemote(text: string, signal?: AbortSignal): Promise<BranchId | null> {
  if (!text.trim()) return null;
  try {
    const res = await fetch('/api/intake/classify', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ text }),
      signal,
    });
    if (!res.ok) return null;
    const data = (await res.json()) as { branch?: unknown };
    return typeof data?.branch === 'string' ? (data.branch as BranchId) : null;
  } catch {
    return null;
  }
}
