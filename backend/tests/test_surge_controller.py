"""
backend/tests/test_surge_controller.py

Tests for the surge controller forbidden-action guards and detection.
"""

import datetime
import pytest

from triage.surge_controller import SurgeController, SurgeState, SurgeViolation

CTRL = SurgeController()
NOW = datetime.datetime(2026, 8, 22, 14, 0, tzinfo=datetime.timezone.utc)


def test_raise_cost_ratio_during_surge_raises_violation():
    with pytest.raises(SurgeViolation):
        CTRL.guard_raise_cost_ratio(proposed_R=3.0, current_R=2.0)


def test_lower_cost_ratio_is_allowed():
    # Lowering R is always allowed — it's more conservative
    CTRL.guard_raise_cost_ratio(proposed_R=1.5, current_R=2.0)  # no exception


def test_resolve_abstention_by_guessing_raises_violation():
    with pytest.raises(SurgeViolation):
        CTRL.guard_abstention_guess(is_abstained=True, is_guessing=True)


def test_resolve_non_abstention_is_fine():
    # Not abstained — no violation
    CTRL.guard_abstention_guess(is_abstained=False, is_guessing=True)  # no exception


def test_deescalate_for_capacity_raises_violation():
    with pytest.raises(SurgeViolation):
        CTRL.guard_deescalate_for_capacity(reason="free_capacity")


def test_deescalate_clinical_reason_is_allowed():
    # Clinical reason — not a capacity reason
    CTRL.guard_deescalate_for_capacity(reason="clinical_gestalt")  # no exception


def test_surge_entry_logged():
    state = SurgeState()
    # Simulate 25 arrivals in a 20-minute window (>> 3× normal rate of 8/hr)
    for i in range(25):
        now_offset = NOW + datetime.timedelta(seconds=i * 30)
        state = CTRL.record_arrival(state, now_offset)

    # Should be in surge
    assert state.in_surge is True
    assert len(state.log) >= 1
    assert state.log[-1].mode == "entered"


def test_surge_policy_red_never_stretches():
    state = SurgeState(in_surge=True)
    policy = CTRL.current_policy(state)
    # Red cadence must NOT be stretched
    assert policy.get("red_remeasure_s", 300) <= 300, (
        "Red re-measurement cadence must never stretch under surge"
    )
