import React from 'react';

interface Props {
  title: string;
  subtitle?: string;
  className?: string;
}

export function SectionHeading({ title, subtitle, className = '' }: Props) {
  return (
    <div className={`mb-12 ${className}`}>
      <h2 className="text-3xl md:text-4xl font-bold tracking-tight inline-block relative">
        {title}
        <div className="absolute -bottom-2 left-0 h-1 rounded-full bg-gradient-to-r from-[#DF423D] to-[#926A47]" style={{ width: '40%' }} />
      </h2>
      {subtitle && (
        <p className="mt-4 text-lg" style={{ color: 'var(--text-dim)' }}>
          {subtitle}
        </p>
      )}
    </div>
  );
}
