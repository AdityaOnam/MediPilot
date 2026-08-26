import { Mascot } from './Mascot';

interface CockpitRingProps {
  micLevel: number;
  isListening: boolean;
  isRedFlag: boolean;
  size?: number;
}

export function CockpitRing({ micLevel, isListening, isRedFlag, size = 200 }: CockpitRingProps) {
  const center = size / 2;
  const radius = center - 4; // leave room for stroke width
  const circumference = 2 * Math.PI * radius;

  // Animate the dash array based on mic level (0-1)
  // If red-flag, steady (full ring). If listening but no mic input, tiny dot.
  // If not listening, just a thin empty ring.
  
  let dash = 0;
  if (isRedFlag) {
    dash = circumference;
  } else if (isListening) {
    // scale micLevel (usually quite small) to something visible
    const amplified = Math.min(1, micLevel * 3); 
    dash = Math.max(circumference * 0.05, circumference * amplified);
  }

  const pose = isRedFlag ? 'steady' : (isListening ? 'listening' : 'pose-01');

  return (
    <div className="relative flex items-center justify-center" style={{ width: size, height: size }}>
      {/* Background track */}
      <svg className="absolute inset-0 w-full h-full" viewBox={`0 0 ${size} ${size}`}>
        <circle
          cx={center}
          cy={center}
          r={radius}
          fill="none"
          stroke="var(--mp-glass)"
          strokeWidth="2"
          opacity={0.3}
        />
        {/* Active mic ring */}
        {isListening && (
          <circle
            cx={center}
            cy={center}
            r={radius}
            fill="none"
            stroke="var(--mp-glass)"
            strokeWidth="4"
            strokeLinecap="round"
            strokeDasharray={`${dash} ${circumference}`}
            strokeDashoffset={circumference * 0.25} // start from top maybe? actually SVG starts from right, we can offset to center it at bottom or something, but let's just let it be.
            className="transition-all duration-75 ease-out"
            style={{ transformOrigin: 'center', transform: 'rotate(-90deg)' }}
          />
        )}
      </svg>
      {/* Mascot in center */}
      <div style={{ zIndex: 10 }}>
        <Mascot pose={pose as any} size={size * 0.6} alt="MediPilot" />
      </div>
    </div>
  );
}
