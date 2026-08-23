"""
medipilot-model/model/reliability.py

Asymmetric reliability weighting of self-report.

From the brief:
  "Reliability weighting reduces the evidential weight of a REASSURING answer.
   It must NEVER reduce the weight of an alarming one."

In model terms:
  - Reassuring answer + discount → widen the uncertainty / conformal set
    → pushes toward abstention, not toward Green
  - Alarming answer + any discount → NO change (full evidential weight kept)

Every applied discount is named in the output (reliability_discounts_applied[])
so a clinician can see and reject the reasoning.

Factors consumed as flags from Track A (or set by clinician):
  - communication_barrier
  - health_literacy_signal
  - stoic_presentation      (clinician-set only — never inferred)
  - non_assisted_arrival
  - analgesia_given
  - geriatric_stratum       (set automatically based on resolved stratum — NOT from demographics)

Note: age enters through the clinical stratum, not as a direct demographic input.
"For age >= 60, discount self-report" is explicitly WRONG — age enters as stratum.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


# Discount magnitudes — how much each factor widens the uncertainty
# 0.0 = no effect, 1.0 = maximum uncertainty inflation
DISCOUNT_MAGNITUDES: dict[str, float] = {
    "geriatric_stratum":       0.35,   # atypical presentation well documented
    "communication_barrier":   0.30,   # interaction not in patient's first language
    "health_literacy_signal":  0.25,   # confusion about terms in the interaction
    "stoic_presentation":      0.40,   # clinician-set flag only
    "non_assisted_arrival":    0.20,   # nobody to corroborate history
    "analgesia_given":         0.45,   # masks pain score outright
}


@dataclass
class ReliabilityResult:
    discounts_applied: list[str]
    combined_discount: float       # [0, 1] — how much to widen uncertainty
    is_reassuring_context: bool    # was the answer reassuring before discount?
    uncertainty_inflation: float   # amount to add to conformal width


def compute_reliability_discount(
    flags: dict[str, bool],
    stratum: str,
    is_reassuring_answer: bool,
) -> ReliabilityResult:
    """
    Compute the reliability discount given the active flags and stratum.

    ASYMMETRIC: discount is only applied when the answer is reassuring.
    If is_reassuring_answer is False (patient reports alarm), discount = 0.

    Args:
        flags: dict of reliability flag names → bool (True = flag is set)
        stratum: resolved stratum string (e.g. "geriatric")
        is_reassuring_answer: True if the current self-report is reassuring
    """
    # Automatically set geriatric_stratum flag from stratum — NOT from demographics
    effective_flags = dict(flags)
    if stratum == "geriatric":
        effective_flags["geriatric_stratum"] = True

    applied = []
    combined = 0.0

    for flag_name, magnitude in DISCOUNT_MAGNITUDES.items():
        if effective_flags.get(flag_name, False):
            applied.append(flag_name)
            # Combine discounts sub-additively (avoid over-discounting)
            combined = combined + magnitude * (1 - combined)

    # ASYMMETRIC: if the answer is alarming, zero out the discount
    if not is_reassuring_answer:
        # Discount not applied — alarming answers keep full weight
        return ReliabilityResult(
            discounts_applied=[],       # empty — no discount was applied
            combined_discount=0.0,
            is_reassuring_context=False,
            uncertainty_inflation=0.0,
        )

    # Reassuring answer — apply discount as uncertainty inflation
    # Uncertainty inflation: how much wider the conformal set gets
    # Combined discount of 0.5 → 0.25 inflation (mapped to [0, 0.4])
    uncertainty_inflation = combined * 0.4

    return ReliabilityResult(
        discounts_applied=applied,
        combined_discount=round(combined, 4),
        is_reassuring_context=True,
        uncertainty_inflation=round(uncertainty_inflation, 4),
    )
