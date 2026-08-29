import { useState, useEffect, useRef, useCallback } from 'react';
import { isGlobalMuted } from './audio';

export interface UseVoiceReturn {
  isListening: boolean;
  /** Live interim text from the browser recogniser. Display-only feedback
   *  while the patient is speaking — never submitted. */
  transcript: string;
  /** The transcript intake actually consumes. Whisper's output once it
   *  returns; the browser recogniser's text only until then. */
  finalTranscript: string;
  /** Which engine produced `finalTranscript` right now. */
  transcriptSource: 'browser' | 'whisper' | null;
  /** ASR-observable metadata from the backend for the last utterance.
   *  Descriptive only — carries no clinical meaning. */
  asrMeta: AsrMeta | null;
  /** True while the recorded utterance is being transcribed by Whisper. */
  isTranscribing: boolean;
  startListening: () => void;
  stopListening: () => void;
  /** Clear the consumed transcript WITHOUT stopping the microphone, so the
   *  next question starts clean while listening stays on. */
  resetTranscript: () => void;
  micLevel: number;
  speak: (text: string, lang: 'en' | 'hi', onEnd?: () => void) => void;
  /** 0..1. The kiosk exposes this as a slider next to the mute button so
   *  a patient can raise it in a noisy waiting area or lower it to be
   *  polite. Persists across questions and across page reloads. */
  volume: number;
  setVolume: (v: number) => void;
  isSpeaking: boolean;
  cancelSpeech: () => void;
  supported: boolean;
  error: string | null;
}

export interface AsrMeta {
  language: string | null;
  codeMixed: boolean;
  backend: string;
  reliability: {
    no_speech: boolean;
    low_confidence: boolean;
    possible_hallucination: boolean;
    unsupported_language: boolean;
  };
}

// Add type def for WebkitSpeechRecognition
declare global {
  interface Window {
    SpeechRecognition: any;
    webkitSpeechRecognition: any;
  }
}

export function useVoice(lang: 'en' | 'hi'): UseVoiceReturn {
  const [isListening, setIsListening] = useState(false);
  const [transcript, setTranscript] = useState('');
  const [finalTranscript, setFinalTranscript] = useState('');
  const [micLevel, setMicLevel] = useState(0);
  const [transcriptSource, setTranscriptSource] = useState<'browser' | 'whisper' | null>(null);
  const [asrMeta, setAsrMeta] = useState<AsrMeta | null>(null);
  const [isTranscribing, setIsTranscribing] = useState(false);
  const [isSpeaking, setIsSpeaking] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [volume, setVolumeState] = useState<number>(() => {
    if (typeof window === 'undefined') return 1;
    const stored = window.localStorage.getItem('medipilot.voiceVolume');
    const parsed = stored ? parseFloat(stored) : 1;
    return isNaN(parsed) ? 1 : Math.max(0, Math.min(1, parsed));
  });
  const volumeRef = useRef(volume);
  const setVolume = useCallback((v: number) => {
    const clamped = Math.max(0, Math.min(1, v));
    volumeRef.current = clamped;
    setVolumeState(clamped);
    if (typeof window !== 'undefined') {
      window.localStorage.setItem('medipilot.voiceVolume', String(clamped));
    }
  }, []);

  const recognitionRef = useRef<any>(null);
  const audioCtxRef = useRef<AudioContext | null>(null);
  const analyserRef = useRef<AnalyserNode | null>(null);
  const micStreamRef = useRef<MediaStream | null>(null);
  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const audioChunksRef = useRef<Blob[]>([]);
  const reqFrameRef = useRef<number>(0);
  // True only when the PATIENT pressed stop. The browser recogniser ends
  // its own session constantly (silence timeouts, end of utterance); those
  // must not be mistaken for "the patient is done talking" or the kiosk
  // goes deaf mid-conversation and the patient has to keep re-pressing the
  // mic. Everything auto-restarts unless this is set.
  const userStoppedRef = useRef(true);
  // Set while cutting one utterance out of the continuous recording, so
  // the recorder's onstop handler knows to restart rather than tear down.
  const segmentingRef = useRef(false);
  // Silence-based auto-cut. A run of quiet after real audio ends the
  // segment the way "you stopped talking" would end it, so Whisper gets a
  // bounded clip and the textarea sees the authoritative transcript.
  //
  // Three guards keep this from firing constantly:
  //   * VOICED_THRESHOLD is above typical mic-ambient noise (~0.02-0.05
  //     on a laptop mic). Below that, background hiss keeps resetting
  //     the silence timer and cuts never happen, or (worse) an
  //     intermittently-crossed threshold produces many tiny segments.
  //   * MIN_VOICED_MS requires SUSTAINED voice, not a single peak: a
  //     cough or a door slam should not count as "the patient spoke".
  //   * MIN_SEGMENT_MS blocks cuts in the first ~1.5 s of a fresh
  //     segment, so restarting the recorder immediately after a cut
  //     cannot cascade into a chain of empty-segment cuts.
  const lastVoicedAtRef = useRef<number>(0);
  const heardAudioRef = useRef(false);
  const voicedSinceRef = useRef<number>(0);
  const segmentStartRef = useRef<number>(0);
  const silenceTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const SILENCE_MS = 6500;
  const VOICED_THRESHOLD = 0.08;
  const MIN_VOICED_MS = 400;
  const MIN_SEGMENT_MS = 1500;
  // When TTS is speaking the question aloud, mute the transcription
  // pipeline: same speaker feeds the same room the mic is in, so without
  // this the kiosk transcribes its own voice and treats "What is bothering
  // you today?" as the patient's answer. We drop recognizer results,
  // discard recorder chunks, and freeze the silence timer, then restart
  // clean when TTS ends. Cheaper and more robust than acoustic echo
  // cancellation, and safe because a real patient can start speaking the
  // instant the prompt finishes -- which is when we unmute anyway.
  const pausedForTtsRef = useRef(false);

  // Initialize Speech Recognition
  const supported = typeof window !== 'undefined' && !!(window.SpeechRecognition || window.webkitSpeechRecognition);

  useEffect(() => {
    if (!supported) return;

    const SpeechRec = window.SpeechRecognition || window.webkitSpeechRecognition;
    const recognition = new SpeechRec();
    recognition.continuous = true;
    recognition.interimResults = true;
    recognition.lang = lang === 'hi' ? 'hi-IN' : 'en-IN';

    recognition.onresult = (event: any) => {
      // Drop everything captured while the kiosk itself was talking; that
      // audio is TTS bleeding into the mic, not the patient.
      if (pausedForTtsRef.current) return;
      let interim = '';
      let final = '';
      for (let i = event.resultIndex; i < event.results.length; ++i) {
        if (event.results[i].isFinal) {
          final += event.results[i][0].transcript;
        } else {
          interim += event.results[i][0].transcript;
        }
      }
      if (final) {
        // Provisional only. The browser recogniser is en-IN/hi-IN and cannot
        // handle the code-mixed Hinglish the intake flow expects (§01 D12),
        // so this holds the field only until Whisper's result lands and
        // replaces it below.
        setFinalTranscript(f => (f + ' ' + final).trim());
        setTranscriptSource(s => (s === 'whisper' ? s : 'browser'));
        // The patient finished an utterance. Cut the continuous recording
        // here so Whisper gets one complete utterance to transcribe --
        // Whisper is the authoritative transcript (it handles Hinglish;
        // the browser recogniser does not), and it needs a bounded clip,
        // not an open-ended stream.
        cutSegment();
      }
      setTranscript(interim);
    };

    recognition.onerror = (event: any) => {
      if (event.error === 'no-speech') return; // ignore silence timeouts
      // 'aborted' fires as part of our own restart cycle; not a real fault.
      if (event.error === 'aborted') return;
      setError(`Speech error: ${event.error}`);
      if (event.error === 'not-allowed' || event.error === 'service-not-allowed') {
        userStoppedRef.current = true; // permission denied — do not fight it
        setIsListening(false);
      }
    };

    recognition.onend = () => {
      // The recogniser stops itself constantly. Keep listening unless the
      // patient actually asked us to stop (task: mic stays on until
      // explicitly turned off).
      if (userStoppedRef.current) {
        setIsListening(false);
        return;
      }
      try {
        recognition.start();
      } catch {
        // Already restarting; the next onend will try again.
      }
    };

    recognitionRef.current = recognition;

    return () => {
      recognition.stop();
    };
  }, [lang, supported]);

  /**
   * End the current audio segment so it can be sent to Whisper, then
   * immediately begin a new one on the same live stream. This is what lets
   * the microphone stay open across many utterances while Whisper still
   * receives discrete, bounded clips.
   */
  const cutSegment = useCallback(() => {
    const mr = mediaRecorderRef.current;
    if (!mr || mr.state === 'inactive') return;
    segmentingRef.current = true;
    try {
      mr.stop(); // fires onstop -> transcribes -> restarts (see startListening)
    } catch {
      segmentingRef.current = false;
    }
  }, []);

  // Mic-level polling + silence-based auto-cut. Runs continuously while
  // listening; only reads from state refs so the callback is stable and
  // doesn't restart on every re-render.
  const updateMicLevel = useCallback(() => {
    if (!analyserRef.current) return;
    const array = new Uint8Array(analyserRef.current.frequencyBinCount);
    analyserRef.current.getByteFrequencyData(array);
    let sum = 0;
    for (let i = 0; i < array.length; i++) sum += array[i];
    const avg = sum / array.length;
    const norm = avg / 255;
    setMicLevel(norm);

    // Silence-based auto-cut. See the comments on the constants above.
    // Frozen while TTS speaks so the prompt itself doesn't count as
    // audio and reset the silence timer.
    if (!userStoppedRef.current && !pausedForTtsRef.current) {
      const now = performance.now();
      if (norm > VOICED_THRESHOLD) {
        lastVoicedAtRef.current = now;
        if (!voicedSinceRef.current) voicedSinceRef.current = now;
        // Only count as "the patient really spoke" once we've seen sustained
        // audio for MIN_VOICED_MS. A single peak doesn't flip the flag.
        if (!heardAudioRef.current && now - voicedSinceRef.current >= MIN_VOICED_MS) {
          heardAudioRef.current = true;
        }
      } else {
        // Any dip below threshold restarts the sustained-voice window.
        voicedSinceRef.current = 0;
        if (
          heardAudioRef.current
          && now - lastVoicedAtRef.current > SILENCE_MS
          && now - segmentStartRef.current > MIN_SEGMENT_MS
          && !segmentingRef.current
        ) {
          heardAudioRef.current = false;
          cutSegment();
        }
      }
    }
    reqFrameRef.current = requestAnimationFrame(updateMicLevel);
  }, []);

  const startListening = async () => {
    setError(null);
    setTranscript('');
    setFinalTranscript('');
    setTranscriptSource(null);
    setAsrMeta(null);
    userStoppedRef.current = false; // stays listening until stopListening()
    heardAudioRef.current = false;
    lastVoicedAtRef.current = performance.now();

    if (recognitionRef.current) {
      try {
        recognitionRef.current.start();
        setIsListening(true);
      } catch (e: any) {
        // Handle case where it's already started
        if (e.name !== 'InvalidStateError') {
          setError(e.message);
        } else {
          setIsListening(true);
        }
      }
    }

    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      micStreamRef.current = stream;
      if (!audioCtxRef.current) {
        audioCtxRef.current = new (window.AudioContext || (window as any).webkitAudioContext)();
      }
      if (audioCtxRef.current.state === 'suspended') {
        audioCtxRef.current.resume();
      }
      analyserRef.current = audioCtxRef.current.createAnalyser();
      analyserRef.current.fftSize = 256;
      const source = audioCtxRef.current.createMediaStreamSource(stream);
      source.connect(analyserRef.current);
      updateMicLevel();
      
      // Parallel recording for Whisper proxy. Recreated per segment so the
      // mic can stay open across many utterances (see cutSegment).
      const startRecorder = () => {
        const mr = new MediaRecorder(stream);
        audioChunksRef.current = [];
        mr.ondataavailable = (e) => {
          // Skip any data captured while TTS was playing -- that IS the
          // question audio, not the patient.
          if (pausedForTtsRef.current) return;
          if (e.data.size > 0) audioChunksRef.current.push(e.data);
        };
        mr.onstop = () => {
          const chunks = audioChunksRef.current;
          audioChunksRef.current = [];
          const wasSegmenting = segmentingRef.current;
          segmentingRef.current = false;
          // Restart immediately so no speech is lost in the gap between
          // one utterance being sent off and the next one beginning.
          if (wasSegmenting && !userStoppedRef.current) {
            try { startRecorder(); } catch { /* stream ended */ }
          }
          if (chunks.length > 0) void transcribeSegment(chunks);
        };
        mr.start();
        mediaRecorderRef.current = mr;
        // Reset the audio-detection state so the auto-cut guards apply
        // per-segment, not once-per-listening-session.
        segmentStartRef.current = performance.now();
        heardAudioRef.current = false;
        voicedSinceRef.current = 0;
        lastVoicedAtRef.current = performance.now();
      };

      const transcribeSegment = async (chunks: Blob[]) => {
        const audioBlob = new Blob(chunks, { type: 'audio/webm' });
        setIsTranscribing(true);
        try {
          const { api } = await import('../api/client');
          const res = await api.transcribe(audioBlob);

          // Whisper is authoritative, not a fallback. It saw the whole
          // utterance at once, transcribes in the language spoken rather
          // than a language we had to pick in advance, and is the only path
          // that handles Hinglish — which is the default this deployment
          // expects, not an edge case. The browser recogniser exists for
          // live interim feedback while the patient talks.
          //
          // The one case where it does not win: an empty result. A silent
          // or gated recording must not wipe text the patient did produce.
          if (res.text) {
            setFinalTranscript(res.text);
            setTranscriptSource('whisper');
          }
          setAsrMeta({
            language: res.language,
            codeMixed: res.codeMixed,
            backend: res.backend,
            reliability: res.asrReliability,
          });
        } catch (err) {
          // The orchestrator returns 503 with a reason when ASR is
          // unavailable. Keep whatever the browser recogniser heard and say
          // the accurate path failed — never substitute placeholder text.
          console.error('Whisper transcription failed:', err);
          setError(
            'Voice transcription is unavailable. Your words were captured by the ' +
            'browser instead, which is less accurate — please check the readback, ' +
            'or type your answer.'
          );
        } finally {
          setIsTranscribing(false);
        }
      };

      startRecorder();

    } catch (e: any) {
      setError(`Mic access denied: ${e.message}`);
    }
  };

  const stopListening = useCallback(() => {
    // The ONLY place this is set. Everything else (silence timeouts, end of
    // an utterance, an auto-advance to the next question) keeps listening.
    userStoppedRef.current = true;
    segmentingRef.current = false;
    heardAudioRef.current = false;
    if (silenceTimerRef.current) {
      clearTimeout(silenceTimerRef.current);
      silenceTimerRef.current = null;
    }
    if (recognitionRef.current) {
      recognitionRef.current.stop();
    }
    if (mediaRecorderRef.current && mediaRecorderRef.current.state !== 'inactive') {
      mediaRecorderRef.current.stop();
    }
    setIsListening(false);
    if (reqFrameRef.current) {
      cancelAnimationFrame(reqFrameRef.current);
    }
    setMicLevel(0);
    if (micStreamRef.current) {
      micStreamRef.current.getTracks().forEach(t => t.stop());
      micStreamRef.current = null;
    }
  }, []);

  /** Clear consumed text without touching the microphone — used when the
   *  tree advances to the next question while listening stays on. */
  const resetTranscript = useCallback(() => {
    setTranscript('');
    setFinalTranscript('');
    setTranscriptSource(null);
  }, []);

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      stopListening();
    };
  }, [stopListening]);

  // TTS
  const speak = useCallback((text: string, langSetting: 'en' | 'hi', onEnd?: () => void) => {
    if (isGlobalMuted()) {
      onEnd?.();
      return;
    }
    if (typeof window === 'undefined' || !window.speechSynthesis) {
      onEnd?.();
      return;
    }

    // Vocabulary guard (DESIGN_SYSTEM §7)
    const lower = text.toLowerCase();
    if (
      lower.includes('red') || 
      lower.includes('yellow') || 
      lower.includes('green') ||
      lower.includes('you have') ||
      lower.includes('you might have')
    ) {
      if (process.env.NODE_ENV !== 'production') {
        throw new Error(`TTS Vocabulary violation: MediPilot cannot speak acuity levels or diagnoses. Text: "${text}"`);
      }
    }

    window.speechSynthesis.cancel(); // stop any current speech
    
    const utterance = new SpeechSynthesisUtterance(text);
    utterance.lang = langSetting === 'hi' ? 'hi-IN' : 'en-IN';
    // Waiting rooms are noisy and listeners may be elderly or standing back
    // from the kiosk. The default is max volume; a slider in the header
    // (see resetTranscript / setVolume) lets a patient turn it down when
    // that is too loud. Rate is slightly slower than the browser default
    // so the question stays intelligible over ambient noise.
    utterance.volume = volumeRef.current;
    utterance.rate = 0.9;
    
    // Try to find a good voice
    const voices = window.speechSynthesis.getVoices();
    const targetVoice = voices.find(v => v.lang.includes(utterance.lang)) || voices[0];
    if (targetVoice) {
      utterance.voice = targetVoice;
    }

    utterance.onstart = () => {
      pausedForTtsRef.current = true;
      // Drop anything currently buffered -- if we already captured a
      // fraction of a second of TTS it should not reach Whisper.
      audioChunksRef.current = [];
      setTranscript('');
      setIsSpeaking(true);
    };
    const resumeAfterTts = () => {
      pausedForTtsRef.current = false;
      // Reset silence detection so the countdown doesn't fire the instant
      // we unmute (it thinks the room has been quiet the whole time TTS
      // was speaking, and the silence guard was frozen -- but the timer
      // reference is now stale). A fresh segment gets a fresh clock.
      heardAudioRef.current = false;
      voicedSinceRef.current = 0;
      lastVoicedAtRef.current = performance.now();
      segmentStartRef.current = performance.now();
      audioChunksRef.current = [];
    };
    utterance.onend = () => {
      resumeAfterTts();
      setIsSpeaking(false);
      onEnd?.();
    };
    utterance.onerror = () => {
      resumeAfterTts();
      setIsSpeaking(false);
      onEnd?.();
    };

    window.speechSynthesis.speak(utterance);
  }, []);

  const cancelSpeech = useCallback(() => {
    if (typeof window !== 'undefined' && window.speechSynthesis) {
      window.speechSynthesis.cancel();
    }
    // Cancel does not fire onend on every browser, so unmute here too.
    // Also reset the silence-guard state, same as after a normal end.
    pausedForTtsRef.current = false;
    heardAudioRef.current = false;
    voicedSinceRef.current = 0;
    lastVoicedAtRef.current = performance.now();
    segmentStartRef.current = performance.now();
    audioChunksRef.current = [];
    setIsSpeaking(false);
  }, []);

  // Listen for synthetic voice events from the Control panel
  useEffect(() => {
    const handleSyntheticSpeech = (e: CustomEvent) => {
      if (e.detail.finalTranscript) {
        setFinalTranscript(f => (f + ' ' + e.detail.finalTranscript).trim());
        setTranscriptSource('browser');
      }
    };
    window.addEventListener('synthetic-speech' as any, handleSyntheticSpeech);
    return () => window.removeEventListener('synthetic-speech' as any, handleSyntheticSpeech);
  }, []);

  return {
    isListening,
    transcript,
    finalTranscript,
    transcriptSource,
    asrMeta,
    isTranscribing,
    startListening,
    stopListening,
    resetTranscript,
    micLevel,
    speak,
    volume,
    setVolume,
    isSpeaking,
    cancelSpeech,
    supported,
    error
  };
}
