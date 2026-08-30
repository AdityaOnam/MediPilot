"""
Serves the REAL M04 question tree (intake/question_tree.py) over HTTP.

Until this module existed, the 140-node clinical tree — every
complaint-specific branch, every level-2 follow-up — was dead code as far
as the running product was concerned: nothing served it, and the kiosk
walked an 8-question static list defined separately in the frontend. This
is what connects them.

Why the tree must be driven turn-by-turn from the SERVER rather than
shipped to the browser as data: which question comes next is not a
property of the tree alone. It depends on

  * what the M06 structurer extracted from the previous free-text answer
    (classify_complaint picks the branch),
  * whether an upcoming question was already answered unprompted
    (_skip_known_nodes), and
  * whether intake/red_flags.py's fixed table has already fired, which
    truncates the remaining plan outright
    (_maybe_stop_for_confirmed_red_flag).

All three live in Python, next to the vocabulary and the rule table they
depend on. Shipping the tree to the client would mean reimplementing them
in TypeScript and keeping two copies of clinical routing logic in step —
exactly the drift that left the frontend walking a different tree in the
first place.

Session state is in-memory and per-process. An intake conversation is
short and a lost session costs the patient a restart, not data: nothing
here is the record of the visit. /v1/intake/submit still owns that.
"""

from __future__ import annotations

import threading
import time
import uuid
from dataclasses import dataclass, field
from typing import Optional

from intake.age_stratification import resolve_age_stratum
from intake.complaint_lexicon import (
    LEXICON_CONFIDENCE_MIN_LEN,
    score_categories,
)
from intake.llm_structurer import StructurerOutputError
from intake.models import AgeInfo, AgeSource, AgeStatus, ConsentState, Observation
from intake.question_tree import (
    COMPLAINT_BRANCHES,
    QuestionTreeSession,
    _CATEGORY_KEYWORDS,
    _CATEGORY_NAMES,
    build_plan,
)
from intake.red_flags import evaluate_red_flags
from intake.speech_adapter import Utterance
from intake.state_machine import InvalidAnswerError

# A kiosk conversation that has gone quiet for this long is abandoned --
# the patient walked away, or the tab was closed. Reaped so a long-running
# server does not accumulate dead sessions.
SESSION_TTL_SECONDS = 60 * 60


class TreeSessionError(Exception):
    """Unknown or expired session id."""


@dataclass
class _Entry:
    tree: QuestionTreeSession
    language: str
    created_at: float
    touched_at: float
    # Every red-flag observation seen across the whole conversation, so the
    # frontend can pass the full set to /v1/intake/submit even though the
    # tree truncates the moment the first one fires.
    red_flag_observations: list = field(default_factory=list)
    # Which ComplaintCategory the chief complaint routed to, once known.
    # Surfaced so the UI can say WHY these questions are being asked.
    branch: Optional[str] = None


_sessions: dict = {}
_lock = threading.Lock()


def _reap_expired(now: float) -> None:
    stale = [sid for sid, e in _sessions.items() if now - e.touched_at > SESSION_TTL_SECONDS]
    for sid in stale:
        _sessions.pop(sid, None)


def _get(session_id: str) -> _Entry:
    with _lock:
        entry = _sessions.get(session_id)
        if entry is None:
            raise TreeSessionError(f"unknown or expired intake session: {session_id}")
        entry.touched_at = time.time()
        return entry


def start(age_years: Optional[float], medical_info_consent: bool, language: str = "en") -> dict:
    """
    Build the plan for this patient's age stratum and return the first
    question. Age drives which tail (paediatric / geriatric / adult) the
    plan gets; consent drops the questions that require it rather than
    asking them and discarding the answer.
    """
    if age_years is None:
        # resolve_age_stratum's own widest-safety path. build_plan(None, ...)
        # then uses the paediatric branch, matching the architecture's
        # worked example for unresolved age.
        stratum = None
    else:
        age_info = AgeInfo(
            value_days=int(age_years * 365.25),
            source=AgeSource.PATIENT,
            status=AgeStatus.KNOWN,
        )
        stratum = resolve_age_stratum(age_info).stratum

    consent = ConsentState.GRANTED if medical_info_consent else ConsentState.DECLINED
    tree = QuestionTreeSession(plan=build_plan(stratum, consent))

    session_id = uuid.uuid4().hex
    now = time.time()
    with _lock:
        _reap_expired(now)
        _sessions[session_id] = _Entry(
            tree=tree, language=language, created_at=now, touched_at=now,
        )

    return {
        "sessionId": session_id,
        "stratum": stratum.value if stratum else None,
        **_state_of(tree, []),
    }


def answer(session_id: str, text: str) -> dict:
    """
    Record one answer and return whatever the tree decided comes next.

    A yes/no or 0-10 node whose answer could not be parsed is reported as
    `accepted: false` with the SAME question repeated -- the tree does not
    advance and nothing is fabricated. That is a normal conversational
    outcome ("could you say that again?"), not an error.
    """
    entry = _get(session_id)
    tree = entry.tree

    if tree.complete:
        return {"sessionId": session_id, "accepted": True, **_state_of(tree, entry.red_flag_observations, entry.branch)}

    # Fast path: on the chief-complaint turn (the first free-text answer),
    # if the lexicon has a confident match we skip the LLM structurer
    # entirely and splice the branch by hand. The extraction the structurer
    # would have done -- chief_complaint text, raw_transcript -- is trivial
    # to fill directly from the input; symptoms would still be missed here,
    # but the frontend already runs its own red-flag scan on every keystroke
    # so the interrupt overlay does not depend on this call, and the FULL
    # narrative extraction still happens for later free-text follow-ups.
    #
    # This turns a ~20s wait on turn 1 (local qwen2.5:3b on CPU) into the
    # network round-trip. Worth it because turn 1 is where every patient
    # starts, and the "Thinking..." wait there is the biggest UX hit.
    node = tree.current_node
    if node is not None and node.node_id == "chief_complaint" and (text or "").strip():
        cleaned = text.strip()
        scored = score_categories(cleaned, _CATEGORY_KEYWORDS)
        if scored and scored[0][1] >= LEXICON_CONFIDENCE_MIN_LEN:
            branch_name = scored[0][0] if scored[0][0] in _CATEGORY_NAMES else "generic"
            entry.branch = branch_name
            tree.narrative.chief_complaint = cleaned
            tree.narrative.raw_transcript = (
                (tree.narrative.raw_transcript + "\n" + cleaned).strip()
                if tree.narrative.raw_transcript else cleaned
            )
            tree.observations.append(Observation("chief_complaint", cleaned, "patient", cleaned))
            branch_questions = COMPLAINT_BRANCHES.get(branch_name, ())
            existing_ids = {n.node_id for n in tree.plan}
            new_nodes = [n for n in branch_questions if n.node_id not in existing_ids]
            insert_at = tree.cursor + 1
            tree.plan[insert_at:insert_at] = new_nodes
            tree._advance()
            tree._skip_known_nodes()
            tree._maybe_stop_for_confirmed_red_flag()
            return {
                "sessionId": session_id,
                "accepted": True,
                "note": f"lexicon_fast_path:{branch_name}",
                **_state_of(tree, entry.red_flag_observations, entry.branch),
            }

    from triage.orchestrator import speech_intake

    structurer, _ = speech_intake.get_structurer()
    utterance = Utterance(text=text or "", interaction_mode="voice", language=entry.language)

    accepted = True
    note = None
    try:
        tree.record_answer(utterance, structurer)
    except InvalidAnswerError:
        # Unparseable yes/no or severity. Stay on this question.
        accepted = False
        note = "unparsed_answer"
    except StructurerOutputError:
        # Extraction failed (model/API/malformed). Skip the node explicitly
        # rather than invent a value -- the field stays missing, exactly as
        # intake/pipeline.py does in the same situation.
        tree.skip_current(reason="structurer_failed")
        note = "structurer_failed"

    # The structurer path takes its branch decision inside
    # QuestionTreeSession._insert_branch_questions(); recover it here so
    # the UI can show which category is driving these questions.
    if entry.branch is None and tree.narrative.chief_complaint:
        from intake.question_tree import classify_complaint
        try:
            entry.branch = classify_complaint(tree.narrative)
        except Exception:  # noqa: BLE001 -- display metadata only
            entry.branch = None

    # Accumulate red flags across the conversation. The tree truncates on
    # the first confirmed one, but the caller needs the full observation
    # list for /v1/intake/submit.
    verdict = evaluate_red_flags(tree.narrative)
    if verdict.red_flag:
        for obs in verdict.matched_observations:
            if obs not in entry.red_flag_observations:
                entry.red_flag_observations.append(obs)

    result = {
        "sessionId": session_id,
        "accepted": accepted,
        **_state_of(tree, entry.red_flag_observations, entry.branch),
    }
    if note:
        result["note"] = note
    return result


def collected_answers(session_id: str) -> dict:
    """
    Flat {node_id: raw answer text} of everything answered so far, for the
    frontend's readback screen and for symptomAnswers on /v1/intake/submit.
    """
    entry = _get(session_id)
    out = {}
    for obs in entry.tree.observations:
        if obs.raw_answer:
            out[obs.field] = obs.raw_answer
    return out


def end(session_id: str) -> None:
    with _lock:
        _sessions.pop(session_id, None)


def _node_tree(node) -> dict:
    """One node plus its level-2 follow-ups, recursively. follow_ups are
    the questions that fire only when THIS node's answer matches its
    triggers -- rendering them nested is the only honest way to show that
    the tree is conditional rather than a flat list."""
    return {
        "nodeId": node.node_id,
        "prompt": node.prompt,
        "promptHi": node.prompt_hi,
        "kind": node.kind.value,
        "requiresConsent": node.requires_consent,
        "impliesSymptom": node.implies_symptom,
        "followUpTriggers": list(node.follow_up_triggers),
        "followUps": [_node_tree(f) for f in node.follow_ups],
    }


def structure() -> dict:
    """
    The WHOLE decision tree, independent of any session: every complaint
    category, the questions in each, and their conditional follow-ups.

    This is what a reviewer needs to see to understand the system --
    `_state_of`'s `plan` only shows the linear path one patient is on,
    which before the chief complaint is answered is just the seven shared
    questions and shows none of the branching.
    """
    from intake.question_tree import (
        CATEGORIES,
        _ADULT_ADOLESCENT_TAIL,
        _COMMON_OPENING,
        _GERIATRIC_TAIL,
        _PAEDIATRIC_TAIL,
    )

    return {
        "opening": [_node_tree(n) for n in _COMMON_OPENING],
        "tails": {
            "adult": [_node_tree(n) for n in _ADULT_ADOLESCENT_TAIL],
            "paediatric": [_node_tree(n) for n in _PAEDIATRIC_TAIL],
            "geriatric": [_node_tree(n) for n in _GERIATRIC_TAIL],
        },
        "categories": [
            {
                "name": c.name,
                "symptomCodes": list(c.symptom_codes),
                "keywordSample": list(c.keywords[:6]),
                "questions": [_node_tree(q) for q in c.questions],
            }
            for c in CATEGORIES
        ],
    }


def _state_of(tree: QuestionTreeSession, red_flag_observations: list, branch=None) -> dict:
    node = tree.current_node
    narrative = tree.narrative
    # A snapshot of the plan as it stands right now, so the frontend can
    # render "where am I in the tree?" for the demo. Status is derived
    # from the cursor: already-answered nodes are DONE, the cursor node
    # is CURRENT, anything after is UPCOMING. When the tree truncates on
    # a red flag, everything past the cursor disappears from the plan
    # itself -- that is the truncation showing through, not something
    # this response hides.
    plan_snapshot = []
    for i, n in enumerate(tree.plan):
        if tree.complete:
            status = "done"
        elif i < tree.cursor:
            status = "done"
        elif i == tree.cursor:
            status = "current"
        else:
            status = "upcoming"
        plan_snapshot.append({
            "nodeId": n.node_id,
            "prompt": n.prompt,
            "promptHi": n.prompt_hi,
            "kind": n.kind.value,
            "status": status,
        })
    return {
        "question": node.to_dict() if node else None,
        "complete": tree.complete,
        # The tree truncated itself because red_flags.py already confirmed a
        # time-critical presentation. The kiosk must route to a nurse now,
        # not keep asking.
        "stoppedForRedFlag": tree.stopped_for_red_flag,
        "redFlagObservations": list(red_flag_observations),
        "progress": {
            # cursor is 0-based; the question being ASKED is cursor+1 of the
            # plan as it currently stands. The denominator moves as branches
            # splice in, which is honest: the tree genuinely does not know
            # its own length until the complaint is known.
            "i": min(tree.cursor + 1, len(tree.plan)) if not tree.complete else len(tree.plan),
            "n": len(tree.plan),
        },
        "chiefComplaint": narrative.chief_complaint,
        "symptoms": list(narrative.symptoms),
        "plan": plan_snapshot,
        # Which ComplaintCategory these questions came from, so the UI can
        # explain WHY it is asking them.
        "branch": branch,
    }
