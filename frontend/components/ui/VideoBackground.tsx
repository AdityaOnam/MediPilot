'use client';
import React, { useEffect, useRef, useState } from 'react';

interface Props {
  src: string;
  poster?: string;
  className?: string;
  opacity?: number;
  lazy?: boolean;
}

export function VideoBackground({ src, poster, className = '', opacity = 1, lazy = false }: Props) {
  const containerRef = useRef<HTMLDivElement>(null);
  const [isVisible, setIsVisible] = useState(!lazy);

  useEffect(() => {
    if (!lazy || !containerRef.current) return;
    const observer = new IntersectionObserver(
      ([entry]) => {
        if (entry.isIntersecting) {
          setIsVisible(true);
          observer.disconnect();
        }
      },
      { rootMargin: '100px' }
    );
    observer.observe(containerRef.current);
    return () => observer.disconnect();
  }, [lazy]);

  return (
    <div ref={containerRef} className="absolute inset-0 z-0">
      {isVisible && (
        <video
          className={`video-bg ${className}`}
          style={{ opacity }}
          autoPlay
          muted
          loop
          playsInline
          poster={poster}
          preload={lazy ? 'none' : 'auto'}
        >
          <source src={src} type="video/mp4" />
        </video>
      )}
    </div>
  );
}
