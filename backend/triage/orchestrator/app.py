"""
Orchestrator FastAPI app — serves the frontend contract at /v1/*.

Run from backend/:
    .venv/Scripts/python.exe -m uvicorn triage.orchestrator.app:app --port 8000
"""

from __future__ import annotations

import asyncio
import json
import hashlib
import uuid
import logging
from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI, HTTPException, Request, Response, File, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from triage.orchestrator.world import World
from triage.orchestrator import mapping
from model.artifact import current_versions
from triage.band_engine import AsymmetricAutonomyViolation, BAND_ORDER
from triage.audit_log import ValidationError

log = logging.getLogger(__name__)

# How many intake desks this site has. Demo value -- a real deployment
# reads this from site config, not a constant.
INTAKE_COUNTER_COUNT = 4

world = World()


@asynccontextmanager
async def lifespan(app: FastAPI):
    world.bootstrap()
    world.start_tick_loop()
    yield


app = FastAPI(
    title="MediPilot Orchestrator",
    version="1.0.0",
    lifespan=lifespan,
)

import os

# Comma-separated list of allowed frontend origins, e.g. the Vercel
# deployment URL(s). Falls back to local dev origins when unset so `uvicorn`
# still works out of the box on a laptop.
_default_origins = "http://localhost:3000,http://127.0.0.1:3000"
_allowed_origins = [
    o.strip() for o in os.getenv("ALLOWED_ORIGINS", _default_origins).split(",") if o.strip()
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_allowed_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Request schemas
# ---------------------------------------------------------------------------

class ScoreRequest(BaseModel):
    encounter_id: str = Field(alias="encounterId")
    model_config = {"populate_by_name": True}


class DecisionInput(BaseModel):
    encounter_id: str = Field(alias="encounterId")
    action: str
    band: Optional[str] = None
    reason_code: Optional[str] = Field(None, alias="reasonCode")
    reason_text: Optional[str] = Field(None, alias="reasonText")
    clinician_id: str = Field(alias="clinicianId")
    clinician_role: str = Field(alias="clinicianRole")
    factors_shown: Optional[list[dict]] = Field(None, alias="factorsShown")
    score_at_decision: Optional[dict] = Field(None, alias="scoreAtDecision")
    model_config = {"populate_by_name": True}


class SurgeInput(BaseModel):
    active: bool


class RInput(BaseModel):
    r: float = Field(alias="R")
    model_config = {"populate_by_name": True}


class IntakeSubmission(BaseModel):
    display_name: str = Field(alias="displayName")
    age_years: Optional[float] = Field(None, alias="ageYears")
    sex: Optional[str] = None
    chief_complaint: str = Field(alias="chiefComplaint")
    arrival_mode: str = Field(alias="arrivalMode")
    assisted: bool
    human_assistance_requested: bool = Field(alias="humanAssistanceRequested")
    medical_info_consent: bool = Field(alias="medicalInfoConsent")
    listening_consent: bool = Field(alias="listeningConsent")
    language: str
    symptom_answers: dict[str, str] = Field(default_factory=dict, alias="symptomAnswers")
    red_flags_fired: list[str] = Field(default_factory=list, alias="redFlagsFired")
    model_config = {"populate_by_name": True}


class StructureRequest(BaseModel):
    text: str
    language: str = "en"


class OptionMatchInput(BaseModel):
    """Only used when the client-side matcher has already given up. The
    frontend sends the question the patient is on, what they said, and the
    exact option set on screen -- see backend/orchestrator/option_matcher.py.
    """
    question_prompt: str = Field(alias="questionPrompt")
    patient_text: str = Field(alias="patientText")
    options: list = Field(default_factory=list)
    model_config = {"populate_by_name": True}


class MeasurementInput(BaseModel):
    code: str
    value: float
    source: str
    taken_at: str = Field(alias="takenAt")
    model_config = {"populate_by_name": True}




class ClockInput(BaseModel):
    speed: float


class TreeStartInput(BaseModel):
    age_years: Optional[float] = Field(None, alias="ageYears")
    medical_info_consent: bool = Field(True, alias="medicalInfoConsent")
    language: str = "en"
    model_config = {"populate_by_name": True}


class TreeAnswerInput(BaseModel):
    session_id: str = Field(alias="sessionId")
    text: str
    model_config = {"populate_by_name": True}


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.get("/v1/config")
def get_config():
    from triage.orchestrator import speech_intake

    mv, cv = current_versions()
    r_val = world.R
    if r_val is None:
        r_val = 12.15
        try:
            from model.artifact import get_artifact
            art = get_artifact()
            if art:
                r_val = float(art.thresholds.get("R_yellow", 12.15))
        except Exception:
            pass

    return {
        "costRatioR": round(r_val, 2),
        "rBounds": {"min": 1.0, "max": 30.0},
        "cadences": {
            "RED": {"rescoreSec": 60, "remeasureSec": 300, "ceilingSec": 0},
            "YELLOW": {"rescoreSec": 300, "remeasureSec": 1800, "ceilingSec": 3600},
            "GREEN": {"rescoreSec": 300, "remeasureSec": 3600, "ceilingSec": 7200},
            "ABSTAINED": {"rescoreSec": 300, "remeasureSec": 1800, "ceilingSec": 900},
        },
        "strata": [
            {"stratum": "neonate", "minDays": 0, "maxDays": 27},
            {"stratum": "infant", "minDays": 28, "maxDays": 364},
            {"stratum": "child", "minDays": 365, "maxDays": 4379},
            {"stratum": "adolescent", "minDays": 4380, "maxDays": 6569},
            {"stratum": "adult", "minDays": 6570, "maxDays": 23724},
            {"stratum": "geriatric", "minDays": 23725, "maxDays": 99999},
        ],
        "modelVersion": mv,
        "calibrationVersion": cv,
        # Which perception backends are actually live. Surfaced so the
        # judge-facing control panel never implies an LLM is doing the
        # extraction when the deterministic keyword fallback is.
        "perception": speech_intake.backend_status(),
    }


@app.get("/v1/census")
def get_census():
    result = []
    for eid, es in world.encounters.items():
        result.append(world.get_encounter_dto_data(es))
    return result


@app.get("/v1/encounter/{encounter_id}")
def get_encounter(encounter_id: str):
    es = world.encounters.get(encounter_id)
    if not es:
        raise HTTPException(404, f"Encounter {encounter_id} not found")
    return world.get_encounter_dto_data(es)


@app.post("/v1/speech/transcribe")
async def transcribe_audio(file: UploadFile = File(...)):
    """
    M05 — transcribe one completed Tap-to-Speak recording.

    Delegates to backend/orchestrator/speech_intake.py, which by default
    calls Groq's hosted whisper-large-v3-turbo (see §16: the demo must not
    depend on a GPU, a tunnel, or a process staying alive).

    On failure this returns 503 rather than a placeholder string. An earlier
    version answered every failure with "This is a fallback transcription
    from the backend." — a fabricated patient utterance entering a clinical
    pipeline. The intake state machine already handles a failed voice turn by
    re-prompting or falling back to typed input, which is the honest
    behaviour and the one §09 assumes.
    """
    from triage.orchestrator import speech_intake

    audio_bytes = await file.read()
    if not audio_bytes:
        raise HTTPException(400, "empty audio upload")

    try:
        result = speech_intake.transcribe(audio_bytes, file.filename or "utterance.webm")
    except speech_intake.TranscriptionUnavailable as exc:
        log.warning("transcription unavailable: %s", exc)
        raise HTTPException(503, f"transcription unavailable: {exc}")

    # `text` first so the frontend's existing {text} contract still holds;
    # everything else is ASR-observable metadata the intake layer consumes.
    return {
        "text": result["text"],
        "language": result["language"],
        "languageConfidence": result["language_confidence"],
        "codeMixed": result["code_mixed"],
        "asrReliability": result["asr_reliability"],
        "backend": result["backend"],
    }


@app.post("/v1/score")
def score_encounter(req: ScoreRequest):
    eid = req.encounter_id
    es = world.encounters.get(eid)
    if not es:
        raise HTTPException(404, f"Encounter {eid} not found")

    import datetime
    sim_now = world.clock.sim_now()
    arrived = datetime.datetime.fromisoformat(es.seed.arrived_at)
    if arrived.tzinfo is None:
        arrived = arrived.replace(tzinfo=datetime.timezone.utc)
    elapsed_s = (sim_now - arrived).total_seconds()
    k_step = max(0, int(elapsed_s / 300))

    from triage.orchestrator.seed import record_at
    from model.risk_model import score_patient_verbose

    pr = record_at(es.seed, k_step, es.current_band, sim_now)
    result, p_model, conf = score_patient_verbose(
        pr, cost_ratio_R=world.R, now=sim_now, ood_flag=es.seed.force_ood,
    )
    d = result.as_dict()
    es.last_score_result = d
    es.last_p_model = p_model
    es.last_conformal = conf
    es.last_scored_at = sim_now.isoformat()

    try:
        from triage.band_engine import assign_band
        assignment = assign_band(
            patient_id=eid,
            scored_band=d["band"],
            current_band=es.current_band,
            reason="manual_rescore",
            now=sim_now,
        )
        es.current_band = assignment.new_band
        if es.schedule_state:
            es.schedule_state.current_band = assignment.new_band
    except AsymmetricAutonomyViolation:
        pass

    return world.build_score_response(es)


@app.get("/v1/rechecks")
def get_rechecks():
    tasks = []
    for eid, es in world.encounters.items():
        if es.state != "waiting":
            continue
        cadence = world._build_cadence(es, world.clock.sim_now())
        tasks.append({
            "encounterId": eid,
            "owner": "station",
            "trust": "full",
            "dueAt": cadence["nextRemeasureAt"],
            "canCloseBands": ["RED", "YELLOW", "GREEN"],
        })
    return tasks


@app.post("/v1/decision")
def post_decision(req: DecisionInput):
    eid = req.encounter_id
    es = world.encounters.get(eid)
    if not es:
        raise HTTPException(404, f"Encounter {eid} not found")

    import datetime
    sim_now = world.clock.sim_now()
    d = es.last_score_result or {}

    system_band = mapping.band_to_fe(es.current_band) or "YELLOW"
    if req.action == "accept":
        clinician_band = system_band
    else:
        clinician_band = req.band or system_band

    score_val = es.last_p_model or d.get("confidence", 0.0)
    conf_val = d.get("confidence", 0.0)

    factors_shown = req.factors_shown or []
    inputs_hash = hashlib.sha256(json.dumps(d, default=str).encode()).hexdigest()
    mv, cv = current_versions()

    reason_code = req.reason_code or "other-with-note"
    reason_text = req.reason_text or (f"Accepted {system_band} band" if req.action == "accept" else "Override")

    try:
        record = world.audit_log.record_override(
            patient_id=eid,
            clinician_id=req.clinician_id,
            clinician_role=req.clinician_role,
            system_band=mapping.band_to_be(system_band) or "yellow",
            clinician_band=mapping.band_to_be(clinician_band) or "yellow",
            reason_code=reason_code,
            reason_text=reason_text,
            score=round(score_val, 4),
            confidence=round(conf_val, 4),
            factors_shown=factors_shown,
            inputs_hash=inputs_hash,
            model_version=d.get("model_version", mv),
            calibration_version=d.get("calibration_version", cv),
            consent_state={"medicalInfo": es.seed.medical_info_consent},
            outcome_ref=None,
            now=sim_now,
        )
    except ValidationError as e:
        raise HTTPException(422, str(e))

    if req.action == "override" and req.band:
        new_band_be = mapping.band_to_be(req.band)
        try:
            from triage.band_engine import assign_band
            assignment = assign_band(
                patient_id=eid,
                scored_band=new_band_be,
                current_band=es.current_band,
                last_human_action=record.record_hash,
                reason=f"clinician_override:{reason_code}",
                now=sim_now,
            )
            es.current_band = assignment.new_band
            if es.schedule_state:
                es.schedule_state.current_band = assignment.new_band
            if es.human_assigned_band is None or BAND_ORDER.get(assignment.new_band, 0) > BAND_ORDER.get(es.human_assigned_band.lower() if es.human_assigned_band else "green", 0):
                es.human_assigned_band = mapping.band_to_fe(assignment.new_band)
        except AsymmetricAutonomyViolation as e:
            raise HTTPException(409, str(e))

    rec_dict = record.as_dict()
    return {
        "patientId": rec_dict["patient_id"],
        "timestampUtc": rec_dict["timestamp_utc"],
        "clinicianId": rec_dict["clinician_id"],
        "clinicianRole": rec_dict["clinician_role"],
        "systemBand": mapping.band_to_fe(rec_dict["system_band"]),
        "clinicianBand": mapping.band_to_fe(rec_dict["clinician_band"]),
        "direction": mapping.direction_to_fe(rec_dict["direction"]),
        "reasonCode": rec_dict["reason_code"],
        "reasonText": rec_dict["reason_text"],
        "score": rec_dict["score"],
        "confidence": mapping.confidence_label(rec_dict["confidence"]),
        "factorsShown": factors_shown,
        "inputsHash": rec_dict["inputs_hash"],
        "modelVersion": rec_dict["model_version"],
        "calibrationVersion": rec_dict["calibration_version"],
        "consentState": json.dumps(rec_dict["consent_state"]),
        "outcomeRef": rec_dict["outcome_ref"],
        "hash": rec_dict["record_hash"],
        "prevHash": rec_dict["previous_record_hash"],
    }


@app.get("/v1/surge")
def get_surge():
    return _surge_dto()


@app.post("/v1/surge")
def set_surge(req: SurgeInput):
    import datetime
    sim_now = world.clock.sim_now()
    if req.active and not world.surge_state.in_surge:
        world.surge_ctrl.record_arrival(world.surge_state, sim_now)
        for _ in range(20):
            world.surge_ctrl.record_arrival(world.surge_state, sim_now)
    elif not req.active:
        world.surge_state.in_surge = False

    world._emit({
        "type": "surge",
        "active": world.surge_state.in_surge,
        "multiplier": 3.0 if world.surge_state.in_surge else 1.0,
    })
    return _surge_dto()


def _surge_dto():
    in_surge = world.surge_state.in_surge
    stretched = []
    if in_surge:
        stretched = [
            {"band": "YELLOW", "fromSec": 1800, "toSec": 2700},
            {"band": "GREEN", "fromSec": 3600, "toSec": 5400},
        ]
    return {
        "active": in_surge,
        "multiplier": 3.0 if in_surge else 1.0,
        "stretched": stretched,
        "refusals": ["Red re-measurement cadence unchanged"] if in_surge else [],
    }


@app.get("/v1/audit")
def get_audit(since: Optional[str] = None):
    records = world.audit_log.records
    if since:
        records = [r for r in records if r.timestamp_utc >= since]
    result = []
    for r in reversed(records):
        d = r.as_dict()
        result.append({
            "patientId": d["patient_id"],
            "timestampUtc": d["timestamp_utc"],
            "clinicianId": d["clinician_id"],
            "clinicianRole": d["clinician_role"],
            "systemBand": mapping.band_to_fe(d["system_band"]),
            "clinicianBand": mapping.band_to_fe(d["clinician_band"]),
            "direction": mapping.direction_to_fe(d["direction"]),
            "reasonCode": d["reason_code"],
            "reasonText": d["reason_text"],
            "score": d["score"],
            "confidence": mapping.confidence_label(d["confidence"]),
            "factorsShown": d["factors_shown"],
            "inputsHash": d["inputs_hash"],
            "modelVersion": d["model_version"],
            "calibrationVersion": d["calibration_version"],
            "consentState": json.dumps(d["consent_state"]),
            "outcomeRef": d["outcome_ref"],
            "hash": d["record_hash"],
            "prevHash": d["previous_record_hash"],
        })
    return result


@app.post("/v1/control/r")
def set_r(req: RInput):
    new_R = max(1.0, min(30.0, req.r))
    moved = world.rescore_all_for_R(new_R)

    effective_R = new_R
    p_star = 1.0 / (1.0 + effective_R)

    census = []
    for eid, es in world.encounters.items():
        census.append(world.get_encounter_dto_data(es))

    return {
        "R": round(effective_R, 2),
        "pStar": round(p_star, 4),
        "moved": moved,
        "note": f"R set to {effective_R:.2f}. {moved['up']} escalated, {moved['down']} held (Invariant 1).",
        "census": census,
    }


@app.post("/v1/control/clock")
def set_clock(req: ClockInput):
    world.clock.set_speed(max(0.0, min(600.0, req.speed)))
    return {
        "simTime": world.clock.sim_now_iso(),
        "speed": world.clock.speed,
    }


@app.get("/v1/stream")
async def stream_events(request: Request):
    queue: asyncio.Queue = asyncio.Queue()

    def handler(event: dict):
        try:
            queue.put_nowait(event)
        except asyncio.QueueFull:
            pass

    unsub = world.subscribe(handler)

    async def event_generator():
        try:
            while True:
                if await request.is_disconnected():
                    break
                try:
                    event = await asyncio.wait_for(queue.get(), timeout=15.0)
                    yield f"data: {json.dumps(event)}\n\n"
                except asyncio.TimeoutError:
                    yield f": keepalive\n\n"
        finally:
            unsub()

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )

@app.post("/v1/intake/submit")
def submit_intake(req: IntakeSubmission):
    from triage.orchestrator.seed import SeedRecord, _infer_stratum
    
    # Generate ID and token
    next_num = len([e for e in world.encounters.values() if e.seed.encounter_id.startswith("P-")]) + 1
    new_id = f"P-{next_num:02d}"
    new_token = str(200 + next_num)
    
    # Calculate age and stratum
    age_days = int(req.age_years * 365.25) if req.age_years is not None else None
    stratum_inferred = age_days is None
    stratum = _infer_stratum(age_days) if age_days is not None else "adult"
    
    # Generate a flat trajectory
    traj = [{"at_min": 0}]
    
    # Mid-tree short-circuit. When intake fired a red-flag rule (see
    # §10 and intake/pipeline.py's needs_immediate_nurse), submit_intake
    # must NOT queue this patient behind others waiting for a model score:
    # the rule already decided this is a nurse-now case. So the human-
    # assigned band is set to RED right here -- it did not come from the
    # model, and Invariant §1 (asymmetric autonomy) allows a rule-based
    # ESCALATION without a clinician's signature; only de-escalation
    # requires one.
    needs_immediate_nurse = bool(req.red_flags_fired)
    initial_human_band = "RED" if needs_immediate_nurse else None

    s = SeedRecord(
        encounter_id=new_id,
        token=new_token,
        display_name=req.display_name,
        age_years=req.age_years,
        age_days=age_days,
        stratum=stratum,
        stratum_inferred=stratum_inferred,
        sex=req.sex,
        chief_complaint=req.chief_complaint,
        arrival_mode=req.arrival_mode,
        human_assigned_band=initial_human_band,
        arrived_at=world.clock.sim_now_iso(),
        assisted=req.assisted,
        medical_info_consent=req.medical_info_consent,
        has_prior_record=False,
        red_flag_observations=req.red_flags_fired,
        reliability_flags={},
        force_ood=False,
        spo2_bias_risk=False,
        trajectory={"steps": traj, "final_outcome_band": "UNKNOWN"},
        stale_vitals_hours=0.0,
        zero_history=True,
    )

    encounter_id, token, initial_band = world.add_patient(s)

    # If a red flag fired, force the returned currentBand to RED regardless
    # of what world.add_patient() picked from the (empty) initial vitals --
    # the fixed table is authoritative for the escalation direction, and a
    # frontend that shows anything but RED here would contradict what the
    # patient's own words already established.
    if needs_immediate_nurse:
        initial_band = "RED"

    # Where the patient physically goes next. A token alone tells someone
    # they are in a queue but not where to stand -- in a real ED waiting
    # area that is the difference between the number meaning something and
    # meaning nothing. Deliberately NOT a clinical decision: a red-flag
    # patient is sent to the triage bay because a nurse is already coming
    # to them, everyone else is spread across the open counters so one
    # desk does not absorb the whole queue.
    if needs_immediate_nurse:
        counter = "Triage Bay"
    else:
        counter = f"Counter {(next_num % INTAKE_COUNTER_COUNT) + 1}"

    return {
        "encounterId": encounter_id,
        "token": token,
        "counter": counter,
        "currentBand": initial_band,
        "humanAssignedBand": initial_human_band,
        # New: tells the frontend to skip the "your queue position" screen
        # and jump straight to "a nurse is coming to you now" -- the token
        # was still issued, but no queue applies.
        "needsImmediateNurse": needs_immediate_nurse,
        "redFlagsFired": list(req.red_flags_fired),
    }


@app.post("/v1/intake/tree/start")
def intake_tree_start(req: TreeStartInput):
    """
    Begin a walk through the REAL M04 question tree (intake/question_tree.py)
    and return its first question. See backend/orchestrator/tree_session.py
    for why the tree is driven from the server rather than shipped to the
    browser as data.
    """
    from triage.orchestrator import tree_session

    return tree_session.start(
        age_years=req.age_years,
        medical_info_consent=req.medical_info_consent,
        language=req.language,
    )


@app.post("/v1/intake/tree/answer")
def intake_tree_answer(req: TreeAnswerInput):
    """
    Record one answer and return the next question the tree decided on --
    which depends on what the structurer extracted, what the patient already
    volunteered, and whether the red-flag table has fired.

    `accepted: false` means the answer could not be parsed for a yes/no or
    0-10 node and the SAME question is being repeated. That is a normal
    conversational outcome, not an error, so it is a 200.
    """
    from triage.orchestrator import tree_session

    try:
        return tree_session.answer(req.session_id, req.text)
    except tree_session.TreeSessionError as exc:
        raise HTTPException(404, str(exc)) from exc


@app.get("/v1/intake/tree/structure")
def intake_tree_structure():
    """
    The whole decision tree: every complaint category, its questions, and
    their conditional level-2 follow-ups. Session-independent. Used by the
    kiosk's tree-flow panel so a reviewer can see the branching that a
    single patient's linear path does not reveal.
    """
    from triage.orchestrator import tree_session

    return tree_session.structure()


@app.get("/v1/intake/tree/{session_id}/answers")
def intake_tree_answers(session_id: str):
    """Flat {nodeId: raw answer} for the readback screen and submission."""
    from triage.orchestrator import tree_session

    try:
        return tree_session.collected_answers(session_id)
    except tree_session.TreeSessionError as exc:
        raise HTTPException(404, str(exc)) from exc


@app.post("/v1/intake/tree/match-option")
def match_option(req: OptionMatchInput):
    """
    LLM-assisted option matching for the tree UI. Called ONLY when the
    frontend's Jaccard matcher scored below its threshold: the patient
    said something that plausibly matches an on-screen choice but the
    keyword overlap wasn't sharp enough to auto-advance on. Groq gets the
    question, the options, and what was actually said, and returns one of
    the option values or NONE. See backend/orchestrator/option_matcher.py.
    """
    from triage.orchestrator import option_matcher

    return option_matcher.match(
        question_prompt=req.question_prompt,
        patient_text=req.patient_text,
        options=req.options,
    )


@app.post("/v1/structure")
def structure_text(req: StructureRequest):
    """
    M06 (LLM structurer) followed by M07 (deterministic red-flag pass).

    The split is the point, per §10: the LLM extracts observations into a
    closed vocabulary under a strict JSON schema, and a fixed table
    (intake/red_flags.py) maps those observations to Red. The model is never
    asked whether something is a red flag, and its output schema has no field
    for a band, an acuity or a diagnosis.

    This replaces eight hardcoded regexes that also emitted a `severity`
    string of their own invention — M06 asserting acuity, which Invariant 2
    forbids.
    """
    from triage.orchestrator import speech_intake

    text = (req.text or "").strip()
    if not text:
        raise HTTPException(400, "empty text")

    narrative, structurer_name = speech_intake.structure_text(text)
    return speech_intake.narrative_to_response(narrative, structurer_name)


@app.post("/v1/encounter/{encounter_id}/measurement")
def add_measurement(encounter_id: str, req: MeasurementInput):
    es = world.encounters.get(encounter_id)
    if not es:
        raise HTTPException(404, f"Encounter {encounter_id} not found")
        
    world.add_measurement(
        eid=encounter_id,
        vital_code=req.code.lower(),
        value=req.value,
        source=req.source,
        taken_at=req.taken_at
    )
    
    return world.get_encounter_dto_data(es)

