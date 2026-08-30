"""
Manual, standalone check of the real Groq API (M06's GroqLLMStructurer).

This is NOT a pytest test — it is never collected or run automatically, so
it never requires GROQ_API_KEY in CI or in intake/test_pipeline.py. Run it
by hand when you want to confirm the live Groq integration actually works.

Usage:
    GROQ_API_KEY=your-key python -m intake.groq_live_check
    GROQ_API_KEY=your-key python -m intake.groq_live_check "mujhe chest mein pain ho raha hai"
"""

import json
import os
import sys

from intake.llm_structurer import GroqLLMStructurer, StructurerOutputError

DEFAULT_TRANSCRIPT = "I have had chest pain and sweating since about 30 minutes ago."


def main() -> int:
    if not os.environ.get("GROQ_API_KEY"):
        print("GROQ_API_KEY is not set. Set it in your shell before running this script.")
        print('Example: GROQ_API_KEY=your-key python -m intake.groq_live_check')
        return 1

    transcript = " ".join(sys.argv[1:]) or DEFAULT_TRANSCRIPT
    print(f"Transcript: {transcript!r}")
    print(f"Model: {GroqLLMStructurer.DEFAULT_MODEL}")

    structurer = GroqLLMStructurer()
    try:
        result = structurer.structure(transcript)
    except StructurerOutputError as exc:
        print(f"FAILED: {exc}")
        return 1

    print(json.dumps(
        {
            "chief_complaint": result.chief_complaint,
            "onset_minutes": result.onset_minutes,
            "self_reported_severity": result.self_reported_severity,
            "symptoms": result.symptoms,
            "medications": result.medications,
            "pregnancy_status": result.pregnancy_status,
            "relevant_history": result.relevant_history,
            "extraction_status": result.extraction_status,
            "unrecognized_terms": result.unrecognized_terms,
        },
        indent=2,
    ))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
