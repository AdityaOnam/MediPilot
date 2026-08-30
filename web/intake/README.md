# The Talking Kiosk (`web/intake/`)

> **All data in this repository is synthetic.**

This module houses the interactive, patient-facing triage kiosk. It is explicitly separated from the nurse surfaces because the patient kiosk must function in severe offline environments.

## Resilience Architecture
1. **ASR (Speech-to-Text):** Connects to Groq `whisper-large-v3-turbo` for rapid transcription. If network latency spikes, it falls back seamlessly to the `webkitSpeechRecognition` native browser layer.
2. **Offline Mode:** Using the `MEDIPILOT_INTAKE_OFFLINE=1` environment flag, the kiosk can be rehearsed using pure offline matching without ever hitting cloud APIs.
3. **Mascot Degradation:** Uses `useCan3D` hook to check the client hardware profile. If `prefers-reduced-motion` is active or if hardware concurrency is too low, the interactive 3D WebGL mascot gracefully degrades to a 2D image cutout, guaranteeing UI responsiveness on low-end hospital tablets.
