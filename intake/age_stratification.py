"""
M08 — Age stratification.

Resolves an AgeInfo (collected by intake) into an age stratum. This is
intentionally a separate module from intake collection (M03/M04): the
intake layer only records what it observed about age; this module decides
what that means clinically.

Invariant 3 (round2-implementation-plan.html §04): no threshold, weight or
calibration is applied without a stratum resolved first. Where age is
unknown, the widest-safety configuration is used and the system says so —
it never silently assumes Adult.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from intake.models import AgeInfo, AgeStatus, AgeStratum

_NEONATE_MAX_DAYS = 28
_INFANT_MAX_DAYS = 365
_CHILD_MAX_DAYS = 12 * 365
_ADOLESCENT_MAX_DAYS = 18 * 365
_ADULT_MAX_DAYS = 65 * 365

_ALL_STRATA = list(AgeStratum)

# Coarse appearance hints -> plausible stratum range. Deliberately small and
# conservative: only used when no explicit/attendant/record age exists at
# all. This is NOT a demographic inference about the person — it narrows an
# otherwise-unknown age using what a clinician/attendant visually reported
# (e.g. "looks like an infant"), which the architecture explicitly permits
# ("estimates a coarse stratum from what is available").
_APPEARANCE_HINTS = {
    "infant": [AgeStratum.NEONATE, AgeStratum.INFANT],
    "child": [AgeStratum.INFANT, AgeStratum.CHILD],
    "adolescent": [AgeStratum.CHILD, AgeStratum.ADOLESCENT],
    "adult": [AgeStratum.ADOLESCENT, AgeStratum.ADULT],
    "elderly": [AgeStratum.ADULT, AgeStratum.GERIATRIC],
}


@dataclass
class AgeResolution:
    stratum: Optional[AgeStratum]  # None only when truly unresolved (widest-safety across all strata)
    status: AgeStatus
    inferred: bool
    confidence: float
    plausible_strata: list = field(default_factory=list)
    basis: str = ""


def _stratum_from_days(days: int) -> AgeStratum:
    if days < _NEONATE_MAX_DAYS:
        return AgeStratum.NEONATE
    if days < _INFANT_MAX_DAYS:
        return AgeStratum.INFANT
    if days < _CHILD_MAX_DAYS:
        return AgeStratum.CHILD
    if days < _ADOLESCENT_MAX_DAYS:
        return AgeStratum.ADOLESCENT
    if days < _ADULT_MAX_DAYS:
        return AgeStratum.ADULT
    return AgeStratum.GERIATRIC


def resolve_age_stratum(age_info: AgeInfo) -> AgeResolution:
    """
    Resolve an AgeStratum from AgeInfo. Never assumes Adult.

    - Known age (value_days present, status KNOWN): exact stratum, full confidence.
    - Inferred age (status INFERRED, e.g. an attendant's estimate expressed in
      days, or a coarse appearance hint): stratum or narrowed plausible range,
      reduced confidence, inferred=True.
    - Unknown age with no signal at all: stratum=None, plausible_strata=ALL,
      very low confidence — this is the "widest-safety configuration" the
      architecture calls for. Downstream modules (M10-M14) are responsible
      for actually merging thresholds across plausible_strata; this module's
      job ends at exposing that range honestly.
    """
    if age_info.status == AgeStatus.KNOWN and age_info.value_days is not None:
        stratum = _stratum_from_days(age_info.value_days)
        return AgeResolution(
            stratum=stratum,
            status=AgeStatus.KNOWN,
            inferred=False,
            confidence=1.0,
            plausible_strata=[stratum],
            basis=f"explicit age_days={age_info.value_days} (source={age_info.source.value})",
        )

    if age_info.value_days is not None:
        # A numeric estimate exists but was flagged as inferred/attendant-estimated.
        stratum = _stratum_from_days(age_info.value_days)
        return AgeResolution(
            stratum=stratum,
            status=AgeStatus.INFERRED,
            inferred=True,
            confidence=0.5,
            plausible_strata=[stratum],
            basis=f"inferred age_days={age_info.value_days} (source={age_info.source.value}); reduced confidence",
        )

    if age_info.appearance_hint and age_info.appearance_hint in _APPEARANCE_HINTS:
        plausible = _APPEARANCE_HINTS[age_info.appearance_hint]
        return AgeResolution(
            stratum=None,
            status=AgeStatus.INFERRED,
            inferred=True,
            confidence=0.25,
            plausible_strata=list(plausible),
            basis=f"no stated age; appearance hint '{age_info.appearance_hint}' narrows plausible strata",
        )

    # Truly unknown: no age, no attendant estimate, no appearance hint.
    # Widest-safety configuration: every stratum stays plausible.
    return AgeResolution(
        stratum=None,
        status=AgeStatus.UNKNOWN,
        inferred=False,
        confidence=0.1,
        plausible_strata=list(_ALL_STRATA),
        basis="no age information available; widest-safety configuration across all strata",
    )
