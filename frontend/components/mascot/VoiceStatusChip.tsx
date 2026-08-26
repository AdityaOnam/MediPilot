interface VoiceStatusChipProps {
  supported: boolean;
  isListening: boolean;
  isSpeaking: boolean;
  error: string | null;
  globalMuted?: boolean;
}

export function VoiceStatusChip({ supported, isListening, isSpeaking, error, globalMuted }: VoiceStatusChipProps) {
  if (!supported) {
    return (
      <div className="inline-flex items-center gap-2 px-3 py-1.5 rounded-full text-xs border" style={{ borderColor: 'var(--line)', color: 'var(--text-dim)', background: 'var(--bg-card)' }}>
        <span>⌨</span>
        <span>Type your answer</span>
      </div>
    );
  }

  if (error) {
    return (
      <div className="inline-flex items-center gap-2 px-3 py-1.5 rounded-full text-xs border" style={{ borderColor: 'var(--accent)', color: 'var(--accent)', background: 'var(--bg-card)' }}>
        <span>❌</span>
        <span className="truncate max-w-[150px]">{error}</span>
      </div>
    );
  }

  if (globalMuted) {
    return (
      <div className="inline-flex items-center gap-2 px-3 py-1.5 rounded-full text-xs border" style={{ borderColor: 'var(--line)', color: 'var(--text-dim)', background: 'var(--bg-card)' }}>
        <span>🔇</span>
        <span>Muted</span>
      </div>
    );
  }

  if (isSpeaking) {
    return (
      <div className="inline-flex items-center gap-2 px-3 py-1.5 rounded-full text-xs font-medium border" style={{ borderColor: 'var(--focus)', color: 'var(--focus)', background: 'var(--bg-card)' }}>
        <span>🔊</span>
        <span>Speaking…</span>
      </div>
    );
  }

  if (isListening) {
    return (
      <div className="inline-flex items-center gap-2 px-3 py-1.5 rounded-full text-xs font-medium border" style={{ borderColor: '#3DD68C', color: '#3DD68C', background: 'var(--bg-card)' }}>
        <span className="relative flex h-2 w-2">
          <span className="animate-ping absolute inline-flex h-full w-full rounded-full opacity-75" style={{ backgroundColor: '#3DD68C' }}></span>
          <span className="relative inline-flex rounded-full h-2 w-2" style={{ backgroundColor: '#3DD68C' }}></span>
        </span>
        <span>Listening…</span>
      </div>
    );
  }

  return (
    <div className="inline-flex items-center gap-2 px-3 py-1.5 rounded-full text-xs border" style={{ borderColor: 'var(--line)', color: 'var(--text-dim)', background: 'var(--bg-card)' }}>
      <span>🎙</span>
      <span>Voice ready</span>
    </div>
  );
}
