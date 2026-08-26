'use client';
import React, { useEffect, useRef, useState } from 'react';

interface Props {
  src: string;
  poster?: string;
  aspect?: '16/9' | '9/16';
  className?: string;
  lazy?: boolean;
}

export function VideoClip({ src, poster, aspect = '16/9', className = '', lazy = true }: Props) {
  const containerRef = useRef<HTMLDivElement>(null);
  const videoRef = useRef<HTMLVideoElement>(null);
  const [isVisible, setIsVisible] = useState(!lazy);

  // Lazy load: only render video when container enters viewport
  useEffect(() => {
    if (!lazy || !containerRef.current) return;
    const observer = new IntersectionObserver(
      ([entry]) => {
        if (entry.isIntersecting) {
          setIsVisible(true);
          observer.disconnect();
        }
      },
      { rootMargin: '200px' }
    );
    observer.observe(containerRef.current);
    return () => observer.disconnect();
  }, [lazy]);

  const handleMouseEnter = () => videoRef.current?.pause();
  const handleMouseLeave = () => videoRef.current?.play().catch(() => {});

  const aspectRatio = aspect === '16/9' ? '16 / 9' : '9 / 16';

  return (
    <div 
      ref={containerRef}
      className={`overflow-hidden rounded-xl border relative ${className}`}
      style={{ aspectRatio, borderColor: 'var(--line)', background: 'var(--bg-raised)' }}
      onMouseEnter={handleMouseEnter}
      onMouseLeave={handleMouseLeave}
    >
      {isVisible && (
        <video
          ref={videoRef}
          src={src}
          poster={poster}
          autoPlay
          muted
          loop
          playsInline
          preload="metadata"
          className="w-full h-full object-cover"
        />
      )}
    </div>
  );
}
