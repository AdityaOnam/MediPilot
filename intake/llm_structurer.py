"""
M06 — LLM structurer.

Turns one free-text turn (a patient/attendant utterance, already
transcribed by M05 if spoken) into the StructuredNarrative schema defined
in intake/models.py. Extraction ONLY: no diagnosis, no acuity, no
Red/Yellow/Green. The output schema below has no field for any of those,
and the system prompt explicitly forbids inferring them — the red-flag
pass (intake/red_flags.py) is a separate, deterministic module that never
asks this one "is this a red flag".

Two implementations of the same interface:
  - GroqLLMStructurer — calls the Groq API (openai/gpt-oss-20b by default)
    with a JSON-schema-constrained request (strict structured outputs).
    Requires the `groq` package and a GROQ_API_KEY the SDK resolves from
    the environment. No key is ever hardcoded or read directly by this
    module beyond checking that one is present — the SDK's default client
    resolves it.
  - RuleBasedStructurer — a deterministic, offline keyword/regex extractor.
    This is NOT an LLM. It exists so the intake flow, and its tests, can
    run without network access or an API key, using the exact same
    interface and output schema as the real structurer.

intake/question_tree.py depends only on the LLMStructurer interface, so it
does not know or care which implementation it is talking to.
"""

from __future__ import annotations

import json
import os
import re
from abc import ABC, abstractmethod
from typing import Optional

from intake.models import ObservationCode, StructuredNarrative

_VALID_SYMPTOM_CODES = {c.value for c in ObservationCode}

# Defense in depth: even though the JSON-schema-constrained API request has
# no property for any of these, a candidate output (from any implementation
# of this interface, including future ones) is rejected outright if one
# shows up. M06 must never carry a clinical decision.
_FORBIDDEN_KEYS = {
    "diagnosis", "band", "acuity", "acuity_band", "triage", "red_flag",
    "risk", "severity_band", "clinical_confidence", "medical_confidence",
    "patient_reliability",
}

_SCHEMA = {
    "type": "object",
    "properties": {
        "chief_complaint": {"type": ["string", "null"]},
        "onset_minutes": {"type": ["integer", "null"]},
        "self_reported_severity": {"type": ["integer", "null"], "minimum": 0, "maximum": 10},
        "symptoms": {
            "type": "array",
            "items": {"type": "string", "enum": sorted(_VALID_SYMPTOM_CODES)},
        },
        "medications": {"type": "array", "items": {"type": "string"}},
        "pregnancy_status": {"type": ["boolean", "null"]},
        "relevant_history": {"type": "array", "items": {"type": "string"}},
    },
    "required": [
        "chief_complaint", "onset_minutes", "self_reported_severity",
        "symptoms", "medications", "pregnancy_status", "relevant_history",
    ],
    "additionalProperties": False,
}

_SYSTEM_PROMPT = """You extract structured fields from one turn of a patient/attendant \
intake conversation at a hospital triage desk. You are a transcription-to-fields \
extractor ONLY.

Rules, no exceptions:
- Extract only what the speaker actually stated in THIS transcript. Never infer, \
guess, or carry over information from outside the transcript.
- If a field was not mentioned, return null (or an empty array for list fields). \
Never fabricate a value to fill a field.
- You do NOT diagnose. You do NOT assign or imply a severity band, an acuity \
level, a triage colour, or a red-flag status. Those concepts do not exist in \
your output schema and must never appear in any field, including free-text \
fields like relevant_history.
- `symptoms` may only contain codes from the provided closed vocabulary. If \
something the speaker said does not clearly match one of those codes, leave \
it out of `symptoms` rather than inventing a new code.
- Preserve the language/wording faithfully; do not translate or normalize \
Hindi/Hinglish content into English.
- `self_reported_severity` is only set if the speaker gave a 0-10 number \
themselves; do not estimate it from descriptive language.
"""


class StructurerOutputError(Exception):
    """
    Raised when the structurer cannot produce a valid StructuredNarrative:
    malformed JSON, a schema violation, a forbidden clinical-decision key,
    or an underlying API failure (missing credentials, auth failure, rate
    limit, connection error). Callers must not fabricate a narrative when
    this is raised.
    """


class LLMStructurer(ABC):
    @abstractmethod
    def structure(self, transcript: str, context: Optional[dict] = None) -> StructuredNarrative:
        raise NotImplementedError


def _empty_narrative(raw_transcript: str, status: str) -> StructuredNarrative:
    return StructuredNarrative(raw_transcript=raw_transcript or "", extraction_status=status)


def validate_structured_narrative(raw: object, raw_transcript: str) -> StructuredNarrative:
    """
    Defense-in-depth validation of a candidate structured-output dict, on
    top of whatever schema constraint the caller already applied. Rejects
    anything resembling a clinical decision leaking into the output, and
    never lets an out-of-range or wrong-typed value through silently.
    """
    if not isinstance(raw, dict):
        raise StructurerOutputError(f"structured output is not a JSON object: {type(raw).__name__}")

    forbidden = _FORBIDDEN_KEYS & {str(k).lower() for k in raw.keys()}
    if forbidden:
        raise StructurerOutputError(
            f"structurer output contained forbidden clinical-decision keys: {sorted(forbidden)}"
        )

    severity = raw.get("self_reported_severity")
    if severity is not None and not (isinstance(severity, int) and not isinstance(severity, bool) and 0 <= severity <= 10):
        raise StructurerOutputError(f"self_reported_severity out of range or wrong type: {severity!r}")

    onset = raw.get("onset_minutes")
    if onset is not None and not (isinstance(onset, int) and not isinstance(onset, bool)):
        raise StructurerOutputError(f"onset_minutes wrong type: {onset!r}")

    symptoms_raw = raw.get("symptoms")
    if symptoms_raw is None:
        symptoms_raw = []
    if not isinstance(symptoms_raw, list):
        raise StructurerOutputError("symptoms must be a list")

    accepted, unrecognized = [], []
    for s in symptoms_raw:
        if isinstance(s, str) and s in _VALID_SYMPTOM_CODES:
            if s not in accepted:
                accepted.append(s)
        else:
            unrecognized.append(str(s))

    pregnancy = raw.get("pregnancy_status")
    if pregnancy is not None and not isinstance(pregnancy, bool):
        raise StructurerOutputError(f"pregnancy_status wrong type: {pregnancy!r}")

    medications = [m for m in (raw.get("medications") or []) if isinstance(m, str)]
    relevant_history = [h for h in (raw.get("relevant_history") or []) if isinstance(h, str)]

    chief_complaint = raw.get("chief_complaint")
    if chief_complaint is not None and not isinstance(chief_complaint, str):
        raise StructurerOutputError(f"chief_complaint wrong type: {chief_complaint!r}")

    return StructuredNarrative(
        chief_complaint=chief_complaint or None,
        onset_minutes=onset,
        self_reported_severity=severity,
        symptoms=accepted,
        medications=medications,
        pregnancy_status=pregnancy,
        relevant_history=relevant_history,
        raw_transcript=raw_transcript,
        extraction_status="ok",
        unrecognized_terms=unrecognized,
    )


class GroqLLMStructurer(LLMStructurer):
    """
    Calls the Groq API with a strict JSON-schema-constrained request
    (`response_format={"type": "json_schema", ...}`, strict=True) so the
    response can only ever contain the StructuredNarrative fields — there
    is no schema property for a diagnosis or a band, so the model is
    structurally incapable of returning one, and
    validate_structured_narrative() rejects it anyway as defense in depth.

    Default model: openai/gpt-oss-20b (Groq-hosted; supports strict
    structured outputs via constrained decoding).

    Credentials: resolved by the `groq` SDK's default client from the
    GROQ_API_KEY environment variable. This class never reads or hardcodes
    a key itself — it only checks that one is present so it can fail with
    a clear StructurerOutputError instead of an opaque SDK error.
    """

    DEFAULT_MODEL = "openai/gpt-oss-20b"

    def __init__(self, model: str = DEFAULT_MODEL, client=None):
        self.model = model
        self._client = client  # allows tests to inject a stub client

    def _ensure_client(self):
        if self._client is not None:
            return self._client
        try:
            import groq
        except ImportError as exc:
            raise StructurerOutputError(
                "the 'groq' package is not installed; "
                "install it (`pip install groq`) or inject a client for testing"
            ) from exc

        if not os.environ.get("GROQ_API_KEY"):
            raise StructurerOutputError(
                "no Groq credentials found: set the GROQ_API_KEY environment "
                "variable before using GroqLLMStructurer"
            )
        self._client = groq.Groq()
        return self._client

    def structure(self, transcript: str, context: Optional[dict] = None) -> StructuredNarrative:
        text = (transcript or "").strip()
        if not text:
            return _empty_narrative(transcript or "", "empty_input")

        client = self._ensure_client()  # raises StructurerOutputError if the
        # package is missing or no credentials are present, before we touch
        # the `groq` module directly below.
        import groq

        field_hint = (context or {}).get("field_hint") if context else None
        user_content = (
            f"Transcript of one intake turn"
            + (f" (question asked: {field_hint})" if field_hint else "")
            + f":\n\n{text}"
        )

        try:
            response = client.chat.completions.create(
                model=self.model,
                max_tokens=1024,
                messages=[
                    {"role": "system", "content": _SYSTEM_PROMPT},
                    {"role": "user", "content": user_content},
                ],
                response_format={
                    "type": "json_schema",
                    "json_schema": {
                        "name": "structured_narrative",
                        "strict": True,
                        "schema": _SCHEMA,
                    },
                },
            )
        except groq.AuthenticationError as exc:
            raise StructurerOutputError(f"Groq authentication failed: {exc}") from exc
        except groq.RateLimitError as exc:
            raise StructurerOutputError(f"Groq rate limited: {exc}") from exc
        except groq.BadRequestError as exc:
            # e.g. best-effort schema mismatch, or a request-shape error.
            raise StructurerOutputError(f"Groq rejected the request: {exc}") from exc
        except groq.APIConnectionError as exc:
            raise StructurerOutputError(f"Groq connection error: {exc}") from exc
        except groq.APIStatusError as exc:
            raise StructurerOutputError(f"Groq API error ({exc.status_code}): {exc}") from exc

        try:
            content = response.choices[0].message.content
            raw = json.loads(content)
        except (IndexError, AttributeError, TypeError, json.JSONDecodeError) as exc:
            raise StructurerOutputError(f"malformed structurer output: {exc}") from exc

        return validate_structured_narrative(raw, text)


class RuleBasedStructurer(LLMStructurer):
    """
    Deterministic, offline stand-in for the LLM structurer. NOT an LLM —
    a fixed keyword/regex extractor, documented as such. Implements the
    exact same interface and output schema as GroqLLMStructurer, so
    it can be swapped in for tests, demos, or offline operation without
    touching intake/question_tree.py.

    Covers a small set of English, Hindi and Hinglish keyword patterns
    (matching the vocabulary seen in speech/f_test*.ogg and test*.ogg) —
    illustrative for the prototype, not a substitute for the real
    extraction quality an LLM provides on messy or novel phrasing.
    """

    _SYMPTOM_KEYWORDS = {
        ObservationCode.CHEST_PAIN.value: [
            "chest pain", "chest mein pain", "chest me pain", "chest me dard", "seene mein dard",
        ],
        ObservationCode.SWEATING.value: ["sweating", "paseena", "pasina"],
        ObservationCode.BREATHLESSNESS.value: [
            "breathless", "can't breathe", "cannot breathe", "saans lene mein", "saans phool",
        ],
        ObservationCode.RADIATING_PAIN.value: ["radiating", "spreading to my arm", "spreads to arm"],
        ObservationCode.ALTERED_CONSCIOUSNESS.value: [
            "not responding", "unresponsive", "unconscious", "hosh nahi", "not oriented",
        ],
        ObservationCode.NOT_RESPONDING.value: ["not responding to me", "won't wake up", "wont wake up"],
        ObservationCode.ACTIVE_LABOUR.value: ["labour", "labor pains", "contractions"],
        ObservationCode.BLEEDING_IN_PREGNANCY.value: ["bleeding and pregnant", "pregnant and bleeding"],
        ObservationCode.DIFFICULTY_SPEAKING_FULL_SENTENCES.value: [
            "can't speak full sentences", "cannot complete a sentence", "cant finish a sentence",
        ],
        ObservationCode.SUDDEN_ONE_SIDED_WEAKNESS.value: [
            "one side weak", "one-sided weakness", "left side weak", "right side weak",
        ],
        ObservationCode.FACIAL_DROOP.value: ["face drooping", "facial droop", "face is drooping"],
        ObservationCode.SUDDEN_SPEECH_CHANGE.value: ["slurred speech", "speech changed suddenly"],
        ObservationCode.UNCONTROLLED_BLEEDING.value: [
            "bleeding heavily", "won't stop bleeding", "wont stop bleeding", "uncontrolled bleeding",
        ],
        ObservationCode.PENETRATING_INJURY.value: ["stabbed", "knife wound", "penetrating injury", "gunshot"],
        ObservationCode.POISONING_OR_OVERDOSE.value: ["poison", "overdose", "took too many pills"],
        ObservationCode.SNAKEBITE.value: ["snake bite", "snakebite"],
        ObservationCode.INFANT_NOT_FEEDING.value: ["not feeding", "won't feed", "refusing to feed"],
        ObservationCode.INFANT_FLOPPY.value: ["floppy", "limp baby"],
        ObservationCode.INFANT_INCONSOLABLE.value: ["inconsolable", "won't stop crying", "wont stop crying"],
        ObservationCode.FEVER.value: ["fever", "bukhar", "bukhaar"],
        ObservationCode.WEAKNESS_GENERAL.value: ["weakness", "kamzori", "kamzor"],
    }

    def structure(self, transcript: str, context: Optional[dict] = None) -> StructuredNarrative:
        text = (transcript or "").strip()
        if not text:
            return _empty_narrative(transcript or "", "empty_input")

        lowered = text.lower()
        symptoms = [
            code for code, keywords in self._SYMPTOM_KEYWORDS.items()
            if any(kw in lowered for kw in keywords)
        ]
        field_hint = (context or {}).get("field_hint") if context else None

        return StructuredNarrative(
            chief_complaint=text if field_hint == "chief_complaint" else None,
            onset_minutes=self._extract_onset(lowered) if field_hint in (None, "onset") else None,
            symptoms=symptoms,
            medications=self._split_list(text) if field_hint == "medications" else [],
            relevant_history=self._split_list(text) if field_hint == "relevant_history" else [],
            raw_transcript=text,
            extraction_status="ok",
        )

    @staticmethod
    def _split_list(text: str) -> list:
        parts = re.split(r",| and ", text)
        return [p.strip() for p in parts if p.strip()]

    @staticmethod
    def _extract_onset(lowered: str) -> Optional[int]:
        if "since morning" in lowered or "this morning" in lowered:
            return 6 * 60
        if "since yesterday" in lowered or "kal se" in lowered:
            return 24 * 60
        m = re.search(r"(\d+)\s*hour", lowered)
        if m:
            return int(m.group(1)) * 60
        m = re.search(r"(\d+)\s*min", lowered)
        if m:
            return int(m.group(1))
        m = re.search(r"(\d+)\s*day", lowered)
        if m:
            return int(m.group(1)) * 24 * 60
        return None
