// lib/voice/audio.ts

let audioCtx: AudioContext | null = null;
let globalMuted = false;

export function setGlobalMute(muted: boolean) {
  globalMuted = muted;
}

export function isGlobalMuted() {
  return globalMuted;
}

function getContext() {
  if (typeof window === 'undefined') return null;
  if (!audioCtx) {
    audioCtx = new (window.AudioContext || (window as any).webkitAudioContext)();
  }
  if (audioCtx.state === 'suspended') {
    audioCtx.resume();
  }
  return audioCtx;
}

/** Rising two-note interval (C5 -> E5), 200ms each, gain 0.15 */
export function playEscalationChime() {
  if (globalMuted) return;
  const ctx = getContext();
  if (!ctx) return;

  const t = ctx.currentTime;
  
  // Note 1: C5 (523.25 Hz)
  const osc1 = ctx.createOscillator();
  const gain1 = ctx.createGain();
  osc1.type = 'sine';
  osc1.frequency.setValueAtTime(523.25, t);
  gain1.gain.setValueAtTime(0, t);
  gain1.gain.linearRampToValueAtTime(0.15, t + 0.05);
  gain1.gain.exponentialRampToValueAtTime(0.01, t + 0.2);
  osc1.connect(gain1);
  gain1.connect(ctx.destination);
  osc1.start(t);
  osc1.stop(t + 0.2);

  // Note 2: E5 (659.25 Hz)
  const osc2 = ctx.createOscillator();
  const gain2 = ctx.createGain();
  osc2.type = 'sine';
  osc2.frequency.setValueAtTime(659.25, t + 0.2);
  gain2.gain.setValueAtTime(0, t + 0.2);
  gain2.gain.linearRampToValueAtTime(0.15, t + 0.25);
  gain2.gain.exponentialRampToValueAtTime(0.01, t + 0.4);
  osc2.connect(gain2);
  gain2.connect(ctx.destination);
  osc2.start(t + 0.2);
  osc2.stop(t + 0.4);
}

/** Single short tick, noise burst 80ms, gain 0.1 */
export function playCaptureConfirm() {
  if (globalMuted) return;
  const ctx = getContext();
  if (!ctx) return;

  const bufferSize = ctx.sampleRate * 0.08; // 80ms
  const buffer = ctx.createBuffer(1, bufferSize, ctx.sampleRate);
  const data = buffer.getChannelData(0);
  for (let i = 0; i < bufferSize; i++) {
    data[i] = Math.random() * 2 - 1;
  }

  const noise = ctx.createBufferSource();
  noise.buffer = buffer;
  
  // Bandpass filter to make it a "tick"
  const filter = ctx.createBiquadFilter();
  filter.type = 'bandpass';
  filter.frequency.value = 4000;
  
  const gain = ctx.createGain();
  gain.gain.setValueAtTime(0.1, ctx.currentTime);
  gain.gain.exponentialRampToValueAtTime(0.01, ctx.currentTime + 0.08);

  noise.connect(filter);
  filter.connect(gain);
  gain.connect(ctx.destination);
  
  noise.start(ctx.currentTime);
}

/** Low settle, C3 (130.81 Hz), 300ms exp decay, gain 0.1 */
export function playCommitSettle() {
  if (globalMuted) return;
  const ctx = getContext();
  if (!ctx) return;

  const t = ctx.currentTime;
  const osc = ctx.createOscillator();
  const gain = ctx.createGain();
  
  osc.type = 'sine';
  osc.frequency.setValueAtTime(130.81, t);
  
  gain.gain.setValueAtTime(0, t);
  gain.gain.linearRampToValueAtTime(0.1, t + 0.05);
  gain.gain.exponentialRampToValueAtTime(0.01, t + 0.3);
  
  osc.connect(gain);
  gain.connect(ctx.destination);
  
  osc.start(t);
  osc.stop(t + 0.3);
}
