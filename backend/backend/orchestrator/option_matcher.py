"""
Server-side option matcher for the tree UI.

The frontend already runs a fast Jaccard token-overlap matcher
(lib/intake/optionMatcher.ts). This module is what runs when THAT match
falls below its confidence threshold: it asks the hosted LLM (Groq)
"here is the question, here are the choices, here is what the patient
actually said -- pick the closest choice, or say NONE."

Kept deliberately narrow: the model is not asked to interpret meaning
or make a clinical judgement. Its only job is to pick one of the given
option slugs verbatim, or to return "NONE" so the caller shows the
patient a "please pick one below" hint. The output vocabulary is closed
by construction -- anything the model returns that is not one of the
listed slug values reads as NONE, so the model cannot invent options.

Never called from the client on every keystroke: only when the local
matcher has already given up. That keeps the cost and latency of a
network call on the exception path, not the happy path.
"""

from __future__ import annotations

import json
import os
from typing import Optional

# The prompt is composed so the model sees exactly what the patient sees.
_SYSTEM = (
    "You are a picker, not a clinician. You are given a question, a list "
    "of allowed answer choices, and what the patient said. Choose the "
    "SINGLE choice whose meaning best matches what the patient said. If "
    "no choice is a reasonable match, answer NONE. Reply with only the "
    "choice's `value` field, nothing else."
)


def _build_user_prompt(question_prompt: str, patient_text: str, options: list) -> str:
    lines = [
        f"Question: {question_prompt}",
        "Choices (value → label):",
    ]
    for o in options:
        label = o.get("label", {})
        label_str = label.get("en") or label.get("hi") or o.get("value", "")
        lines.append(f"  {o['value']} → {label_str}")
    lines.append(f"Patient said: {patient_text!r}")
    lines.append("Reply with one value from the list, or NONE.")
    return "\n".join(lines)


def match(
    question_prompt: str,
    patient_text: str,
    options: list,
    model: Optional[str] = None,
) -> dict:
    """
    Return {matched: <value>|None, source: 'groq'|'unavailable', reason: str}.

    Cheap to call with a bad `patient_text`: on any transport / auth /
    parse error, `matched` is None and `source` is "unavailable" -- the
    caller shows the fallback hint and stays on the same question. No
    exception surfaces.
    """
    text = (patient_text or "").strip()
    if not text or not options:
        return {"matched": None, "source": "unavailable", "reason": "empty_input"}

    api_key = os.environ.get("GROQ_API_KEY")
    if not api_key:
        return {"matched": None, "source": "unavailable", "reason": "no_api_key"}

    try:
        import groq
    except ImportError:
        return {"matched": None, "source": "unavailable", "reason": "groq_package_missing"}

    valid_values = {str(o["value"]) for o in options}

    try:
        client = groq.Groq(api_key=api_key)
        response = client.chat.completions.create(
            model=model or os.environ.get("MEDIPILOT_MATCHER_MODEL", "openai/gpt-oss-20b"),
            messages=[
                {"role": "system", "content": _SYSTEM},
                {"role": "user", "content": _build_user_prompt(question_prompt, text, options)},
            ],
            temperature=0,
            max_tokens=32,
        )
        raw = (response.choices[0].message.content or "").strip()
    except Exception as exc:  # noqa: BLE001 -- network/auth/rate-limit shouldn't crash intake
        return {"matched": None, "source": "unavailable", "reason": f"api_error: {exc}"}

    # Closed-vocabulary decode. The model was told to reply with a value,
    # but real replies often include punctuation, quotes, or a full label
    # word. Match against valid_values by exact word first, then substring.
    lowered = raw.lower().strip(".,!?;: '\"")
    for v in valid_values:
        if lowered == v.lower():
            return {"matched": v, "source": "groq", "reason": "exact"}
    for v in valid_values:
        if v.lower() in lowered:
            return {"matched": v, "source": "groq", "reason": "substring"}
    return {"matched": None, "source": "groq", "reason": f"no_match:{raw[:40]!r}"}
