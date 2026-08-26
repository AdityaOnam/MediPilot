'use client';
import { useEffect, useState } from 'react';

export function useCan3D() {
  const [can3D, setCan3D] = useState(false);

  useEffect(() => {
    const hasConcurrency = navigator.hardwareConcurrency >= 4;
    const reducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    const isMobile = /Android|webOS|iPhone|iPad|iPod|BlackBerry|IEMobile|Opera Mini/i.test(navigator.userAgent);
    
    if (reducedMotion) {
      setCan3D(false);
    } else if (isMobile && navigator.hardwareConcurrency < 6) {
      setCan3D(false);
    } else {
      setCan3D(true);
    }
  }, []);

  return can3D;
}
