"""MediPilot speech layer (M05).

Backends:
  - groq_asr.GroqWhisperSTT  — hosted Whisper (the served path, see §16)
  - whisper_stt.WhisperSTT     — local openai-whisper (benchmark/offline path)
  - vad_recorder               — hands-free utterance segmentation (Silero VAD)

Both ASR backends return the same result contract, assembled in asr_common.py.
"""
