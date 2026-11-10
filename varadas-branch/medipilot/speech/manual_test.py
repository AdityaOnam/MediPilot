from whisper_stt import WhisperSTT

print("Loading Whisper...")
stt = WhisperSTT()

print("\nTranscribing f_test1...")

result = stt.transcribe("speech/f_test3.ogg")

print("\n==============================")
print("Language:", result["language"])
print("Text:", result["text"])
print("Reliability:", result["asr_reliability"])
print("==============================")