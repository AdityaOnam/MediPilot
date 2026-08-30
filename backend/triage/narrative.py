"""
backend/narrative.py

Ollama-powered risk narrative layer for MediPilot.

This module is an INTERPRETABILITY feature, not a predictor.
Ollama (qwen2.5:7b / llama3.2:1b) is a chat LLM — it has no role in the
prediction leaderboard and does not affect any go-live gate.

What it does:
  Given a ScoreObject and the dominant feature contributions, it asks a local
  Ollama model to generate a short, clinician-readable narrative explaining
  WHY a patient received a particular triage band.

Usage:
  from triage.narrative import generate_risk_narrative, is_ollama_available

  if is_ollama_available():
      narrative = generate_risk_narrative(score_dict, patient_context)

Design constraints:
  - The LLM NEVER sees raw model probabilities (these are internal).
  - The LLM NEVER makes or modifies a triage decision.
  - The output is labelled as "AI-generated summary" in the response.
  - If Ollama is unavailable, the function returns None silently — the API
    must degrade gracefully without raising an exception.
"""
from __future__ import annotations

import json
import urllib.request
import urllib.error
from typing import Optional

# Ollama default endpoint
_OLLAMA_URL = "http://localhost:11434/api/generate"

# Preferred model — falls back in order
_MODEL_PREFERENCE = ["qwen2.5:7b", "llama3.2:1b"]

# Hard character limit on LLM output to prevent verbosity
_MAX_CHARS = 300


def is_ollama_available() -> bool:
    """Check if Ollama is running and has at least one usable model."""
    try:
        with urllib.request.urlopen("http://localhost:11434/api/tags", timeout=2) as r:
            data = json.loads(r.read())
            names = [m["name"] for m in data.get("models", [])]
            return any(pref in names for pref in _MODEL_PREFERENCE)
    except Exception:
        return False


def _pick_model() -> Optional[str]:
    """Return the best available model name, or None."""
    try:
        with urllib.request.urlopen("http://localhost:11434/api/tags", timeout=2) as r:
            data = json.loads(r.read())
            names = [m["name"] for m in data.get("models", [])]
            for pref in _MODEL_PREFERENCE:
                if pref in names:
                    return pref
    except Exception:
        pass
    return None


def generate_risk_narrative(
    score_dict: dict,
    dominant_features: Optional[list[str]] = None,
    patient_context: Optional[dict] = None,
    timeout: int = 8,
) -> Optional[str]:
    """
    Generate a short clinician-readable narrative for a triage decision.

    Args:
        score_dict: The ScoreObject.as_dict() output from the risk model.
        dominant_features: List of feature names with the highest contribution
                           (optional — from feature importance, not yet wired).
        patient_context: Optional dict with non-sensitive clinical context
                         (e.g. stratum, chief_complaint, active_red_flags).
        timeout: Seconds to wait for Ollama response. Returns None on timeout.

    Returns:
        A 1-3 sentence narrative string, or None if Ollama is unavailable.

    IMPORTANT:
        - The LLM is given band and reasoning signals, NOT raw probabilities.
        - The output is always prefixed with "[AI summary — not a clinical decision]"
        - This function must never raise — all failures return None.
    """
    model = _pick_model()
    if model is None:
        return None

    band = score_dict.get("band", "unknown").upper()
    score_source = score_dict.get("score_source", "unknown")
    abstained = score_dict.get("abstained", False)
    red_flags = (patient_context or {}).get("active_red_flags", [])
    stratum = (patient_context or {}).get("stratum", "adult")
    chief = (patient_context or {}).get("chief_complaint", "")

    # Build a structured, bounded prompt.
    # Deliberately short — the LLM must summarise, not diagnose.
    prompt_parts = [
        f"You are a clinical decision support assistant summarising a triage system output.",
        f"Triage band assigned: {band}.",
    ]
    if abstained:
        prompt_parts.append("Note: The AI model abstained due to uncertainty; this band is from a safety rule.")
    if red_flags:
        prompt_parts.append(f"Active red flags: {', '.join(red_flags)}.")
    if dominant_features:
        prompt_parts.append(f"Key clinical signals: {', '.join(dominant_features[:5])}.")
    if chief:
        prompt_parts.append(f"Chief complaint: {chief}.")
    prompt_parts.append(f"Patient group: {stratum}.")
    prompt_parts.append(
        f"Write a 1-2 sentence plain-English summary of why this patient received a {band} band. "
        f"Do NOT suggest a diagnosis. Do NOT modify or second-guess the band. "
        f"Be direct and concise. Maximum 60 words."
    )

    prompt = " ".join(prompt_parts)

    try:
        payload = json.dumps({
            "model": model,
            "prompt": prompt,
            "stream": False,
            "options": {"num_predict": 100, "temperature": 0.2},
        }).encode()

        req = urllib.request.Request(
            _OLLAMA_URL,
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=timeout) as r:
            result = json.loads(r.read())
            text = result.get("response", "").strip()
            if len(text) > _MAX_CHARS:
                text = text[:_MAX_CHARS].rsplit(" ", 1)[0] + "..."
            return f"[AI summary — not a clinical decision] {text}"

    except Exception:
        return None
