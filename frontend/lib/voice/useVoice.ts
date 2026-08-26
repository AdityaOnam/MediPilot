import { useState, useEffect, useRef, useCallback } from 'react';
import { isGlobalMuted } from './audio';

export interface UseVoiceReturn {
  isListening: boolean;
  transcript: string;
  finalTranscript: string;
  startListening: () => void;
  stopListening: () => void;
  micLevel: number;
  speak: (text: string, lang: 'en' | 'hi', onEnd?: () => void) => void;
  isSpeaking: boolean;
  cancelSpeech: () => void;
  supported: boolean;
  error: string | null;
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
  const [isSpeaking, setIsSpeaking] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const recognitionRef = useRef<any>(null);
  const audioCtxRef = useRef<AudioContext | null>(null);
  const analyserRef = useRef<AnalyserNode | null>(null);
  const micStreamRef = useRef<MediaStream | null>(null);
  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const audioChunksRef = useRef<Blob[]>([]);
  const reqFrameRef = useRef<number>(0);

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
        setFinalTranscript(f => (f + ' ' + final).trim());
      }
      setTranscript(interim);
    };

    recognition.onerror = (event: any) => {
      if (event.error === 'no-speech') return; // ignore silence timeouts
      setError(`Speech error: ${event.error}`);
      setIsListening(false);
    };

    recognition.onend = () => {
      setIsListening(false);
    };

    recognitionRef.current = recognition;

    return () => {
      recognition.stop();
    };
  }, [lang, supported]);

  // Handle mic level visualization
  const updateMicLevel = useCallback(() => {
    if (!analyserRef.current) return;
    const array = new Uint8Array(analyserRef.current.frequencyBinCount);
    analyserRef.current.getByteFrequencyData(array);
    let sum = 0;
    for (let i = 0; i < array.length; i++) {
      sum += array[i];
    }
    const avg = sum / array.length;
    setMicLevel(avg / 255); // normalize 0-1
    reqFrameRef.current = requestAnimationFrame(updateMicLevel);
  }, []);

  const startListening = async () => {
    setError(null);
    setTranscript('');
    setFinalTranscript('');
    
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
      
      // Parallel recording for Whisper proxy
      const mr = new MediaRecorder(stream);
      audioChunksRef.current = [];
      mr.ondataavailable = (e) => {
        if (e.data.size > 0) audioChunksRef.current.push(e.data);
      };
      mr.onstop = async () => {
        const audioBlob = new Blob(audioChunksRef.current, { type: 'audio/webm' });
        try {
          const { api } = await import('../api/client');
          const res = await api.transcribe(audioBlob);
          console.log("Whisper proxy transcribed:", res.text);
          // If browser speech failed or isn't supported, use the Whisper output
          if (!supported || error) {
            setFinalTranscript(f => (f + ' ' + res.text).trim());
          }
        } catch (err) {
          console.error("Whisper proxy error:", err);
        }
      };
      mr.start();
      mediaRecorderRef.current = mr;

    } catch (e: any) {
      setError(`Mic access denied: ${e.message}`);
    }
  };

  const stopListening = useCallback(() => {
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
    utterance.rate = 0.95;
    
    // Try to find a good voice
    const voices = window.speechSynthesis.getVoices();
    const targetVoice = voices.find(v => v.lang.includes(utterance.lang)) || voices[0];
    if (targetVoice) {
      utterance.voice = targetVoice;
    }

    utterance.onstart = () => setIsSpeaking(true);
    utterance.onend = () => {
      setIsSpeaking(false);
      onEnd?.();
    };
    utterance.onerror = () => {
      setIsSpeaking(false);
      onEnd?.();
    };

    window.speechSynthesis.speak(utterance);
  }, []);

  const cancelSpeech = useCallback(() => {
    if (typeof window !== 'undefined' && window.speechSynthesis) {
      window.speechSynthesis.cancel();
    }
    setIsSpeaking(false);
  }, []);

  // Listen for synthetic voice events from the Control panel
  useEffect(() => {
    const handleSyntheticSpeech = (e: CustomEvent) => {
      if (e.detail.finalTranscript) {
        setFinalTranscript(f => (f + ' ' + e.detail.finalTranscript).trim());
      }
    };
    window.addEventListener('synthetic-speech' as any, handleSyntheticSpeech);
    return () => window.removeEventListener('synthetic-speech' as any, handleSyntheticSpeech);
  }, []);

  return {
    isListening,
    transcript,
    finalTranscript,
    startListening,
    stopListening,
    micLevel,
    speak,
    isSpeaking,
    cancelSpeech,
    supported,
    error
  };
}
