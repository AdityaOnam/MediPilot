"""
backend/triage/surge_controller.py

Surge detection and stretch policy.

Detects load (3× normal arrival rate over rolling window) and applies
stretch policy: Yellow 30→45 min, Green 60→90 min; Red NEVER stretches.

Forbidden actions enforced in code (not just policy):
  1. Raising cost ratio R to reduce alarm volume  → SurgeViolation
  2. Resolving abstention by guessing             → SurgeViolation
  3. De-escalating a patient to free capacity     → SurgeViolation

Every surge entry/exit is logged with trigger, timestamp, and active policy.
"""

from __future__ import annotations

import datetime
import pathlib
from collections import deque
from dataclasses import dataclass, field
from typing import Optional

import yaml


_CONFIG_PATH = pathlib.Path(__file__).parent.parent / "config" / "surge_policy.yaml"


class SurgeViolation(Exception):
    """
    Raised when a forbidden action is attempted during surge mode.
    Forbidden actions: raise R, guess on abstention, de-escalate for capacity.
    """
    pass


@dataclass
class SurgeLogEntry:
    timestamp_utc: str
    trigger_metric: float       # arrival rate that triggered
    mode: str                   # "entered" | "exited"
    active_policy_snapshot: dict

    def as_dict(self) -> dict:
        return {
            "timestamp_utc": self.timestamp_utc,
            "trigger_metric": self.trigger_metric,
            "mode": self.mode,
            "active_policy_snapshot": self.active_policy_snapshot,
        }


@dataclass
class SurgeState:
    in_surge: bool = False
    surge_started_at: Optional[datetime.datetime] = None
    current_arrival_rate: float = 0.0
    log: list[SurgeLogEntry] = field(default_factory=list)


class SurgeController:
    """
    Detects surge conditions and applies stretch policy.
    Enforces forbidden actions in code.
    """

    #: The three guards below are unconditional in code (F4) — this set is
    #: kept only as documentation surfaced to operators/audits, and startup
    #: verifies the config hasn't drifted from what's actually enforced.
    _REQUIRED_FORBIDDEN_ACTIONS = frozenset({
        "raise_cost_ratio_R",
        "resolve_abstention_by_guessing",
        "deescalate_to_free_capacity",
    })

    def __init__(self, config_path: pathlib.Path = _CONFIG_PATH):
        with open(config_path, encoding="utf-8") as f:
            cfg = yaml.safe_load(f)
        self._cfg = cfg
        self._detection = cfg["detection"]
        self._stretch = cfg["stretch_policy"]
        self._forbidden = set(cfg["forbidden_actions"])

        missing = self._REQUIRED_FORBIDDEN_ACTIONS - self._forbidden
        if missing:
            raise ValueError(
                f"surge_policy.yaml is missing documented forbidden_actions "
                f"entries: {sorted(missing)}. These guards run unconditionally "
                f"in code regardless of this list, but the list must stay in "
                f"sync as documentation for operators and audits — fix the "
                f"config rather than removing the check."
            )

        # Rolling arrival tracking: timestamps of recent arrivals
        self._arrivals: deque[datetime.datetime] = deque()

    @property
    def state(self) -> SurgeState:
        return self._state

    def _build_state(self) -> SurgeState:
        return SurgeState()

    # ------------------------------------------------------------------
    # Arrival tracking
    # ------------------------------------------------------------------

    def record_arrival(
        self,
        state: SurgeState,
        now: datetime.datetime,
    ) -> SurgeState:
        """Record a new patient arrival and update surge status."""
        window_min = self._detection["measurement_window_minutes"]
        cutoff = now - datetime.timedelta(minutes=window_min)

        # Add new arrival
        self._arrivals.append(now)

        # Prune old arrivals outside window
        while self._arrivals and self._arrivals[0] < cutoff:
            self._arrivals.popleft()

        # Compute rate per hour
        rate_per_hour = (len(self._arrivals) / window_min) * 60.0
        state.current_arrival_rate = round(rate_per_hour, 2)

        normal_rate = self._detection["normal_arrival_rate_per_hour"]
        surge_threshold = self._detection["surge_multiplier_threshold"]
        exit_threshold = self._detection["exit_threshold_multiplier"]

        if not state.in_surge and rate_per_hour >= normal_rate * surge_threshold:
            # Enter surge
            state.in_surge = True
            state.surge_started_at = now
            policy = self._active_policy(surge=True)
            entry = SurgeLogEntry(
                timestamp_utc=now.isoformat(),
                trigger_metric=round(rate_per_hour, 2),
                mode="entered",
                active_policy_snapshot=policy,
            )
            state.log.append(entry)

        elif state.in_surge and rate_per_hour < normal_rate * exit_threshold:
            # Exit surge
            state.in_surge = False
            policy = self._active_policy(surge=False)
            entry = SurgeLogEntry(
                timestamp_utc=now.isoformat(),
                trigger_metric=round(rate_per_hour, 2),
                mode="exited",
                active_policy_snapshot=policy,
            )
            state.log.append(entry)

        return state

    def _active_policy(self, surge: bool) -> dict:
        if not surge:
            return {"mode": "normal", "yellow_remeasure_s": 1800, "green_remeasure_s": 3600}
        return {
            "mode": "surge",
            "yellow_remeasure_s": 1800 + self._stretch["yellow_remeasure_stretch_s"],
            "green_remeasure_s": 3600 + self._stretch["green_remeasure_stretch_s"],
            "red_remeasure_s": 300,   # never stretches
        }

    def current_policy(self, state: SurgeState) -> dict:
        return self._active_policy(surge=state.in_surge)

    # ------------------------------------------------------------------
    # Forbidden action guards
    # ------------------------------------------------------------------

    def guard_raise_cost_ratio(self, proposed_R: float, current_R: float) -> None:
        """
        Guard: raising cost ratio R during surge is forbidden.
        R should only be adjusted deliberately by a clinical admin, never
        automatically during surge to reduce alarm volume.

        Unconditional — this does NOT check config membership. Config tunes
        thresholds; it does not decide whether a safety invariant is
        enforced. (F4: previously gated on `"raise_cost_ratio_R" in
        self._forbidden`, so deleting a line from surge_policy.yaml silently
        disabled this check with no test failing.)
        """
        if proposed_R > current_R:
            raise SurgeViolation(
                f"SurgeViolation: Attempt to raise cost ratio R from {current_R} to "
                f"{proposed_R} during surge. Forbidden action: 'raise_cost_ratio_R'. "
                "Cost ratio may only be lowered or kept during surge."
            )

    def guard_abstention_guess(self, is_abstained: bool, is_guessing: bool) -> None:
        """
        Guard: resolving an abstention by guessing is forbidden under any load.
        Abstentions always route to a human. Unconditional — see note on
        guard_raise_cost_ratio above.
        """
        if is_abstained and is_guessing:
            raise SurgeViolation(
                "SurgeViolation: Attempt to resolve an abstention by guessing. "
                "Forbidden action: 'resolve_abstention_by_guessing'. "
                "Abstentions always route to a human reviewer."
            )

    def guard_deescalate_for_capacity(
        self,
        reason: str,
    ) -> None:
        """
        Guard: de-escalating a patient to free capacity is forbidden.
        Band lowering must only happen via human override with a clinical reason,
        never for queue management. Unconditional — see note on
        guard_raise_cost_ratio above.
        """
        capacity_reasons = {
            "capacity", "queue_full", "free_capacity", "discharge_pressure",
            "surge_capacity", "reduce_queue",
        }
        if any(r in reason.lower() for r in capacity_reasons):
            raise SurgeViolation(
                f"SurgeViolation: Attempt to de-escalate patient for capacity reason: '{reason}'. "
                "Forbidden action: 'deescalate_to_free_capacity'. "
                "Band lowering must be driven by clinical judgement, never queue pressure."
            )

    # ------------------------------------------------------------------
    # Alert ranking
    # ------------------------------------------------------------------

    def rank_alerts(
        self,
        patients: list[dict],  # [{"patient_id", "risk_score", "time_waiting_s"}]
    ) -> list[dict]:
        """
        Rank alerts by risk × time_waiting. Never suppress alerts under surge.
        """
        for p in patients:
            p["alert_rank"] = p.get("risk_score", 0) * (
                p.get("time_waiting_s", 0) / 60.0
            )
        return sorted(patients, key=lambda p: p["alert_rank"], reverse=True)
