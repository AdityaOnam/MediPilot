import { normaliseVitalCode } from '@/lib/clinical/vitals';

/**
 * One glyph per vital, plus a deliberate generic fallback.
 *
 * The fallback is the point, not an afterthought: a nurse can add any
 * measurement she likes ("peak flow", "urine output") and that reading
 * still needs to render as a first-class row on the card. It gets the
 * neutral gauge glyph, which reads as "a measurement" without pretending
 * to be a specific one.
 *
 * Everything is hand-drawn inline SVG on a 24×24 grid with
 * `stroke="currentColor"`, so the icon inherits the acuity colour the
 * surrounding chip already computed and needs no per-theme variant. No
 * icon-font, no sprite sheet, no network request — which also means these
 * work inside the CSP-restricted Artifact renderer.
 */

export type VitalIconProps = {
  /** Any spelling — normalised internally. Unknown codes get the fallback. */
  code: string;
  size?: number;
  className?: string;
};

const PATHS: Record<string, React.ReactNode> = {
  // Heart
  HR: <path d="M19 14c1.49-1.46 3-3.21 3-5.5A5.5 5.5 0 0 0 16.5 3c-1.76 0-3 .5-4.5 2-1.5-1.5-2.74-2-4.5-2A5.5 5.5 0 0 0 2 8.5c0 2.3 1.5 4.05 3 5.5l7 7Z" />,

  // Lungs
  RR: (
    <>
      <path d="M12 3v9" />
      <path d="M8.5 8.5C8.5 6.5 6 6 5 7.5S3 12 3 15a3 3 0 0 0 5.5 1.7Z" />
      <path d="M15.5 8.5C15.5 6.5 18 6 19 7.5S21 12 21 15a3 3 0 0 1-5.5 1.7Z" />
    </>
  ),

  // Blood-pressure cuff / gauge
  SBP: (
    <>
      <rect x="3" y="7" width="13" height="10" rx="2" />
      <path d="M16 10h2a3 3 0 0 1 0 6h-2" />
      <path d="M7 12h5" />
    </>
  ),
  DBP: (
    <>
      <rect x="3" y="7" width="13" height="10" rx="2" />
      <path d="M16 10h2a3 3 0 0 1 0 6h-2" />
      <path d="M7 14h5" />
    </>
  ),

  // Droplet with O2 sense
  SPO2: (
    <>
      <path d="M12 22a7 7 0 0 0 7-7c0-2-1-3.9-3-5.5s-3.5-4-4-6.5c-.5 2.5-2 4.9-4 6.5C6 11.1 5 13 5 15a7 7 0 0 0 7 7z" />
      <circle cx="12" cy="15" r="2.2" />
    </>
  ),

  // Thermometer
  TEMP: (
    <>
      <path d="M14 14.76V3.5a2.5 2.5 0 0 0-5 0v11.26a4.5 4.5 0 1 0 5 0z" />
      <path d="M12 8v6" />
    </>
  ),

  // Head / consciousness
  GCS: (
    <>
      <path d="M12 3a7 7 0 0 0-7 7c0 2.2 1 3.6 1.8 4.7.5.7.7 1.2.7 2V18a2 2 0 0 0 2 2h5a2 2 0 0 0 2-2v-1.3c0-.8.2-1.3.7-2C18 13.6 19 12.2 19 10a7 7 0 0 0-7-7z" />
      <path d="M9.5 10.5h5" />
    </>
  ),

  // Glucose drop with rising trace
  RBS: (
    <>
      <path d="M12 21a6 6 0 0 0 6-6c0-3-3.5-6.5-6-10-2.5 3.5-6 7-6 10a6 6 0 0 0 6 6z" />
      <path d="M9 15.5l1.8-2 1.6 1.4 2.1-2.6" />
    </>
  ),

  // Pain — a spark / alert on a body point
  PAIN: (
    <>
      <path d="M13 2L4.5 13H11l-1 9 8.5-11H12l1-9z" />
    </>
  ),
};

/** The generic gauge — used for anything the nurse invents. */
const FALLBACK = (
  <>
    <circle cx="12" cy="12" r="9" />
    <path d="M12 12l4-2.5" />
    <path d="M12 7v1" />
    <path d="M7 12H6" />
    <path d="M18 12h-1" />
  </>
);

export function VitalIcon({ code, size = 16, className }: VitalIconProps) {
  const canonical = normaliseVitalCode(code);
  const glyph = (canonical && PATHS[canonical]) || FALLBACK;

  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
      className={className}
      aria-hidden="true"
      focusable="false"
    >
      {glyph}
    </svg>
  );
}

/** True when this code has a purpose-drawn glyph rather than the gauge.
 *  The counter screen uses it to caption custom readings differently. */
export function hasDedicatedIcon(code: string): boolean {
  const canonical = normaliseVitalCode(code);
  return !!canonical && canonical in PATHS;
}
