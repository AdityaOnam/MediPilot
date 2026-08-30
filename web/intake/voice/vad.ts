/**
 * Voice activity detection over an AnalyserNode.
 *
 * Two jobs, both of which the old implementation got wrong by using a
 * hardcoded decibel threshold:
 *
 *   1. CALIBRATE the noise floor from the room itself, during the 2 s
 *      arming window, every question. A ceiling fan switching on halfway
 *      through an intake must not break the rest of the conversation.
 *   2. Report onset and silence against that floor — never against a
 *      constant that happened to work at a developer's desk.
 *
 * Nothing here starts a timer. useSpeech.ts owns the state machine; this
 * module only answers "how loud is it right now, and what counts as loud
 * in this room".
 */

/** Below this the gate is meaningless — a silent room's 80th percentile
 *  is near zero and `floor * MULTIPLIER` would trigger on nothing. */
const MIN_ABSOLUTE_GATE = 0.012;

/** How far above the measured floor a sample must sit to count as speech.
 *  2.2 is forgiving enough for a soft-spoken patient in a busy hall
 *  without opening on room tone. */
const FLOOR_MULTIPLIER = 2.2;

export interface Vad {
  /** Current RMS, 0..1. Safe to call before attach() — returns 0. */
  level(): number;
  /** Samples the room for `ms` and returns the speech gate to use for
   *  this question. Runs during ARMING, so the TTS has already finished
   *  and what it measures is genuinely ambient. */
  calibrate(ms: number): Promise<number>;
  /** Stops metering and releases the AudioContext. The MediaStream is
   *  owned by the caller and is NOT stopped here. */
  detach(): void;
}

export async function createVad(stream: MediaStream): Promise<Vad> {
  const Ctor: typeof AudioContext =
    window.AudioContext ?? (window as unknown as { webkitAudioContext: typeof AudioContext }).webkitAudioContext;
  const ctx = new Ctor();

  // Autoplay policy can leave a freshly created context suspended until a
  // gesture. By the time intake reaches a question the patient has tapped
  // several buttons, so this resolves immediately in practice.
  if (ctx.state === 'suspended') {
    await ctx.resume().catch(() => undefined);
  }

  const source = ctx.createMediaStreamSource(stream);
  const analyser = ctx.createAnalyser();
  analyser.fftSize = 1024;
  analyser.smoothingTimeConstant = 0.2;
  source.connect(analyser);

  const buf = new Uint8Array(analyser.fftSize);

  function level(): number {
    analyser.getByteTimeDomainData(buf);
    let sum = 0;
    for (let i = 0; i < buf.length; i++) {
      const v = (buf[i] - 128) / 128;
      sum += v * v;
    }
    return Math.sqrt(sum / buf.length);
  }

  async function calibrate(ms: number): Promise<number> {
    const samples: number[] = [];
    const started = Date.now();
    return new Promise((resolve) => {
      const id = setInterval(() => {
        samples.push(level());
        if (Date.now() - started >= ms) {
          clearInterval(id);
          resolve(gateFrom(samples));
        }
      }, 25);
    });
  }

  function detach() {
    try {
      source.disconnect();
      analyser.disconnect();
    } catch {
      // already torn down
    }
    void ctx.close().catch(() => undefined);
  }

  return { level, calibrate, detach };
}

/**
 * 80th percentile rather than the mean: a couple of loud transients (a
 * door, a cough) during calibration would drag a mean upward and leave
 * the gate too high to hear the patient at all. The percentile ignores
 * them.
 */
export function gateFrom(samples: number[]): number {
  if (samples.length === 0) return MIN_ABSOLUTE_GATE;
  const sorted = [...samples].sort((a, b) => a - b);
  const idx = Math.min(sorted.length - 1, Math.floor(sorted.length * 0.8));
  const floor = sorted[idx];
  return Math.max(MIN_ABSOLUTE_GATE, floor * FLOOR_MULTIPLIER);
}
