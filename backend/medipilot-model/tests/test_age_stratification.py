"""
medipilot-model/tests/test_age_stratification.py

Tests for age stratum resolution and the two-mechanism separation.
"""

import pytest
from model.age_stratum import resolve_stratum


def test_neonate_stratum():
    r = resolve_stratum(age_days=14, age_known=True)
    assert r.stratum == "neonate"
    assert not r.inferred

def test_infant_stratum():
    r = resolve_stratum(age_days=180, age_known=True)
    assert r.stratum == "infant"

def test_child_stratum():
    r = resolve_stratum(age_days=365 * 5, age_known=True)
    assert r.stratum == "child"

def test_adolescent_stratum():
    r = resolve_stratum(age_days=365 * 15, age_known=True)
    assert r.stratum == "adolescent"

def test_adult_stratum():
    r = resolve_stratum(age_days=365 * 40, age_known=True)
    assert r.stratum == "adult"

def test_geriatric_stratum():
    r = resolve_stratum(age_days=365 * 75, age_known=True)
    assert r.stratum == "geriatric"
    assert r.calibration_weight > 1.0  # geriatric has elevated calibration weight

def test_geriatric_lower_reassurance_decay():
    """Geriatric must have lower reassurance_decay than adult."""
    adult = resolve_stratum(age_days=365 * 40, age_known=True)
    geriatric = resolve_stratum(age_days=365 * 75, age_known=True)
    assert geriatric.reassurance_decay < adult.reassurance_decay, (
        "Geriatric stratum must offer less reassurance from normal vitals than adult"
    )

def test_unknown_age_is_inferred():
    r = resolve_stratum(age_days=None, age_known=False)
    assert r.inferred is True
    assert r.stratum is not None   # widest-safety fallback assigned

def test_known_age_is_not_inferred():
    r = resolve_stratum(age_days=365 * 40, age_known=True)
    assert r.inferred is False

def test_age_unknown_flag_overrides_known_days():
    """Even if age_days is provided, age_known=False must mark as inferred."""
    r = resolve_stratum(age_days=365 * 40, age_known=False)
    assert r.inferred is True
