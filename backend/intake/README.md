# Perception and Structurer (`backend/intake/`)

> **All data in this repository is synthetic.**

This directory governs the intake conversation structure (M03–M09 modules) and the extraction of unstructured patient speech into typed, clinical data.

## The Closed-Loop Contract
The Structurer (LLM) is highly constrained. It is provided with a strict schema and an explicit list of valid option slugs (e.g., `["pain_chest", "pain_abd", "NONE"]`). 
- **The model cannot invent options.** 
- Any hallucinated or out-of-bounds response is forcibly mapped to `NONE`. 
- The model is never asked what a symptom *means* clinically; it is only asked what the patient *said*.

## Tiered Fallbacks
Extraction runs via prioritized tiers:
1. **Tier 0:** Dictionary matching for offline, local fallback.
2. **Tier 1:** String similarity and edit-distance rescue.
3. **Tier 2 (Remote):** LLM constrained extraction.

If cloud access is severed or disabled, Tier 0 and Tier 1 degrade gracefully and keep the kiosk functional.
