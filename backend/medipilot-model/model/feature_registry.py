"""
medipilot-model/model/feature_registry.py

Loader and enforcement for config/feature_registry.yaml.

This is the mechanical half of the whitepaper's leakage claim. The registry
alone is documentation; `assert_features_permitted()` is what makes including a
prohibited feature impossible rather than merely discouraged.

Two design rules, both deliberate:

  1. FAIL CLOSED. An unregistered feature name is treated as PROHIBITED, not as
     SAFE. Adding a generator field without classifying it breaks the build,
     which is how drift gets caught instead of silently shipping.

  2. The guard is UNCONDITIONAL. It does not consult config to decide whether to
     run — config classifies fields, it never decides whether enforcement
     happens. (Same principle as FIX_PLAN F4, where surge guards gated on config
     membership could be silently disabled by editing YAML.)
"""

from __future__ import annotations

import hashlib
import pathlib
import re
from typing import Iterable, Optional

import yaml


_CONFIG_PATH = pathlib.Path(__file__).parent.parent / "config" / "feature_registry.yaml"

SAFE = "SAFE"
CONDITIONAL = "CONDITIONAL"
PROHIBITED = "PROHIBITED"

# Feature columns are emitted per-vital as "<vital>_<suffix>". The registry
# classifies the suffix family once rather than 7x.
_VITALS = ("hr", "rr", "bp_sys", "spo2", "temp_c", "gcs", "pain_score")
_PER_VITAL_SUFFIXES = {
    "value": "vital_value",
    "z_stratum": "vital_z_stratum",
    "age_minutes": "vital_age_minutes",
    "slope_per_hour": "vital_slope_per_hour",
    "delta_30min": "vital_delta_30min",
    "n_readings": "vital_n_readings",
}


class LeakageViolation(Exception):
    """
    Raised when a PROHIBITED (or unregistered) field is offered as a model
    input feature. This is a safety error, not a validation warning.
    """


class FeatureRegistry:
    def __init__(self, config_path: pathlib.Path = _CONFIG_PATH):
        self._path = config_path
        raw = config_path.read_bytes()
        self._sha256 = hashlib.sha256(raw).hexdigest()
        cfg = yaml.safe_load(raw.decode("utf-8")) or {}
        self._registry: dict[str, dict] = cfg.get("registry", {})

    @property
    def sha256(self) -> str:
        """Hashed into the artifact manifest so registry drift is detectable."""
        return self._sha256

    def _canonical_name(self, feature: str) -> str:
        """Map a concrete column (e.g. 'hr_slope_per_hour') to its registry key."""
        if feature in self._registry:
            return feature
        for v in _VITALS:
            if feature.startswith(v + "_"):
                suffix = feature[len(v) + 1:]
                if suffix in _PER_VITAL_SUFFIXES:
                    return _PER_VITAL_SUFFIXES[suffix]
        # one-hot stratum columns
        if re.fullmatch(r"stratum_is_[a-z]+", feature):
            return "stratum"
        if feature == "stratum_ord":
            return "stratum"
        return feature

    def leakage_class(self, feature: str) -> str:
        """Class for a feature. Unregistered -> PROHIBITED (fail closed)."""
        entry = self._registry.get(self._canonical_name(feature))
        if entry is None:
            return PROHIBITED
        return str(entry.get("leakage_class", PROHIBITED)).upper()

    def permitted_use(self, feature: str) -> list[str]:
        entry = self._registry.get(self._canonical_name(feature)) or {}
        return list(entry.get("permitted_use", []))

    def is_registered(self, feature: str) -> bool:
        return self._canonical_name(feature) in self._registry

    def assert_features_permitted(self, features: Iterable[str]) -> None:
        """
        Raise LeakageViolation if any name is not SAFE-for-input.

        Called from model/features.py at first use against the canonical
        FEATURE_NAMES, so it is not possible to build a feature matrix that
        contains a prohibited column.
        """
        offenders: list[tuple[str, str, str]] = []
        for f in features:
            cls = self.leakage_class(f)
            if cls == SAFE and "input_features" in self.permitted_use(f):
                continue
            reason = (
                "not registered (fail-closed default is PROHIBITED)"
                if not self.is_registered(f)
                else f"leakage_class={cls}, permitted_use={self.permitted_use(f)}"
            )
            offenders.append((f, cls, reason))

        if offenders:
            lines = "\n".join(f"  - {f}: {reason}" for f, _cls, reason in offenders)
            raise LeakageViolation(
                "LeakageViolation: the following columns may not be used as model "
                f"input features:\n{lines}\n"
                "Either remove them from the feature set, or classify them SAFE "
                "with permitted_use including 'input_features' in "
                "config/feature_registry.yaml — but only if they are genuinely "
                "observable at scoring time."
            )

    def prohibited_names(self) -> set[str]:
        return {
            k for k, v in self._registry.items()
            if str(v.get("leakage_class", PROHIBITED)).upper() == PROHIBITED
        }


_registry: Optional[FeatureRegistry] = None


def get_registry() -> FeatureRegistry:
    global _registry
    if _registry is None:
        _registry = FeatureRegistry()
    return _registry


def assert_features_permitted(features: Iterable[str]) -> None:
    get_registry().assert_features_permitted(features)
