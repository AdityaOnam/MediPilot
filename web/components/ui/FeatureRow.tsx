import React from 'react';
import { VideoClip } from './VideoClip';

interface Props {
  video: string;
  title: string;
  text: string;
  reverse?: boolean;
}

export function FeatureRow({ video, title, text, reverse = false }: Props) {
  return (
    <div className={`flex flex-col ${reverse ? 'md:flex-row-reverse' : 'md:flex-row'} items-center gap-8 md:gap-12 mb-16 md:mb-24`}>
      <div className="w-full md:w-1/2">
        <VideoClip src={video} className="w-full shadow-2xl" lazy />
      </div>
      <div className="w-full md:w-1/2 flex flex-col justify-center">
        <h3 className="text-xl md:text-2xl lg:text-3xl font-bold mb-3 md:mb-4">{title}</h3>
        <p className="text-base md:text-lg leading-relaxed" style={{ color: 'var(--text-dim)' }}>
          {text}
        </p>
      </div>
    </div>
  );
}
