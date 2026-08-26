'use client';
import { useEffect, useRef, useState } from 'react';

interface Props {
  value: number;
  label: string;
  prefix?: string;
  suffix?: string;
  decimals?: number;
}

export function StatCounter({ value, label, prefix = '', suffix = '', decimals = 0 }: Props) {
  const [count, setCount] = useState(0);
  const ref = useRef<HTMLDivElement>(null);
  const [isVisible, setIsVisible] = useState(false);

  useEffect(() => {
    const observer = new IntersectionObserver(
      ([entry]) => {
        if (entry.isIntersecting) {
          setIsVisible(true);
          observer.disconnect();
        }
      },
      { threshold: 0.1 }
    );
    if (ref.current) {
      observer.observe(ref.current);
    }
    return () => observer.disconnect();
  }, []);

  useEffect(() => {
    if (!isVisible) return;
    
    let start = 0;
    const duration = 2000;
    const startTime = performance.now();
    
    const animate = (currentTime: number) => {
      const elapsed = currentTime - startTime;
      const progress = Math.min(elapsed / duration, 1);
      
      const ease = progress === 1 ? 1 : 1 - Math.pow(2, -10 * progress);
      
      setCount(value * ease);
      
      if (progress < 1) {
        requestAnimationFrame(animate);
      } else {
        setCount(value);
      }
    };
    
    requestAnimationFrame(animate);
  }, [isVisible, value]);

  const displayValue = count.toFixed(decimals);

  return (
    <div ref={ref} className="flex flex-col">
      <div className="text-4xl md:text-5xl font-bold tabular-nums mb-2">
        {prefix}{displayValue}{suffix}
      </div>
      <div className="text-sm md:text-base font-medium" style={{ color: 'var(--text-dim)' }}>
        {label}
      </div>
    </div>
  );
}
