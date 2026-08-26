import type { Band } from '@/lib/api/types';

interface Props {
  band: Band | null;
  abstained?: boolean;
  size?: 'sm' | 'md' | 'lg';
}

/**
 * Every acuity chip carries colour AND glyph AND word (DESIGN_SYSTEM §3, rule 1).
 * Never colour alone. Print greyscale and it must still triage.
 */
export function BandChip({ band, abstained = false, size = 'md' }: Props) {
  const spec = abstained
    ? { color: 'var(--acuity-abstained)', fill: 'var(--acuity-abstained-fill)', glyph: '◇', word: 'NEEDS YOUR EYES' }
    : band === 'RED'
    ? { color: 'var(--acuity-red)', fill: 'var(--acuity-red-fill)', glyph: '▲', word: 'RED · P1' }
    : band === 'YELLOW'
    ? { color: 'var(--acuity-yellow)', fill: 'var(--acuity-yellow-fill)', glyph: '◆', word: 'YELLOW · P2' }
    : band === 'GREEN'
    ? { color: 'var(--acuity-green)', fill: 'var(--acuity-green-fill)', glyph: '●', word: 'GREEN · P3' }
    : { color: 'var(--text-dim)', fill: 'transparent', glyph: '·', word: '—' };

  const sizeCls =
    size === 'sm' ? 'px-1.5 py-0.5 text-xs gap-1'
    : size === 'lg' ? 'px-3 py-1.5 text-base gap-2 font-semibold'
    : 'px-2 py-1 text-sm gap-1.5';

  return (
    <span
      className={`inline-flex items-center rounded ${sizeCls}`}
      style={{ color: spec.color, background: spec.fill, border: `1px solid ${spec.color}` }}
    >
      <span aria-hidden>{spec.glyph}</span>
      <span className="font-medium tracking-wide">{spec.word}</span>
    </span>
  );
}
