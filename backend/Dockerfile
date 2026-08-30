# MediPilot orchestrator — Cloud Run image.
#
# The orchestrator keeps world state (encounters, audit log, tick loop) in a
# single in-process `World()` instance (see triage/orchestrator/app.py and
# README.md's "Strictly Single-Worker" note). Do not raise uvicorn's
# --workers above 1, and pin the Cloud Run service to a single instance
# (min-instances=1 max-instances=1) — otherwise Cloud Run's autoscaler will
# spin up independent processes with independent, diverging world state.
FROM python:3.11-slim

WORKDIR /app

# --- system deps -------------------------------------------------------
# ffmpeg: decodes webm/opus uploads in the speech pipeline (see
# speech/asr_common.py). Not required for the deterministic/text-only paths
# but cheap to include so /v1/speech/transcribe works when GROQ_API_KEY is set.
RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg \
    && rm -rf /var/lib/apt/lists/*

# --- python deps --------------------------------------------------------
# Only the serving requirements — NOT requirements-speech-local.txt (torch +
# faster-whisper are multi-GB and only needed for the local ASR fallback,
# which speech_intake.py already skips gracefully via ImportError when
# absent, falling through to the hosted Groq backend) and NOT
# requirements-experimental.txt (training/eval-only).
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# --- app code ------------------------------------------------------------
COPY . .

ENV PYTHONUNBUFFERED=1
EXPOSE 8080

# Cloud Run injects $PORT (default 8080). Shell form so it expands.
CMD exec uvicorn triage.orchestrator.app:app --host 0.0.0.0 --port ${PORT:-8080} --workers 1
