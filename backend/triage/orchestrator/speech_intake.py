"""
Wiring between the orchestrator's HTTP surface and the intake/speech layer.

This module is the only place where the FastAPI app knows that M05 (speech)
and M06 (LLM structurer) exist. It owns four things:

  1. Backend selection and lazy singletons, so a model or client is
     constructed once per process and only if something actually calls it.
  2. The fallback chain, so a cold local model server or an expired API key
     degrades the demo instead of ending it.
  3. Honest reporting of which backend actually ran, so nothing ever claims
     local inference or LLM extraction it did not perform.
  4. Translation from the intake layer's dataclasses to the JSON shape
     web/lib/api/types.ts expects.

The deployment position this implements
---------------------------------------
Local inference is the destination, not an optimisation. Under India's DPDP
Act 2023 and §13's log properties ("Raw patient data stays at the
institution; only model updates leave"), a structurer and an ASR running
inside the hospital are what the plan commits to. Hosted free-tier APIs are
the fallback that keeps a demo alive on unfamiliar conference wifi, and a
deterministic non-LLM extractor is the floor beneath both.

So both chains run local-first by default and fall back outward:

    ASR:  faster-whisper (local)  ->  Groq hosted Whisper  ->  503
    M06:  local OpenAI-compatible ->  Groq hosted LLM     ->  RuleBasedStructurer

Each step down is logged, surfaced on GET /v1/config, and named on the
response, because a demo that silently degrades from local to hosted is
making a privacy claim it is no longer honouring.

What this module deliberately does NOT do
-----------------------------------------
It never invents a transcript, and it never invents a band. The original
implementation of POST /v1/speech/transcribe returned the literal string
"This is a fallback transcription from the backend." whenever its socket
failed; that is a fabricated patient utterance flowing into a clinical
pipeline, and it is gone. A failed ASR turn now surfaces as a failure, which
intake/state_machine.py already handles by re-prompting or falling back to
typed input.

Likewise, red-flag verdicts come only from intake/red_flags.py's fixed table
applied to extracted ObservationCodes -- per §10, "the LLM extracts
observations; a fixed table maps observations to Red." The structurer is
never asked whether something is a red flag.
"""

from __future__ import annotations

import logging
import os
import threading
from typing import Optional

from intake.llm_structurer import (
    GroqLLMStructurer,
    LLMStructurer,
    LocalOpenAICompatStructurer,
    RuleBasedStructurer,
    StructurerOutputError,
)
from intake.models import StructuredNarrative
from intake.red_flags import evaluate_all_red_flags

log = logging.getLogger(__name__)


def _env_chain(var: str, default: str) -> list:
    """Parse a comma-separated backend preference list, e.g. 'local,groq'."""
    return [p.strip().lower() for p in os.getenv(var, default).split(",") if p.strip()]


# MEDIPILOT_ASR_BACKEND: comma-separated preference order.
#   local — faster-whisper (CTranslate2, int8). No network, no key, no audio
#           leaves the building. Needs requirements-speech-local.txt.
#   whisper — openai-whisper in-process. Included for the bake-off; CPU-only
#           on AMD hardware and slow, so not a serving default.
#   groq  — hosted whisper-large-v3-turbo. The fallback: no GPU, no tunnel,
#           nothing to keep alive (§16).
#   off   — refuse transcription, for a typed-only run.
ASR_CHAIN = _env_chain("MEDIPILOT_ASR_BACKEND", "local,groq")

# MEDIPILOT_STRUCTURER: comma-separated preference order.
#   local — a local OpenAI-compatible server (Ollama / llama.cpp / LM Studio).
#   groq  — hosted, JSON-schema-constrained.
#   rules — RuleBasedStructurer: deterministic keywords, explicitly NOT an
#           LLM. Always the last resort; never silently presented as one.
STRUCTURER_CHAIN = _env_chain("MEDIPILOT_STRUCTURER", "local,groq,rules")

_asr = None
_asr_name: Optional[str] = None
_asr_lock = threading.Lock()

_structurer: Optional[LLMStructurer] = None
_structurer_name: Optional[str] = None
_structurer_lock = threading.Lock()

# Backends that have already failed this process. Re-trying a cold model
# server or a dead key on every single intake turn adds seconds to each
# answer, which on a triage kiosk is the difference between a demo and a
# queue.
#
# Kept per stage, NOT in one shared set: "groq" means two different things
# here (a Whisper endpoint and a chat endpoint), and a missing GROQ_API_KEY
# is common to both while a cold Ollama server is not. Sharing one set let a
# structurer failure silently disqualify an ASR backend that was fine.
_failed_asr: set = set()
_failed_structurer: set = set()


class TranscriptionUnavailable(Exception):
    """No ASR backend could run. Carries a human-readable reason."""


# ---------------------------------------------------------------------------
# ASR (M05)
# ---------------------------------------------------------------------------

def _build_asr(kind: str):
    """Construct one ASR backend. Raises if it cannot be built."""
    model_override = os.getenv("MEDIPILOT_WHISPER_MODEL")

    if kind == "local":
        from speech.faster_whisper_stt import DEFAULT_MODEL, FasterWhisperSTT

        return FasterWhisperSTT(model_override or DEFAULT_MODEL), "local"
    if kind == "whisper":
        from speech.whisper_stt import WhisperSTT

        return WhisperSTT(model_override or "turbo"), "whisper"
    if kind == "groq":
        from speech.groq_asr import DEFAULT_MODEL, GroqWhisperSTT

        stt = GroqWhisperSTT(model_override or DEFAULT_MODEL)
        # Fail here rather than on the first patient utterance.
        stt._ensure_client()
        return stt, "groq"
    raise ValueError(f"unknown ASR backend: {kind!r}")


def get_asr() -> tuple:
    """
    Resolve the first ASR backend in the chain that can actually be built.

    Returns (backend, kind). Raises TranscriptionUnavailable when every
    option in the chain fails, listing what was tried and why.
    """
    global _asr, _asr_name

    if ASR_CHAIN == ["off"]:
        raise TranscriptionUnavailable("ASR is disabled (MEDIPILOT_ASR_BACKEND=off)")

    if _asr is not None:
        return _asr, _asr_name

    with _asr_lock:
        if _asr is not None:
            return _asr, _asr_name

        attempts = []
        for kind in ASR_CHAIN:
            if kind == "off":
                break
            if kind in _failed_asr:
                continue
            try:
                _asr, _asr_name = _build_asr(kind)
                log.info("ASR backend ready: %s", _asr_name)
                if _asr_name != ASR_CHAIN[0]:
                    log.warning(
                        "ASR fell back to %r — audio is leaving this machine. "
                        "The preferred backend %r was unavailable.",
                        _asr_name, ASR_CHAIN[0],
                    )
                return _asr, _asr_name
            except Exception as exc:
                _failed_asr.add(kind)
                attempts.append(f"{kind}: {exc}")
                log.warning("ASR backend %r unavailable: %s", kind, exc)

        if not attempts:
            # Every backend in the chain had already been eliminated earlier
            # in this process. Say so, rather than reporting an empty list.
            attempts = [f"{k}: eliminated earlier this session" for k in ASR_CHAIN
                        if k in _failed_asr]
        raise TranscriptionUnavailable(
            "no ASR backend available — tried " + "; ".join(attempts)
        )


def transcribe(audio_bytes: bytes, filename: str = "utterance.webm") -> dict:
    """
    Transcribe one uploaded utterance and return the asr_common result
    contract. Raises TranscriptionUnavailable on failure -- callers must
    surface that rather than substituting text.
    """
    stt, kind = get_asr()

    try:
        if kind == "whisper":
            # openai-whisper takes a path or a waveform, not raw bytes.
            import tempfile

            suffix = os.path.splitext(filename)[1] or ".webm"
            with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
                tmp.write(audio_bytes)
                tmp_path = tmp.name
            try:
                return stt.transcribe(tmp_path)
            finally:
                try:
                    os.unlink(tmp_path)
                except OSError:
                    pass
        return stt.transcribe(audio_bytes, filename=filename)
    except Exception as exc:
        raise TranscriptionUnavailable(f"transcription failed ({kind}): {exc}") from exc


# ---------------------------------------------------------------------------
# M06 structurer
# ---------------------------------------------------------------------------

def _build_structurer(kind: str) -> LLMStructurer:
    if kind == "local":
        return LocalOpenAICompatStructurer(
            os.getenv("MEDIPILOT_LOCAL_LLM_MODEL",
                      LocalOpenAICompatStructurer.DEFAULT_MODEL)
        )
    if kind == "groq":
        if not os.environ.get("GROQ_API_KEY"):
            raise RuntimeError("GROQ_API_KEY is not set")
        return GroqLLMStructurer(
            os.getenv("MEDIPILOT_STRUCTURER_MODEL", GroqLLMStructurer.DEFAULT_MODEL)
        )
    if kind == "rules":
        return RuleBasedStructurer()
    raise ValueError(f"unknown structurer backend: {kind!r}")


def get_structurer() -> tuple:
    """
    Resolve the first structurer in the chain that can be constructed.
    Returns (structurer, kind). Construction is cheap for all three, so a
    backend is only eliminated here for a missing key or a bad config -- a
    local server that is merely cold is discovered on first use, in
    structure_text() below.
    """
    global _structurer, _structurer_name

    if _structurer is not None:
        return _structurer, _structurer_name

    with _structurer_lock:
        if _structurer is not None:
            return _structurer, _structurer_name

        for kind in STRUCTURER_CHAIN:
            if kind in _failed_structurer:
                continue
            try:
                _structurer, _structurer_name = _build_structurer(kind), kind
                if kind == "rules":
                    log.warning(
                        "M06 is running on RuleBasedStructurer — deterministic "
                        "keyword matching, NOT an LLM. Extraction quality is the "
                        "documented floor, and GET /v1/config reports this."
                    )
                return _structurer, _structurer_name
            except Exception as exc:
                _failed_structurer.add(kind)
                log.warning("structurer %r unavailable: %s", kind, exc)

        # RuleBasedStructurer has no dependencies and cannot fail to build, so
        # this is only reachable if it was excluded from the chain entirely.
        _structurer, _structurer_name = RuleBasedStructurer(), "rules"
        return _structurer, _structurer_name


def structure_text(text: str, field_hint: Optional[str] = None) -> tuple:
    """
    Run M06 over one turn of text, walking down the chain on failure.

    Returns (narrative, structurer_label). The label names the backend that
    actually produced the result, including when it was a fallback -- so
    nothing downstream presents keyword matching as LLM extraction, or a
    hosted API call as local inference.
    """
    global _structurer, _structurer_name

    context = {"field_hint": field_hint} if field_hint else None
    _, current_kind = get_structurer()

    # Try the resolved backend, then everything after it in the chain.
    remaining = STRUCTURER_CHAIN[STRUCTURER_CHAIN.index(current_kind):] \
        if current_kind in STRUCTURER_CHAIN else [current_kind, "rules"]

    errors = []
    for kind in remaining:
        if kind in _failed_structurer and kind != current_kind:
            continue
        try:
            structurer = _structurer if kind == current_kind else _build_structurer(kind)
            narrative = structurer.structure(text, context)
        except Exception as exc:
            _failed_structurer.add(kind)
            errors.append(f"{kind}: {exc}")
            log.warning("M06 backend %r failed (%s); trying the next one", kind, exc)
            if kind == current_kind:
                # Stop handing new turns to a backend that just failed.
                _structurer, _structurer_name = None, None
            continue

        # Latch the backend that actually worked, so the next turn goes
        # straight to it and GET /v1/config reports what is really serving —
        # a status endpoint that still names the preferred-but-dead backend
        # would be asserting a privacy property the system is not honouring.
        if kind != current_kind:
            _structurer, _structurer_name = structurer, kind

        label = _label_for(kind)
        if errors:
            label += f" (fallback after {', '.join(e.split(':')[0] for e in errors)} failed)"
        return narrative, label

    # Unreachable in practice: RuleBasedStructurer is pure-python and offline.
    fallback = RuleBasedStructurer()
    _structurer, _structurer_name = fallback, "rules"
    return fallback.structure(text, context), (
        "RuleBasedStructurer (last resort; " + "; ".join(errors) + ")"
    )


def _label_for(kind: str) -> str:
    if kind == "local":
        model = os.getenv("MEDIPILOT_LOCAL_LLM_MODEL",
                          LocalOpenAICompatStructurer.DEFAULT_MODEL)
        return f"local:{model}"
    if kind == "groq":
        model = os.getenv("MEDIPILOT_STRUCTURER_MODEL", GroqLLMStructurer.DEFAULT_MODEL)
        return f"groq:{model}"
    return "RuleBasedStructurer (deterministic keywords, NOT an LLM)"


# ---------------------------------------------------------------------------
# Response mapping
# ---------------------------------------------------------------------------

def narrative_to_response(narrative: StructuredNarrative, structurer_name: str) -> dict:
    """
    Map a StructuredNarrative plus its deterministic red-flag verdict onto the
    StructureResponse shape in web/lib/api/types.ts.

    Note what is absent: there is no `severity` string. The stub this replaces
    emitted "severe" whenever any observation was extracted, which is M06
    asserting acuity -- exactly what §10 and Invariant 2 forbid. The only
    severity reported is `selfReportedSeverity`: the 0-10 number the patient
    said out loud, or null when they gave none.
    """
    red_flags = [
        {
            "observation": r.description,
            "ruleId": r.rule_id,
            "matchedObservations": r.matched_observations,
            "mapsTo": "RED",
            # §10: "A red-flag Red is not overridable downward by the system
            # under any subsequent model output — only a clinician can move
            # it, with a reason."
            "lockedDownward": True,
        }
        for r in evaluate_all_red_flags(narrative)
    ]

    return {
        "observations": list(narrative.symptoms),
        "redFlags": red_flags,
        "structuredFields": {
            "chiefComplaint": narrative.chief_complaint or narrative.raw_transcript,
            "onsetMinutes": narrative.onset_minutes,
            "selfReportedSeverity": narrative.self_reported_severity,
            "symptoms": list(narrative.symptoms),
            "medications": list(narrative.medications),
            "pregnancyStatus": narrative.pregnancy_status,
            "relevantHistory": list(narrative.relevant_history),
        },
        "extraction": {
            "status": narrative.extraction_status,
            "structurer": structurer_name,
            "unrecognizedTerms": list(narrative.unrecognized_terms),
        },
    }


def backend_status() -> dict:
    """
    Reported by GET /v1/config so the judge-facing control panel can show
    which paths are actually live.

    `dataLeavesMachine` is the one a judge should be able to read off the
    screen: it is true whenever a hosted API is serving either stage, which
    is exactly when the "patient data stays at the institution" claim does
    not currently hold.
    """
    asr_active = _asr_name
    structurer_active = _structurer_name

    hosted = {"groq"}
    leaving = (asr_active in hosted) or (structurer_active in hosted)

    return {
        "asrChain": ASR_CHAIN,
        "asrActive": asr_active,
        "structurerChain": STRUCTURER_CHAIN,
        "structurerActive": structurer_active,
        "structurerIsLLM": structurer_active in ("local", "groq"),
        "failedAsrBackends": sorted(_failed_asr),
        "failedStructurerBackends": sorted(_failed_structurer),
        "groqKeyPresent": bool(os.environ.get("GROQ_API_KEY")),
        "localLlmUrl": os.getenv("MEDIPILOT_LOCAL_LLM_URL",
                                 LocalOpenAICompatStructurer.DEFAULT_BASE_URL),
        # None until something has actually run — a status endpoint should not
        # assert where data is going before any data has gone anywhere.
        "dataLeavesMachine": leaving if (asr_active or structurer_active) else None,
    }
