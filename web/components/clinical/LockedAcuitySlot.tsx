/**
 * The most important forty lines of code in the prototype.
 *
 * The LLM structurer (M06) extracts fields from what the patient said. It
 * has NO production rule for acuity — its output grammar structurally cannot
 * contain a band. This component makes that architectural claim visible on
 * the intake and card surfaces: an empty, greyed, locked slot with the reason
 * written on its face.
 *
 * Every other team's demo will show an LLM producing a triage level.
 * Ours shows an LLM that structurally cannot.
 */
export function LockedAcuitySlot() {
  return (
    <div className="p-4 rounded-xl border border-[var(--line)] bg-[var(--bg-card)] flex flex-col gap-2">
      <div className="flex items-center gap-2 text-[var(--text-dim)] text-xs font-semibold uppercase tracking-wider">
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5"><rect x="3" y="11" width="18" height="11" rx="2" ry="2"/><path d="M7 11V7a5 5 0 0 1 10 0v4"/></svg>
        Acuity Unavailable
      </div>
      <p className="text-xs text-[var(--text-dim)] mb-1">
        Not produced by language model
      </p>
      
      <details className="text-[10px] text-[var(--text-dim)] group">
        <summary className="cursor-pointer hover:text-[var(--text)] transition-colors list-none inline-flex items-center gap-1">
          <svg className="w-3 h-3 group-open:rotate-90 transition-transform" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><polyline points="9 18 15 12 9 6"/></svg>
          Technical Details
        </summary>
        <div className="mt-2 pl-4 border-l border-[var(--line)]">
          No production rule exists in the output grammar — see architecture layer L1.
        </div>
      </details>
    </div>
  );
}
