"""
M09 interface — reliability signal collection.

Scope, deliberately narrow for this pass: this module REPORTS the
observable/contextual signals defined in round2-implementation-plan.html
§07. It does not compute or apply any evidential-weight discount to
self-report — that calculation (widening a conformal set, discounting the
negative predictive value of a reassuring answer) belongs to the
downstream M09/M12 modules, out of scope here.

Signals reported: geriatric_stratum, communication_barrier,
health_literacy_signal, stoic_presentation, non_assisted_arrival,
analgesia_given.
"""

from __future__ import annotations

from typing import Optional

from intake.age_stratification import AgeResolution
from intake.models import AgeStratum, ReliabilitySignals, TriState
from intake.question_tree import QuestionTreeSession
from intake.state_machine import IntakeSession


def collect_reliability_signals(
    session: IntakeSession,
    tree_session: Optional[QuestionTreeSession],
    age_resolution: AgeResolution,
) -> ReliabilitySignals:
    """
    Merge the reliability-relevant signals gathered across the intake
    branch (M03: non_assisted_arrival) and the question tree (M04:
    communication_barrier, health_literacy_signal, analgesia_given) with
    the resolved age stratum (M08: geriatric_stratum) into one
    ReliabilitySignals record. Every field is a plain observation, not a
    weight or a discount.
    """
    signals = tree_session.reliability_signals if tree_session else ReliabilitySignals()

    signals.geriatric_stratum = age_resolution.stratum == AgeStratum.GERIATRIC
    signals.non_assisted_arrival = session.assisted == TriState.FALSE

    return signals


def set_stoic_presentation_flag(signals: ReliabilitySignals, value: bool) -> ReliabilitySignals:
    """
    The stoic-presentation flag is clinician-set, never model-guessed
    (round2-implementation-plan.html §07). This is deliberately the only
    place in the codebase that sets it — there is no automatic/inferred
    path to this field anywhere else.
    """
    signals.stoic_presentation = bool(value)
    return signals
