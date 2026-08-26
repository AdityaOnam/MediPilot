"""
Manual, real-microphone check of speech/vad_recorder.py.

NOT a pytest test -- it is never collected or run automatically, and it
requires a real microphone and the `sounddevice`/PortAudio stack to be
working on your machine. Run it by hand to confirm hands-free speech-end
detection actually works end to end (mic -> VAD -> existing WhisperSTT).

Usage:
    python -m speech.mic_check

Speak a short sentence, then go quiet. Recording should stop on its own
about 1-1.5 seconds after you stop talking (or after ~25s regardless).
"""

from speech.vad_recorder import MicrophoneVADListener


def main() -> int:
    print("Loading Whisper + Silero VAD (first run downloads/loads the models)...")
    listener = MicrophoneVADListener()

    print("\nListening... speak whenever you're ready (no button to press).")
    print("Recording starts automatically when you speak, and stops ~1-1.5s after you go quiet.\n")

    result = listener.start_listening()

    print("=" * 60)
    print(f"Ended because: {result.end_reason}")
    print(f"Captured duration: {result.duration_s:.2f}s")
    print(f"Detected language: {result.language}")
    print(f"Transcript: {result.text!r}")
    print(f"ASR reliability: {result.asr_reliability}")
    print("=" * 60)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
