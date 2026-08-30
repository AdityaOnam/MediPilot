"""
backend/tests/test_band_engine.py

Tests for the band engine's asymmetric autonomy enforcement and SpO2 guard.
"""

import datetime
import pytest

from triage.band_engine import assign_band, AsymmetricAutonomyViolation
from rules.spo2_bias_guard import SpO2AloneDeescalationError

NOW = datetime.datetime(2026, 8, 22, 12, 0, tzinfo=datetime.timezone.utc)


def test_escalation_is_autonomous():
    result = assign_band("P1", "red", "yellow", last_human_action=None, now=NOW)
    assert result.direction == "escalation"
    assert result.autonomous is True
    assert result.new_band == "red"


def test_autonomous_deescalation_raises_violation():
    with pytest.raises(AsymmetricAutonomyViolation):
        assign_band("P1", "green", "yellow", last_human_action=None, now=NOW)


def test_human_deescalation_allowed():
    result = assign_band(
        "P1", "green", "yellow",
        last_human_action="override-123",
        spo2_value=None,
        now=NOW,
    )
    assert result.direction == "deescalation"
    assert result.autonomous is False


def test_unchanged_is_allowed():
    result = assign_band("P1", "yellow", "yellow", last_human_action=None, now=NOW)
    assert result.direction == "unchanged"
    assert result.changed is False


def test_initial_assignment_is_allowed():
    result = assign_band("P1", "yellow", None, last_human_action=None, now=NOW)
    assert result.direction == "initial"
    assert result.new_band == "yellow"


def test_spo2_alone_blocks_human_deescalation():
    """Even with a human action, SpO2-alone de-escalation is blocked."""
    with pytest.raises(SpO2AloneDeescalationError):
        assign_band(
            "P1", "green", "yellow",
            last_human_action="override-456",
            spo2_value=96.0,
            spo2_bias_risk=True,
            other_vitals={"hr": 108, "rr": 24},   # elevated — not corroborating
            now=NOW,
        )


def test_spo2_with_corroborating_vitals_allows_deescalation():
    """SpO2 + multiple corroborating normal vitals allows human-initiated deescalation."""
    result = assign_band(
        "P1", "green", "yellow",
        last_human_action="override-789",
        spo2_value=97.0,
        spo2_bias_risk=False,
        other_vitals={"hr": 72, "rr": 15, "bp_sys": 118},  # all normal
        now=NOW,
    )
    assert result.direction == "deescalation"
