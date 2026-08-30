"""
backend/rules/red_flag_engine.py

Deterministic red-flag rule layer. Fires INDEPENDENTLY of the risk model.
Maps extracted observations (from Track A's structured narrative) directly to Red.

This table is EDITABLE CONFIG — in a real deployment it would be clinically
signed off. Loaded from config/red_flags.yaml.

Key property (Invariant 1):
  A red-flag Red is NOT overridable downward except by a clinician with a reason.
  No subsequent model output may lower it autonomously.
"""

from __future__ import annotations

import pathlib
from dataclasses import dataclass
from typing import Optional

import yaml


_CONFIG_PATH = pathlib.Path(__file__).parent.parent / "config" / "red_flags.yaml"


@dataclass
class RedFlagMatch:
    flag_id: str
    observation: str
    description: str
    band: str = "red"
    override_allowed: str = "clinician_only"


class RedFlagEngine:
    """
    Deterministic rule engine that maps extracted observations → band assignments.
    Loaded from config — not hard-coded.
    """

    def __init__(self, config_path: pathlib.Path = _CONFIG_PATH):
        with open(config_path, encoding="utf-8") as f:
            cfg = yaml.safe_load(f)
        self._rules: dict[str, dict] = {
            r["observation"]: r for r in cfg["red_flags"]
        }

    def check(self, observations: list[str]) -> Optional[RedFlagMatch]:
        """
        Check a list of observations against the red-flag table.

        Returns the first RedFlagMatch if any observation triggers a red flag,
        otherwise None.

        The engine checks ALL observations and returns the highest-severity one.
        Currently all red flags are 'red', so this returns the first match.
        """
        for obs in observations:
            if obs in self._rules:
                r = self._rules[obs]
                return RedFlagMatch(
                    flag_id=r["id"],
                    observation=obs,
                    description=r["description"],
                    band=r["band"],
                    override_allowed=r.get("override_allowed", "clinician_only"),
                )
        return None

    def all_rules(self) -> list[dict]:
        """Return all rules — used for display/debugging."""
        return list(self._rules.values())
