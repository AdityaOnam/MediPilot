# MediPilot — Speech & LLM Layer
### Contribution by **Varada** · Branch: `feat/varada/speech-llm`

---

This module is responsible for the natural language intake and triage structuring in MediPilot. It converts live audio into text using Whisper and parses the conversation using large language models to extract structured patient records.

## Directory Structure

- `speech/`: Audio processing, Voice Activity Detection (VAD) via Silero, and STT via Whisper.
- `intake/`: LLM-based state machines and question trees for the clinical interview.
- `tests/`: Centralized test suite and test audio samples.

## How it works

1. **Microphone Input** is monitored by `vad_recorder.py`.
2. Speech chunks are processed by `whisper_stt.py`.
3. Transcriptions are routed through `pipeline.py` which manages the conversation state.
4. `llm_structurer.py` extracts symptoms and vital signs into JSON payloads.
5. Payloads are sent to the ML Risk Engine for final scoring.

## Running Tests
Navigate to the root directory and run pytest:
```bash
pytest speech_layer/tests/ -v
```
