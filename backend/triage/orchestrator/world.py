"""
World state: encounters advancing against a simulated clock.

Owns: encounter list, R, surge state, audit log, scheduler, tick loop.
The tick loop runs at 1 Hz real time, advancing each waiting encounter.
"""

from __future__ import annotations

import asyncio
import datetime
import hashlib
import json
import logging
import uuid
import pathlib
from dataclasses import dataclass, field
from typing import Optional, Any, Callable

from model.risk_model import score_patient_verbose, ScoreObject, AbstentionObject
from model.calibration import MODEL_VERSION, CALIBRATION_VERSION
from model.artifact import current_versions
from model.conformal import _thresholds_from_R, ConformalResult
from triage.band_engine import assign_band, AsymmetricAutonomyViolation, BAND_ORDER
from triage.recheck_scheduler import RecheckScheduler, PatientScheduleState
from triage.surge_controller import SurgeController, SurgeState
from triage.audit_log import AuditLog

from triage.orchestrator.clock import SimClock
from triage.orchestrator.seed import SeedRecord, load_seed, record_at
from triage.orchestrator import mapping

log = logging.getLogger(__name__)


@dataclass
class EncounterState:
    seed: SeedRecord
    current_band: Optional[str] = None
    human_assigned_band: Optional[str] = None
    last_scored_at: Optional[str] = None
    last_score_result: Optional[dict] = None
    last_p_model: Optional[float] = None
    last_conformal: Optional[Any] = None
    schedule_state: Optional[PatientScheduleState] = None
    timeline: list[dict] = field(default_factory=list)
    state: str = "waiting"
    manual_vitals: dict[str, tuple] = field(default_factory=dict)


class World:
    def __init__(self) -> None:
        self.clock = SimClock()
        self.R: Optional[float] = None  # None = USE_TRAINED_R
        self.encounters: dict[str, EncounterState] = {}
        self.scheduler = RecheckScheduler()
        self.surge_ctrl = SurgeController()
        self.surge_state = SurgeState()
        self.audit_log = AuditLog()
        self._sse_handlers: set[Callable] = set()
        self._tick_task: Optional[asyncio.Task] = None
        self._last_rescore_step: dict[str, int] = {}
        self._dynamic_encounters_file = pathlib.Path(__file__).parent.parent.parent / "data" / "dynamic_encounters.json"

    def bootstrap(self) -> None:
        t0 = self.clock.sim_now_iso()
        seeds = load_seed(t0)
        
        # Load any dynamic encounters created in previous runs
        if self._dynamic_encounters_file.exists():
            try:
                import json
                with open(self._dynamic_encounters_file, "r") as f:
                    dyn_data = json.load(f)
                    for rec_dict in dyn_data:
                        # Convert dict back to SeedRecord
                        seeds.append(SeedRecord(**rec_dict))
            except Exception as e:
                log.error(f"Failed to load dynamic encounters: {e}")

        for s in seeds:
            now = self.clock.sim_now()
            pr = record_at(s, 0, None, now)
            result, p_model, conf = score_patient_verbose(
                pr, cost_ratio_R=self.R, now=now, ood_flag=s.force_ood,
            )
            d = result.as_dict()

            human_band = s.human_assigned_band
            initial_band = d["band"]
            if human_band:
                hb_idx = BAND_ORDER.get(human_band.lower(), 1)
                ib_idx = BAND_ORDER.get(initial_band, 1)
                if hb_idx > ib_idx:
                    initial_band = human_band.lower()

            es = EncounterState(
                seed=s,
                current_band=initial_band,
                human_assigned_band=human_band,
                last_scored_at=now.isoformat(),
                last_score_result=d,
                last_p_model=p_model,
                last_conformal=conf,
            )
            es.schedule_state = PatientScheduleState(
                patient_id=s.encounter_id,
                current_band=initial_band,
                last_remeasure_at=now,
                admitted_at=now,
                abstained=d.get("abstained", False),
            )
            self.encounters[s.encounter_id] = es
            self._last_rescore_step[s.encounter_id] = 0

    def _save_dynamic_encounters(self) -> None:
        try:
            import json, dataclasses
            dyn_seeds = [
                dataclasses.asdict(es.seed) 
                for es in self.encounters.values() 
                if es.seed.encounter_id.startswith("P-") and int(es.seed.encounter_id[2:]) > 20
            ]
            self._dynamic_encounters_file.parent.mkdir(parents=True, exist_ok=True)
            with open(self._dynamic_encounters_file, "w") as f:
                json.dump(dyn_seeds, f, indent=2)
        except Exception as e:
            log.error(f"Failed to save dynamic encounters: {e}")

    def add_patient(self, seed: SeedRecord) -> tuple[str, str, str]:
        now = self.clock.sim_now()
        pr = record_at(seed, 0, None, now)
        result, p_model, conf = score_patient_verbose(
            pr, cost_ratio_R=self.R, now=now, ood_flag=seed.force_ood,
        )
        d = result.as_dict()

        scored_band = d["band"]

        # A red-flag rule (intake/red_flags.py) -- or, on a later submission
        # path, an actual clinician -- may have already set a floor before
        # this patient's first score ever ran. That floor arrives on
        # seed.human_assigned_band and MUST NOT be silently overwritten by
        # this initial model score: the model is being run here on
        # essentially no real vitals yet (this is arrival, not a
        # re-measurement), and per Invariant 1 the model may escalate on
        # its own but may never erase a human/rule-derived floor. Without
        # this check, add_patient() ignored seed.human_assigned_band
        # entirely and every red-flag escalation from POST
        # /v1/intake/submit was overwritten by the very first background
        # rescore tick a few seconds later.
        human_floor = seed.human_assigned_band
        if human_floor and BAND_ORDER.get(human_floor.lower(), 0) > BAND_ORDER.get(scored_band, 0):
            initial_band = human_floor.lower()
        else:
            initial_band = scored_band
            human_floor = None

        es = EncounterState(
            seed=seed,
            current_band=initial_band,
            human_assigned_band=human_floor,
            last_scored_at=now.isoformat(),
            last_score_result=d,
            last_p_model=p_model,
            last_conformal=conf,
        )
        es.schedule_state = PatientScheduleState(
            patient_id=seed.encounter_id,
            current_band=initial_band,
            last_remeasure_at=now,
            admitted_at=now,
            abstained=d.get("abstained", False),
        )
        self.encounters[seed.encounter_id] = es
        self._last_rescore_step[seed.encounter_id] = 0
        self._save_dynamic_encounters()

        # Emit SSE for board update
        self._emit({
            "type": "rescore",
            "encounterId": seed.encounter_id,
            "band": mapping.band_to_fe(es.current_band),
            "simTime": now.isoformat(),
        })

        return seed.encounter_id, seed.token, initial_band

    def start_tick_loop(self) -> None:
        if self._tick_task is None or self._tick_task.done():
            self._tick_task = asyncio.create_task(self._tick_loop())

    async def _tick_loop(self) -> None:
        while True:
            await asyncio.sleep(1.0)
            try:
                self._tick()
            except Exception:
                log.exception("tick error")

    def _tick(self) -> None:
        sim_now = self.clock.sim_now()
        for eid, es in self.encounters.items():
            if es.state != "waiting":
                continue

            arrived = datetime.datetime.fromisoformat(es.seed.arrived_at)
            if arrived.tzinfo is None:
                arrived = arrived.replace(tzinfo=datetime.timezone.utc)
            elapsed_s = (sim_now - arrived).total_seconds()
            k_step = max(0, int(elapsed_s / 300))

            prev_step = self._last_rescore_step.get(eid, 0)
            if k_step > prev_step:
                self._rescore(es, k_step, sim_now)
                self._last_rescore_step[eid] = k_step

            if es.schedule_state:
                events = self.scheduler.tick(
                    es.schedule_state, sim_now,
                    surge_mode=self.surge_state.in_surge,
                    surge_policy=self.surge_ctrl.current_policy(self.surge_state),
                )
                for evt_str in events:
                    self._handle_scheduler_event(es, evt_str, sim_now)

    def add_measurement(self, eid: str, vital_code: str, value: float, source: str, taken_at: str) -> None:
        es = self.encounters.get(eid)
        if not es:
            return
        # Store tuple in manual_vitals dict
        es.manual_vitals[vital_code] = (value, taken_at, source, "fresh")
        
        sim_now = self.clock.sim_now()
        # Reset the remeasure timer (schedule state)
        if es.schedule_state:
            es.schedule_state.last_remeasure_at = sim_now
            es.timeline.append({
                "at": sim_now.isoformat(), 
                "kind": "measurement", 
                "detail": f"{vital_code.upper()} = {value} ({source})"
            })
            
        # Trigger an immediate rescore.
        # We need to compute k_step
        arrived = datetime.datetime.fromisoformat(es.seed.arrived_at)
        if arrived.tzinfo is None:
            arrived = arrived.replace(tzinfo=datetime.timezone.utc)
        elapsed_s = (sim_now - arrived).total_seconds()
        k_step = max(0, int(elapsed_s / 300))
        
        self._rescore(es, k_step, sim_now)
        self._last_rescore_step[eid] = k_step

    def _rescore(self, es: EncounterState, k_step: int, sim_now: datetime.datetime) -> None:
        pr = record_at(es.seed, k_step, es.current_band, sim_now)
        
        # Apply manual measurements (overlay on top of the rebased trajectory)
        for code, tup in es.manual_vitals.items():
            if hasattr(pr, code):
                setattr(pr, code, tup)
                if pr.vitals_history is None:
                    pr.vitals_history = {}
                if code not in pr.vitals_history:
                    pr.vitals_history[code] = []
                pr.vitals_history[code].append(tup)
                
        result, p_model, conf = score_patient_verbose(
            pr, cost_ratio_R=self.R, now=sim_now, ood_flag=es.seed.force_ood,
        )
        d = result.as_dict()
        es.last_score_result = d
        es.last_p_model = p_model
        es.last_conformal = conf
        es.last_scored_at = sim_now.isoformat()

        old_band = es.current_band
        scored_band = d["band"]

        try:
            assignment = assign_band(
                patient_id=es.seed.encounter_id,
                scored_band=scored_band,
                current_band=es.current_band,
                reason="model_rescore",
                now=sim_now,
            )
            es.current_band = assignment.new_band
            if es.schedule_state:
                es.schedule_state.current_band = assignment.new_band

            if assignment.changed and assignment.direction == "escalation":
                self._emit({
                    "type": "escalation",
                    "encounterId": es.seed.encounter_id,
                    "from": mapping.band_to_fe(old_band),
                    "to": mapping.band_to_fe(assignment.new_band),
                    "cause": "MODEL",
                    "auditId": str(uuid.uuid4()),
                })
        except AsymmetricAutonomyViolation:
            pass

        self._emit({
            "type": "rescore",
            "encounterId": es.seed.encounter_id,
            "band": mapping.band_to_fe(es.current_band),
            "simTime": sim_now.isoformat(),
        })

    def _handle_scheduler_event(self, es: EncounterState, evt_str: str, sim_now: datetime.datetime) -> None:
        eid = es.seed.encounter_id

        if evt_str.startswith("escalate:yellow") and "time_in_queue" in evt_str:
            old_band = es.current_band
            es.current_band = "red"
            if es.schedule_state:
                es.schedule_state.current_band = "red"
            es.timeline.append({"at": sim_now.isoformat(), "kind": "band-change", "detail": f"Ceiling breach: {old_band} → red"})
            self._emit({
                "type": "escalation",
                "encounterId": eid,
                "from": mapping.band_to_fe(old_band),
                "to": "RED",
                "cause": "CEILING",
                "auditId": str(uuid.uuid4()),
            })

        elif evt_str.startswith("escalate:green") and "missed_rechecks" in evt_str:
            old_band = es.current_band
            es.current_band = "yellow"
            if es.schedule_state:
                es.schedule_state.current_band = "yellow"
            es.timeline.append({"at": sim_now.isoformat(), "kind": "band-change", "detail": "Missed rechecks: green → yellow"})
            self._emit({
                "type": "escalation",
                "encounterId": eid,
                "from": "GREEN",
                "to": "YELLOW",
                "cause": "CEILING",
                "auditId": str(uuid.uuid4()),
            })

        elif evt_str.startswith("ceiling_breach"):
            self._emit({
                "type": "breach",
                "encounterId": eid,
                "kind": "CEILING_EXCEEDED",
                "bandChanged": False,
            })

        elif evt_str == "remeasure_due":
            self._emit({
                "type": "recheckDue",
                "encounterId": eid,
                "owner": "station",
            })
            self._emit({
                "type": "breach",
                "encounterId": eid,
                "kind": "REMEASURE_MISSED",
                "bandChanged": False,
            })

        elif evt_str == "unmet_review_breach":
            self._emit({
                "type": "breach",
                "encounterId": eid,
                "kind": "UNMET_REVIEW",
                "bandChanged": False,
            })

        elif evt_str == "senior_clinician_page":
            es.timeline.append({"at": sim_now.isoformat(), "kind": "alarm", "detail": "Senior clinician paged"})

    def rescore_all_for_R(self, new_R: Optional[float]) -> dict:
        """Re-evaluate all encounters with a new R. Returns {up, down} counts."""
        old_R = self.R
        self.R = new_R
        up = 0
        down = 0
        sim_now = self.clock.sim_now()

        for eid, es in self.encounters.items():
            if es.state != "waiting":
                continue
            p_model = es.last_p_model
            if p_model is None:
                continue

            try:
                from model.artifact import get_artifact
                art = get_artifact()
                if art is None:
                    continue
                p_yellow, p_red = _thresholds_from_R(art, new_R, es.last_score_result.get("age_stratum", "adult"))
            except Exception:
                continue

            if p_model >= p_red:
                new_band = "red"
            elif p_model >= p_yellow:
                new_band = "yellow"
            else:
                new_band = "green"

            floor = es.human_assigned_band
            if floor:
                floor_idx = BAND_ORDER.get(floor.lower(), 0)
                new_idx = BAND_ORDER.get(new_band, 1)
                if new_idx < floor_idx:
                    new_band = floor.lower()

            old_idx = BAND_ORDER.get(es.current_band or "yellow", 1)
            new_idx = BAND_ORDER.get(new_band, 1)
            if new_idx > old_idx:
                up += 1
                es.current_band = new_band
                if es.schedule_state:
                    es.schedule_state.current_band = new_band
            # Invariant 1: autonomous de-escalation is never applied.
            # down stays 0 structurally.

        return {"up": up, "down": down}

    def get_encounter_dto_data(self, es: EncounterState) -> dict:
        """Build raw dict for an encounter — caller converts to EncounterDTO."""
        sim_now = self.clock.sim_now()
        arrived = datetime.datetime.fromisoformat(es.seed.arrived_at)
        if arrived.tzinfo is None:
            arrived = arrived.replace(tzinfo=datetime.timezone.utc)

        elapsed_s = (sim_now - arrived).total_seconds()
        k_step = max(0, int(elapsed_s / 300))

        measurements = self._build_measurements(es, k_step)
        cadence = self._build_cadence(es, sim_now)

        return {
            "encounterId": es.seed.encounter_id,
            "token": es.seed.token,
            "displayName": es.seed.display_name,
            "ageYears": es.seed.age_years,
            "ageStratum": es.seed.stratum,
            "ageStratumInferred": es.seed.stratum_inferred,
            "sex": es.seed.sex,
            "chiefComplaint": es.seed.chief_complaint,
            "arrivedAt": es.seed.arrived_at,
            "arrivalMode": es.seed.arrival_mode,
            "humanAssignedBand": mapping.band_to_fe(es.human_assigned_band) if es.human_assigned_band else None,
            "currentBand": mapping.band_to_fe(es.current_band),
            "measurements": measurements,
            "cadence": cadence,
            "hasPriorRecord": es.seed.has_prior_record,
            "assisted": es.seed.assisted,
            "humanAssistanceRequested": False,
            "medicalInfoConsent": es.seed.medical_info_consent,
            "state": es.state,
            "lastScoredAt": es.last_scored_at,
        }

    def _build_measurements(self, es: EncounterState, k_step: int) -> list[dict]:
        traj = es.seed.trajectory
        sim_now = self.clock.sim_now()
        arrived = datetime.datetime.fromisoformat(es.seed.arrived_at)
        if arrived.tzinfo is None:
            arrived = arrived.replace(tzinfo=datetime.timezone.utc)

        measurements = []
        vital_map = {
            "hr": "HR", "rr": "RR", "bp_sys": "SBP", "spo2": "SPO2",
            "temp_c": "TEMP", "gcs": "GCS", "pain_score": "PAIN",
        }

        for be_vital, fe_code in vital_map.items():
            readings = traj.get(be_vital, [])
            if not readings:
                continue
            idx = min(k_step, len(readings) - 1)
            r = readings[idx]
            ts = (arrived + datetime.timedelta(minutes=idx * 5)).isoformat()

            reading_age_s = (sim_now - (arrived + datetime.timedelta(minutes=idx * 5))).total_seconds()
            if es.seed.stale_vitals_hours > 0:
                reading_age_s += es.seed.stale_vitals_hours * 3600

            band_key = es.current_band or "yellow"
            cadence_table = {"red": 300, "yellow": 1800, "green": 3600}
            remeasure_s = cadence_table.get(band_key, 1800)

            if reading_age_s > remeasure_s * 3:
                validity = "expired"
            elif reading_age_s > remeasure_s * 2:
                validity = "discounted"
            else:
                validity = "fresh"

            measurements.append({
                "code": fe_code,
                "value": r["value"],
                "unit": mapping.vital_unit(fe_code),
                "takenAt": ts,
                "source": r.get("source", "station"),
                "validity": validity,
            })

        # Overlay anything a clinician entered by hand. Without this, a
        # nurse could record a vital, get a 200 back, and never see it on
        # the card -- the reading was stored in manual_vitals but the DTO
        # was built only from the seeded trajectory.
        #
        # A hand-entered reading REPLACES the trajectory value for the same
        # vital (it is newer and a human took it), and a code with no
        # trajectory at all -- including a custom field a nurse typed in
        # themselves -- is appended. Custom codes carry no unit and are
        # deliberately not fed to the scorer (see _rescore's hasattr guard):
        # recorded and visible to the clinician, never silently scored.
        for code, tup in es.manual_vitals.items():
            value, taken_at, source, validity = tup
            fe_code = mapping.vital_code_to_fe(code)
            entry = {
                "code": fe_code,
                "value": value,
                "unit": mapping.vital_unit(fe_code),
                "takenAt": taken_at,
                "source": source,
                "validity": validity,
            }
            for i, existing in enumerate(measurements):
                if existing["code"] == fe_code:
                    measurements[i] = entry
                    break
            else:
                measurements.append(entry)

        return measurements

    def _build_cadence(self, es: EncounterState, sim_now: datetime.datetime) -> dict:
        band = es.current_band or "yellow"
        is_abstained = es.last_score_result and es.last_score_result.get("abstained", False)

        cadence_key = "ABSTAINED" if is_abstained else band.upper()
        table = {
            "RED": {"rescoreSec": 60, "remeasureSec": 300, "ceilingSec": 0},
            "YELLOW": {"rescoreSec": 300, "remeasureSec": 1800, "ceilingSec": 3600},
            "GREEN": {"rescoreSec": 300, "remeasureSec": 3600, "ceilingSec": 7200},
            "ABSTAINED": {"rescoreSec": 300, "remeasureSec": 1800, "ceilingSec": 900},
        }
        c = table.get(cadence_key, table["YELLOW"])

        last_scored = sim_now
        if es.last_scored_at:
            last_scored = datetime.datetime.fromisoformat(es.last_scored_at)
            if last_scored.tzinfo is None:
                last_scored = last_scored.replace(tzinfo=datetime.timezone.utc)

        arrived = datetime.datetime.fromisoformat(es.seed.arrived_at)
        if arrived.tzinfo is None:
            arrived = arrived.replace(tzinfo=datetime.timezone.utc)

        next_rescore = last_scored + datetime.timedelta(seconds=c["rescoreSec"])
        next_remeasure = last_scored + datetime.timedelta(seconds=c["remeasureSec"])
        ceiling_breach = arrived + datetime.timedelta(seconds=c["ceilingSec"])

        breached = sim_now >= ceiling_breach if c["ceilingSec"] >= 0 else False
        breach_kind = "CEILING_EXCEEDED" if breached else None

        return {
            "rescoreSec": c["rescoreSec"],
            "remeasureSec": c["remeasureSec"],
            "ceilingSec": c["ceilingSec"],
            "nextRescoreAt": next_rescore.isoformat(),
            "nextRemeasureAt": next_remeasure.isoformat(),
            "ceilingBreachesAt": ceiling_breach.isoformat(),
            "breached": breached,
            "breachKind": breach_kind,
        }

    def build_score_response(self, es: EncounterState) -> dict:
        d = es.last_score_result or {}
        sim_now = self.clock.sim_now()
        mv, cv = current_versions()

        abstained = d.get("abstained", False)
        effective_band = mapping.band_to_fe(es.current_band) or "YELLOW"
        if abstained:
            effective_band = "YELLOW"

        factors_for = d.get("factors_for", [])
        factors_against = d.get("factors_against", [])
        score_source = d.get("score_source", "heuristic")

        channel1 = []
        for f in factors_for[:2]:
            channel1.append({"label": f, "direction": "supports", "magnitude": 0.7, "source": score_source if score_source != "red_flag_rule" else "rule"})
        for f in factors_against[:1]:
            channel1.append({"label": f, "direction": "opposes", "magnitude": 0.3, "source": score_source if score_source != "red_flag_rule" else "rule"})

        discounts = mapping.discounts_to_fe(d.get("reliability_discounts_applied", []))

        conf = es.last_conformal
        conformal_set = None
        coverage = None
        if conf and hasattr(conf, "prediction_set"):
            conformal_set = [mapping.band_to_fe(b) for b in conf.prediction_set]
            coverage = 1.0 - conf.uncertainty_width if hasattr(conf, "uncertainty_width") else None

        inputs_used = []
        for vital in ["hr", "rr", "bp_sys", "spo2", "temp_c", "gcs", "pain_score"]:
            inputs_used.append(mapping.vital_code_to_fe(vital))

        red_flags = None
        if score_source == "red_flag_rule":
            red_flags = [{"observation": factors_for[0] if factors_for else "red flag", "mapsTo": "RED", "lockedDownward": True}]

        threshold_used = 0.0
        cost_r = self.R
        if cost_r is not None:
            threshold_used = 1.0 / (1.0 + cost_r)
        else:
            try:
                from model.artifact import get_artifact
                art = get_artifact()
                if art:
                    threshold_used = float(art.thresholds.get("p_star_yellow", 0.05))
                    r_ref = float(art.thresholds.get("R_yellow", 12.15))
                    cost_r = r_ref
            except Exception:
                cost_r = 12.15
                threshold_used = 1.0 / (1.0 + cost_r)

        response = {
            "encounterId": es.seed.encounter_id,
            "serverTime": self.clock.real_now_iso(),
            "simTime": sim_now.isoformat(),
            "abstained": abstained,
            "effectiveBand": effective_band,
            "thresholdUsed": round(threshold_used, 4),
            "costRatioR": round(cost_r or 12.15, 2),
            "modelVersion": d.get("model_version", mv),
            "calibrationVersion": d.get("calibration_version", cv),
            "auditId": str(uuid.uuid4()),
        }

        if abstained:
            response["abstentionReason"] = mapping.abstention_reason(d.get("confidence_reason"))
        else:
            response["band"] = mapping.band_to_fe(d.get("band"))
            response["probability"] = es.last_p_model
            response["conformalSet"] = conformal_set
            response["coverage"] = coverage
            response["confidence"] = mapping.confidence_label(d.get("confidence", 0))
            response["confidenceReducedBy"] = mapping.parse_confidence_reduced_by(d.get("confidence_reason"))
            response["inputsUsed"] = inputs_used
            response["redFlags"] = red_flags
            response["explanation"] = {
                "channel1": channel1,
                "channel2": {"considered": [f for f in factors_against], "discounts": discounts},
                "channel3": {"narrative": [], "timeline": es.timeline[-10:]},
            }

        return response

    def subscribe(self, handler: Callable) -> Callable:
        self._sse_handlers.add(handler)
        def unsub():
            self._sse_handlers.discard(handler)
        return unsub

    def _emit(self, event: dict) -> None:
        for handler in list(self._sse_handlers):
            try:
                handler(event)
            except Exception:
                log.exception("SSE handler error")
