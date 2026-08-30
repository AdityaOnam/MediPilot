import React from 'react';

interface Props {
  children: React.ReactNode;
  gradient?: boolean;
  light?: boolean;
  className?: string;
}

export function GlassCard({ children, gradient = false, light = false, className = '' }: Props) {
  const baseClass = light ? 'glass-light' : 'glass';
  const gradientClass = gradient ? 'gradient-border' : '';
  
  return (
    <div className={`rounded-xl p-6 ${baseClass} ${gradientClass} ${className}`}>
      {children}
    </div>
  );
}
