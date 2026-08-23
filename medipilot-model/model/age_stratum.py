"""
medipilot-model/model/age_stratum.py

Age stratum resolver.
Implements Invariant 3: age is NEVER assumed.
  - If age is known → resolve to the correct stratum.
  - If age is unknown → use widest-safety stratum from config,
    mark inferred=True, and NEVER silently resolve.

An inferred stratum is a standing reason for reduced confidence (used by
risk_model.py and conformal.py).
"""

from __future__ import annotations

import pathlib
from dataclasses import dataclass
from typing import Optional

import yaml


_CONFIG_PATH = pathlib.Path(__file__).parent.parent / "config" / "age_strata.yaml"


@dataclass(frozen=True)
class StratumResult:
    stratum: str            # e.g. "adult", "geriatric"
    label: str              # human-readable label
    inferred: bool          # True if age was unknown → widest-safety estimate used
    age_days_estimate: Optional[int]  # None if truly unknown
    calibration_weight: float
    reassurance_decay: float


class AgeStratumResolver:
    """
    Resolves age in days to a stratum.
    Config is loaded once and cached.
    """

    def __init__(self, config_path: pathlib.Path = _CONFIG_PATH):
        with open(config_path, encoding="utf-8") as f:
            cfg = yaml.safe_load(f)
        self._strata = cfg["strata"]
        self._fallback_key = cfg["unknown_age_fallback"]

    def resolve(
        self,
        age_days: Optional[int],
        age_known: bool = True,
    ) -> StratumResult:
        """
        Resolve age to a stratum.

        Args:
            age_days: age in days. None means completely unknown.
            age_known: False means age was estimated / uncertain.

        Returns:
            StratumResult with inferred=True if age was not definitively known.
        """
        if age_days is None or not age_known:
            # Use widest-safety fallback; never silently assign a specific stratum
            fallback = self._strata[self._fallback_key]
            return StratumResult(
                stratum=self._fallback_key,
                label=fallback["label"],
                inferred=True,
                age_days_estimate=age_days,
                calibration_weight=fallback["calibration_weight"],
                reassurance_decay=fallback["reassurance_decay"],
            )

        # Find matching stratum
        for key, s in self._strata.items():
            lo = s["age_min_days"]
            hi = s.get("age_max_days")  # null = no upper bound
            in_range = age_days >= lo and (hi is None or age_days <= hi)
            if in_range:
                return StratumResult(
                    stratum=key,
                    label=s["label"],
                    inferred=False,
                    age_days_estimate=age_days,
                    calibration_weight=s["calibration_weight"],
                    reassurance_decay=s["reassurance_decay"],
                )

        # Age out of all ranges → use widest-safety fallback, mark inferred
        fallback = self._strata[self._fallback_key]
        return StratumResult(
            stratum=self._fallback_key,
            label=fallback["label"],
            inferred=True,
            age_days_estimate=age_days,
            calibration_weight=fallback["calibration_weight"],
            reassurance_decay=fallback["reassurance_decay"],
        )


# Module-level singleton
_resolver: Optional[AgeStratumResolver] = None


def get_resolver() -> AgeStratumResolver:
    global _resolver
    if _resolver is None:
        _resolver = AgeStratumResolver()
    return _resolver


def resolve_stratum(age_days: Optional[int], age_known: bool = True) -> StratumResult:
    """Convenience wrapper around the singleton resolver."""
    return get_resolver().resolve(age_days, age_known)
