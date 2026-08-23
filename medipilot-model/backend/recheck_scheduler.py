"""
medipilot-model/backend/recheck_scheduler.py

Two-clock scheduler:
  Clock 1 — Re-score: model re-runs every 5 minutes for all patients.
  Clock 2 — Re-measure: physical vitals taken by band-specific cadence.

Key behaviours:
  - Stale readings trigger re-measurement tasks AHEAD of the fixed timer.
  - Ceiling breaches escalate or page senior clinician.
  - Green patient with 2 missed consecutive rechecks → escalate to Yellow.
  - Abstained patient: holds at Yellow, unreviewed past 15 min → breach.
  - Recheck trust levels: station > nurse > family > self-report.

Cadences and trust levels loaded from config/band_cadence.yaml.
"""

from __future__ import annotations

import datetime
import pathlib
from dataclasses import dataclass, field
from typing import Optional

import yaml


_CONFIG_PATH = pathlib.Path(__file__).parent.parent / "config" / "band_cadence.yaml"


@dataclass
class RecheckTask:
    """A pending re-measurement task."""
    patient_id: str
    band: str
    task_type: str          # "remeasure" | "rescore" | "wellbeing_contact" | "review"
    due_at: datetime.datetime
    raised_reason: str      # "scheduled" | "stale_reading" | "ceiling_breach"
    completed: bool = False
    completed_at: Optional[datetime.datetime] = None
    completed_by: str = ""  # "recheck_station" | "nurse" | "family" | "self_report"
    trusted: bool = True


@dataclass
class PatientScheduleState:
    """Tracks the recheck state for one patient."""
    patient_id: str
    current_band: str
    last_remeasure_at: Optional[datetime.datetime]
    admitted_at: datetime.datetime
    missed_remeasures: int = 0          # count of consecutive missed remeasures
    abstained: bool = False
    last_reviewed_at: Optional[datetime.datetime] = None  # for abstained patients
    tasks: list[RecheckTask] = field(default_factory=list)


class RecheckScheduler:
    """
    Manages the two-clock recheck schedule for all patients.
    Stateless per call — all state lives in PatientScheduleState objects
    passed in by the API layer.
    """

    def __init__(self, config_path: pathlib.Path = _CONFIG_PATH):
        with open(config_path, encoding="utf-8") as f:
            cfg = yaml.safe_load(f)
        self._bands = cfg["bands"]
        self._trust = cfg["recheck_trust"]
        self._freshness = cfg["freshness"]

    def _band_cfg(self, band: str) -> dict:
        return self._bands.get(band, self._bands["yellow"])

    def _trust_cfg(self, performer: str) -> dict:
        return self._trust.get(performer, {"trust": "partial", "can_close_red": False})

    # ------------------------------------------------------------------
    # Tick — called every minute by the scheduler loop
    # ------------------------------------------------------------------

    def tick(
        self,
        state: PatientScheduleState,
        now: datetime.datetime,
        surge_mode: bool = False,
        surge_policy: Optional[dict] = None,
    ) -> list[str]:
        """
        Process one scheduler tick for a patient.
        Returns a list of events raised (e.g. "rescore", "remeasure_due",
        "ceiling_breach", "escalate_to_yellow", "senior_clinician_page").
        """
        events: list[str] = []
        band = state.current_band
        cfg = self._band_cfg(band)

        rescore_s = cfg.get("rescore_interval_s", 300)
        remeasure_s = cfg.get("remeasure_interval_s", 1800)
        ceiling_s = cfg.get("wait_ceiling_s", 7200)

        # Apply surge stretch if active
        if surge_mode and cfg.get("surge_stretch_allowed", False) and surge_policy:
            remeasure_s = surge_policy.get(
                f"{band}_remeasure_s",
                remeasure_s
            )

        time_in_queue_s = (now - state.admitted_at).total_seconds()

        # ── Re-score clock (always every 5 min regardless of band) ───
        rescore_due = rescore_s  # fixed 300s
        if int(time_in_queue_s) % rescore_due < 60:
            events.append("rescore")

        # ── Re-measure clock ─────────────────────────────────────────
        if state.last_remeasure_at is not None:
            since_remeasure_s = (now - state.last_remeasure_at).total_seconds()
        else:
            since_remeasure_s = time_in_queue_s  # never measured

        if since_remeasure_s >= remeasure_s:
            events.append("remeasure_due")

        # ── Wait ceiling ─────────────────────────────────────────────
        if ceiling_s is not None and ceiling_s > 0:
            if time_in_queue_s >= ceiling_s:
                breach_action = cfg.get("ceiling_breach_action", "")
                events.append(f"ceiling_breach:{breach_action}")

                # Red: page senior clinician if still queued at 5 min
                if band == "red" and time_in_queue_s >= cfg.get("ceiling_breach_delay_s", 300):
                    events.append("senior_clinician_page")

                # Yellow: escalate to Red if re-measurement not done within 15 min
                if band == "yellow":
                    delay_s = cfg.get("ceiling_breach_delay_s", 900)
                    if since_remeasure_s >= (remeasure_s + delay_s):
                        events.append("escalate:yellow→red:time_in_queue")

        # ── Green: consecutive missed rechecks ───────────────────────
        if band == "green":
            max_missed = cfg.get("consecutive_missed_rechecks_escalate", 2)
            if state.missed_remeasures >= max_missed:
                events.append("escalate:green→yellow:missed_rechecks")

        # ── Abstained: 15-min review deadline ───────────────────────
        if state.abstained:
            abstain_ceiling_s = self._bands["abstained"]["wait_ceiling_s"]
            if time_in_queue_s >= abstain_ceiling_s:
                if state.last_reviewed_at is None:
                    events.append("unmet_review_breach")

        return events

    # ------------------------------------------------------------------
    # Mark recheck complete
    # ------------------------------------------------------------------

    def complete_recheck(
        self,
        state: PatientScheduleState,
        performer: str,
        now: datetime.datetime,
    ) -> tuple[bool, str]:
        """
        Mark a re-measurement as completed by performer.

        Returns (accepted, reason).
        Not all performers can close all bands (per trust config).
        """
        trust_cfg = self._trust_cfg(performer)
        band = state.current_band

        can_close = trust_cfg.get(f"can_close_{band}", False)
        if not can_close:
            return False, (
                f"performer '{performer}' cannot close a '{band}' recheck "
                f"(trust level: {trust_cfg.get('trust', 'unknown')})"
            )

        state.last_remeasure_at = now
        state.missed_remeasures = 0
        return True, "recheck_accepted"

    def record_missed_recheck(
        self,
        state: PatientScheduleState,
    ) -> None:
        """Increment the consecutive missed recheck counter."""
        state.missed_remeasures += 1

    # ------------------------------------------------------------------
    # Stale-reading triggered re-measurement
    # ------------------------------------------------------------------

    def check_stale_and_raise(
        self,
        state: PatientScheduleState,
        reading_age_minutes: float,
        now: datetime.datetime,
    ) -> list[str]:
        """
        If a reading is stale (> 2× cadence), raise a re-measurement task
        ahead of the fixed timer.
        """
        band = state.current_band
        cfg = self._band_cfg(band)
        remeasure_s = cfg.get("remeasure_interval_s", 1800)
        remeasure_min = remeasure_s / 60.0

        discount_mult = self._freshness["discount_multiplier"]
        missing_mult = self._freshness["missing_multiplier"]

        if reading_age_minutes > remeasure_min * missing_mult:
            return ["reading_too_stale:treat_as_missing", "remeasure_due:stale_trigger"]
        elif reading_age_minutes > remeasure_min * discount_mult:
            return ["reading_stale:confidence_discounted", "remeasure_due:stale_trigger"]
        return []
