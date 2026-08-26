'use client';

import Image from 'next/image';
import { usePathname } from 'next/navigation';

export type MascotPose =
  | 'pose-01' | 'pose-02' | 'pose-03' | 'pose-04'
  | 'pose-05' | 'pose-06' | 'pose-07' | 'pose-08'
  | 'listening' | 'resting' | 'steady' | 'token' | 'human-lane';

interface Props {
  pose: MascotPose;
  size?: number;
  className?: string;
  alt?: string;
  priority?: boolean;
}

/**
 * The MediPilot mascot. Patient-facing surfaces only.
 *
 * DESIGN_SYSTEM §2: "no virtual-nurse persona or avatar" — the mascot is
 * permitted on patient surfaces where its role is announcing and reassuring,
 * and BANNED on clinical surfaces where it would manufacture false authority.
 *
 * Enforced in code, not in memory: a mascot rendered on /board, /card,
 * /control or /audit throws in development so the mistake shows up on the
 * first render, not in a review three weeks later.
 */
const CLINICAL_ROUTES = ['/board', '/card', '/control', '/audit'];

export function Mascot({ pose, size = 200, className, alt, priority }: Props) {
  const pathname = usePathname();

  if (process.env.NODE_ENV !== 'production') {
    if (pathname && CLINICAL_ROUTES.some(r => pathname.startsWith(r))) {
      throw new Error(
        `Mascot pose="${pose}" rendered on clinical surface "${pathname}". ` +
        `See DESIGN_SYSTEM.md §2 — the mascot is banned from every screen where ` +
        `an acuity band, confidence indicator or override is decided.`
      );
    }
  }

  return (
    <Image
      src={`/media/mascot/cutout/${pose}.png`}
      alt={alt ?? 'MediPilot mascot'}
      width={size}
      height={size}
      className={className}
      priority={priority}
      draggable={false}
    />
  );
}
