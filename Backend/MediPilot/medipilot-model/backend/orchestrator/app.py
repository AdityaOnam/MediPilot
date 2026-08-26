"""
Orchestrator FastAPI app — serves the frontend contract at /v1/*.

Run from medipilot-model/:
    .venv/Scripts/python.exe -m uvicorn backend.orchestrator.app:app --port 8000
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

from backend.orchestrator.world import World
from backend.orchestrator import mapping
from model.artifact import current_versions
from backend.band_engine import AsymmetricAutonomyViolation, BAND_ORDER
from backend.audit_log import ValidationError

log = logging.getLogger(__name__)

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

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
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


class MeasurementInput(BaseModel):
    code: str
    value: float
    source: str
    taken_at: str = Field(alias="takenAt")
    model_config = {"populate_by_name": True}




class ClockInput(BaseModel):
    speed: float


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.get("/v1/config")
def get_config():
    mv, cv = current_versions()
    r_val = world.R
    if r_val is None:
        try:
            from model.artifact import get_artifact
            art = get_artifact()
            if art:
                r_val = float(art.thresholds.get("R_yellow", 12.15))
        except Exception:
            r_val = 12.15

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
    Receives recorded audio from the frontend.
    Proxy to the Colab Whisper ngrok TCP server.
    """
    import os
    host = os.getenv("WHISPER_HOST", "localhost")
    port = int(os.getenv("WHISPER_PORT", "43007"))
    
    try:
        # Read the entire audio blob (could be webm or wav)
        audio_bytes = await file.read()
        
        # If the Colab proxy is configured, send the bytes over TCP.
        # NOTE: For webm, the Colab server would need to parse it (Whisper uses ffmpeg).
        # We'll try to connect to the socket.
        import socket
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(5.0)
            s.connect((host, port))
            s.sendall(audio_bytes)
            # The Colab server responds with text
            s.settimeout(15.0)
            data = s.recv(4096)
            text = data.decode("utf-8").strip()
            return {"text": text}
    except Exception as e:
        # Fallback for the demo if Colab server is offline
        import logging
        logging.warning(f"Whisper proxy failed ({e}). Returning fallback text.")
        return {"text": "This is a fallback transcription from the backend."}
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

    from backend.orchestrator.seed import record_at
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
        from backend.band_engine import assign_band
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
            from backend.band_engine import assign_band
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
    from backend.orchestrator.seed import SeedRecord, _infer_stratum
    
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
        human_assigned_band=None,
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
    
    return {
        "encounterId": encounter_id,
        "token": token,
        "currentBand": initial_band,
        "humanAssignedBand": None
    }


@app.post("/v1/structure")
def structure_text(req: StructureRequest):
    import re
    text = req.text.lower()
    
    observations = []
    red_flags = []
    
    # 1. Altered consciousness
    if re.search(r'unresponsive|gcs\s*(of\s*)?[3-8]\b|status\s*epilepticus', text):
        observations.append("altered_consciousness")
        red_flags.append({
            "observation": "Altered consciousness / not responding",
            "mapsTo": "RED",
            "lockedDownward": True
        })
        
    # 2. Active labour or bleeding
    if re.search(r'active\s+labo(u)?r|contraction.{0,20}(2|3)\s*min', text):
        observations.append("active_labour_or_bleeding_pregnancy")
        red_flags.append({
            "observation": "Active labour, or bleeding in pregnancy",
            "mapsTo": "RED",
            "lockedDownward": True
        })
        
    # 3. Chest pain with sweating
    if re.search(r'crush(ing)?\s+(chest|substernal)\s*pain|radiat(ing|es?)\s+to\s+(left\s+)?arm', text):
        observations.append("chest_pain_with_sweating_radiation_breathlessness")
        red_flags.append({
            "observation": "Chest pain with sweating, radiation, or breathlessness",
            "mapsTo": "RED",
            "lockedDownward": True
        })
        
    # 4. Difficulty speaking
    if re.search(r'airway\s*(obstruct|comprom)|anaphyla', text):
        observations.append("difficulty_speaking_full_sentences")
        red_flags.append({
            "observation": "Difficulty speaking in full sentences",
            "mapsTo": "RED",
            "lockedDownward": True
        })
        
    # 5. Stroke
    if re.search(r'strok(e|ing).{0,20}(onset|acute|sudden)', text):
        observations.append("sudden_onesided_weakness_facial_droop_speech_change")
        red_flags.append({
            "observation": "Sudden one-sided weakness, facial droop, or speech change",
            "mapsTo": "RED",
            "lockedDownward": True
        })
        
    # 6. Bleeding
    if re.search(r'massive\s*(haemorrhage|hemorrhage|bleed)', text):
        observations.append("uncontrolled_bleeding_or_penetrating_injury")
        red_flags.append({
            "observation": "Uncontrolled bleeding, or penetrating injury",
            "mapsTo": "RED",
            "lockedDownward": True
        })
        
    # 7. Poisoning
    if re.search(r'poison|overdose|snakebite', text):
        observations.append("poisoning_overdose_or_snakebite")
        red_flags.append({
            "observation": "Poisoning, overdose, or snakebite",
            "mapsTo": "RED",
            "lockedDownward": True
        })
        
    # 8. Infant
    if re.search(r'floppy|inconsolable', text):
        observations.append("infant_not_feeding_floppy_inconsolable")
        red_flags.append({
            "observation": "Infant not feeding, floppy, or inconsolable",
            "mapsTo": "RED",
            "lockedDownward": True
        })
        
    return {
        "observations": observations,
        "redFlags": red_flags,
        "structuredFields": {
            "chiefComplaint": req.text,
            "onsetMinutes": None,
            "severity": "severe" if observations else "moderate"
        }
    }


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

