"""
medipilot-model/tests/test_reliability_weighting.py

Tests for asymmetric reliability weighting.
Key property: discount only applies to reassuring answers, never alarming ones.
"""

import pytest
from model.reliability import compute_reliability_discount


def test_alarming_answer_gets_zero_discount():
    """Alarming answer must NEVER be discounted, even under high-discount flags."""
    result = compute_reliability_discount(
        flags={
            "communication_barrier": True,
            "stoic_presentation": True,
            "analgesia_given": True,
        },
        stratum="adult",
        is_reassuring_answer=False,   # ALARMING
    )
    assert result.combined_discount == 0.0, (
        "Alarming answers must never be discounted"
    )
    assert result.discounts_applied == [], (
        "No discounts should be recorded for alarming answers"
    )
    assert result.uncertainty_inflation == 0.0


def test_reassuring_answer_gets_discount_under_flags():
    """Reassuring answer with active flags should receive discount."""
    result = compute_reliability_discount(
        flags={"communication_barrier": True},
        stratum="adult",
        is_reassuring_answer=True,
    )
    assert result.combined_discount > 0.0
    assert "communication_barrier" in result.discounts_applied
    assert result.uncertainty_inflation > 0.0


def test_geriatric_stratum_auto_flag():
    """Geriatric stratum should automatically apply the atypical-presentation discount
    on reassuring answers without needing explicit flag."""
    result = compute_reliability_discount(
        flags={},
        stratum="geriatric",
        is_reassuring_answer=True,
    )
    assert "geriatric_stratum" in result.discounts_applied
    assert result.combined_discount > 0.0


def test_geriatric_stratum_alarming_no_discount():
    """Geriatric stratum auto-flag must NOT apply to alarming answers."""
    result = compute_reliability_discount(
        flags={},
        stratum="geriatric",
        is_reassuring_answer=False,  # alarming — no discount even with geriatric stratum
    )
    assert result.combined_discount == 0.0
    assert result.discounts_applied == []


def test_multiple_flags_subadditive():
    """Multiple flags combine sub-additively — total discount < sum of individual discounts."""
    result_all = compute_reliability_discount(
        flags={
            "communication_barrier": True,
            "stoic_presentation": True,
            "analgesia_given": True,
        },
        stratum="adult",
        is_reassuring_answer=True,
    )
    # Each individually: 0.30, 0.40, 0.45
    # Naive sum would be 1.15 — capped is not the test; sub-additive is
    assert result_all.combined_discount < 0.85, (
        "Multiple discounts must combine sub-additively"
    )
    assert result_all.combined_discount <= 1.0


def test_no_flags_no_discount():
    """With no flags and adult stratum, no discount even for reassuring answer."""
    result = compute_reliability_discount(
        flags={},
        stratum="adult",
        is_reassuring_answer=True,
    )
    assert result.combined_discount == 0.0
    assert result.discounts_applied == []
    assert result.uncertainty_inflation == 0.0
