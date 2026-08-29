"""
M04 complaint classification -- decides which situation-specific question
branch to ask next, based on the MEANING of what the patient said, not on
matching pre-written phrases.

Real patients describe the same problem in endless different ways: English,
Hindi, Hinglish, incomplete sentences, and wording no keyword list could
anticipate ("mujhe pet ajeeb lag raha hai aur ulti bhi ho rahi hai" -- "my
stomach feels weird and I'm also vomiting" -- contains no recognizable
"abdominal pain" phrase at all, yet a nurse understands it instantly).
Rather than growing an ever-larger keyword list to chase every possible
phrasing, this module asks an LLM which of the fixed category names the
complaint best fits, given the full text.

This is a ROUTING decision only, never a clinical one: the classifier picks
which QUESTIONS to ask next -- never a diagnosis, acuity, or red flag. The
constrained output schema below has no field for any of those, exactly like
intake/llm_structurer.py's StructuredNarrative schema, and this module does
not import or modify intake/llm_structurer.py at all -- that file, its
model, its prompt, and its API integration are untouched.

Two implementations of the same interface:
  - GroqComplaintClassifier: a small, separate Groq call, strict
    JSON-schema-constrained to return exactly one of the category names it
    was given (never a free-form string), openai/gpt-oss-20b, GROQ_API_KEY.
  - KeywordComplaintClassifier: deterministic, offline, always succeeds.
    Used as the resilient degrade-gracefully path when no Groq credentials
    are available or a classification call fails -- not as the primary
    mechanism. See intake/question_tree.py for how the two are combined:
    symptom-code evidence first (already vetted, closed vocabulary), then
    this classifier, then the keyword fallback only as a last resort.
"""

from __future__ import annotations

import json
import os
from abc import ABC, abstractmethod
from typing import Optional, Sequence


class ComplaintClassifierError(Exception):
    """Raised when a classifier cannot produce a routing decision (missing
    package/credentials, API failure, malformed response). Callers should
    catch this and fall back to a different classifier rather than let a
    routing failure interrupt the conversation -- classification is a
    best-effort convenience, unlike M06 extraction, which must be explicit
    about failure because its output is never silently substituted."""


class ComplaintClassifier(ABC):
    @abstractmethod
    def classify(self, text: str, category_names: Sequence[str], fallback: str = "generic") -> str:
        """Return exactly one of category_names, or `fallback` if none fit."""
        raise NotImplementedError


class GroqComplaintClassifier(ComplaintClassifier):
    """
    Asks Groq which category best matches the complaint. The response
    schema's `category` field is an enum over exactly `category_names +
    [fallback]` -- the model is structurally unable to return anything else,
    including a diagnosis or invented category.
    """

    DEFAULT_MODEL = "openai/gpt-oss-20b"

    _SYSTEM_PROMPT = (
        "You are a triage-desk intake router. Given one patient or attendant "
        "description of their complaint -- which may be in English, Hindi, "
        "Hinglish, informal, incomplete, or phrased in ways a fixed keyword "
        "list would not anticipate -- choose exactly one category from the "
        "provided list that best matches what they described, so the intake "
        "system can ask the most relevant next follow-up questions.\n\n"
        "This is a ROUTING decision only. You are not diagnosing, not "
        "assigning severity or acuity, and not deciding whether anything is "
        "an emergency. If nothing fits well, or the text does not describe a "
        "clear presenting complaint, choose the fallback category."
    )

    def __init__(self, model: str = DEFAULT_MODEL, client=None):
        self.model = model
        self._client = client  # allows tests to inject a stub client

    def _ensure_client(self):
        if self._client is not None:
            return self._client
        try:
            import groq
        except ImportError as exc:
            raise ComplaintClassifierError(
                "the 'groq' package is not installed; "
                "install it (`pip install groq`) or inject a client for testing"
            ) from exc
        if not os.environ.get("GROQ_API_KEY"):
            raise ComplaintClassifierError(
                "no Groq credentials found: set the GROQ_API_KEY environment "
                "variable before using GroqComplaintClassifier"
            )
        self._client = groq.Groq()
        return self._client

    def classify(self, text: str, category_names: Sequence[str], fallback: str = "generic") -> str:
        text = (text or "").strip()
        if not text:
            return fallback

        client = self._ensure_client()
        import groq

        options = list(dict.fromkeys(list(category_names) + [fallback]))  # de-duplicated, order-preserved
        schema = {
            "type": "object",
            "properties": {"category": {"type": "string", "enum": options}},
            "required": ["category"],
            "additionalProperties": False,
        }

        try:
            response = client.chat.completions.create(
                model=self.model,
                max_tokens=64,
                messages=[
                    {"role": "system", "content": self._SYSTEM_PROMPT},
                    {"role": "user", "content": f"Complaint: {text}\n\nFallback category if none fit: {fallback}"},
                ],
                response_format={
                    "type": "json_schema",
                    "json_schema": {"name": "complaint_category", "strict": True, "schema": schema},
                },
            )
        except groq.AuthenticationError as exc:
            raise ComplaintClassifierError(f"Groq authentication failed: {exc}") from exc
        except groq.RateLimitError as exc:
            raise ComplaintClassifierError(f"Groq rate limited: {exc}") from exc
        except groq.BadRequestError as exc:
            raise ComplaintClassifierError(f"Groq rejected the request: {exc}") from exc
        except groq.APIConnectionError as exc:
            raise ComplaintClassifierError(f"Groq connection error: {exc}") from exc
        except groq.APIStatusError as exc:
            raise ComplaintClassifierError(f"Groq API error ({exc.status_code}): {exc}") from exc

        try:
            content = response.choices[0].message.content
            raw = json.loads(content)
            category = raw["category"]
        except (IndexError, AttributeError, TypeError, KeyError, json.JSONDecodeError) as exc:
            raise ComplaintClassifierError(f"malformed classifier output: {exc}") from exc

        return category if category in options else fallback


class KeywordComplaintClassifier(ComplaintClassifier):
    """
    Deterministic, offline fallback. NOT an LLM -- substring matching against
    a caller-supplied keyword map, documented as a conservative last resort
    (see intake/question_tree.py for the actual keyword data). Always
    succeeds; never raises.
    """

    def __init__(self, keyword_map: Optional[dict] = None):
        self.keyword_map = keyword_map or {}

    def classify(self, text: str, category_names: Sequence[str], fallback: str = "generic") -> str:
        normalized = (text or "").lower().replace("'", "")
        for name in category_names:
            keywords = self.keyword_map.get(name, ())
            if keywords and any(kw in normalized for kw in keywords):
                return name
        return fallback
