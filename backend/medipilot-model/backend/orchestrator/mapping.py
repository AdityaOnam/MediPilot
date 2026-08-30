"""
Translation tables between backend snake_case domain and frontend camelCase contract.
"""

from __future__ import annotations
from typing import Optional


# Band: backend lowercase → frontend uppercase
def band_to_fe(band: str | None) -> str | None:
    if band is None:
        return None
    return band.upper()


def band_to_be(band: str | None) -> str | None:
    if band is None:
        return None
    return band.lower()


# Confidence float → frontend enum
def confidence_label(conf: float) -> str:
    if conf >= 0.8:
        return "high"
    if conf >= 0.6:
        return "moderate"
    return "low"


# Reliability discount keys: backend underscore → frontend kebab
_DISCOUNT_MAP = {
    "geriatric_stratum": "geriatric-stratum",
    "communication_barrier": "communication-barrier",
    "health_literacy_signal": "health-literacy",
    "stoic_presentation": "stoic-flag",
    "non_assisted_arrival": "non-assisted",
    "analgesia_given": "analgesia-given",
}


def discount_to_fe(backend_key: str) -> str:
    return _DISCOUNT_MAP.get(backend_key, backend_key)


def discounts_to_fe(backend_list: list[str]) -> list[dict]:
    return [
        {"key": discount_to_fe(k), "appliesTo": "reassuring-only"}
        for k in backend_list
    ]


# Recheck performer: frontend key → backend YAML key
_PERFORMER_MAP = {
    "station": "recheck_station",
    "nurse": "nurse_attendant",
    "family": "accompanying_family",
    "patient": "patient_self_service",
}


def performer_to_be(fe_key: str) -> str:
    return _PERFORMER_MAP.get(fe_key, fe_key)


# Vital code: frontend uppercase → backend snake_case
_VITAL_CODE_MAP = {
    "HR": "hr",
    "RR": "rr",
    "SBP": "bp_sys",
    "DBP": "bp_dia",
    "SPO2": "spo2",
    "TEMP": "temp_c",
    "GCS": "gcs",
    "PAIN": "pain_score",
}

_VITAL_CODE_MAP_REV = {v: k for k, v in _VITAL_CODE_MAP.items()}


def vital_code_to_be(fe_code: str) -> str:
    return _VITAL_CODE_MAP.get(fe_code, fe_code.lower())


def vital_code_to_fe(be_code: str) -> str:
    return _VITAL_CODE_MAP_REV.get(be_code, be_code.upper())


# Vital units for frontend display
_VITAL_UNITS = {
    "HR": "bpm",
    "RR": "/min",
    "SBP": "mmHg",
    "DBP": "mmHg",
    "SPO2": "%",
    "TEMP": "°C",
    "GCS": "/15",
    "PAIN": "/10",
}


def vital_unit(fe_code: str) -> str:
    return _VITAL_UNITS.get(fe_code, "")


# Abstention reason: backend reason string → frontend enum
def abstention_reason(confidence_reason: str | None) -> str | None:
    if not confidence_reason:
        return None
    cr = confidence_reason.lower()
    if "out_of_distribution" in cr:
        return "OUT_OF_DISTRIBUTION"
    if "all_vitals_missing" in cr:
        return "MISSING_CRITICAL_FIELDS"
    if "conformal" in cr or "spans_both" in cr:
        return "CONFORMAL_SET_TOO_WIDE"
    return "CONFORMAL_SET_TOO_WIDE"


# confidenceReducedBy: parse confidence_reason string → frontend union items
def parse_confidence_reduced_by(confidence_reason: str | None) -> list[str]:
    if not confidence_reason:
        return []
    result = []
    cr = confidence_reason.lower()
    if "inferred_age_stratum" in cr:
        result.append("inferred-age")
    if "stale_reading" in cr:
        result.append("stale-reading")
    if "out_of_distribution" in cr or "ood" in cr:
        result.append("ood-flag")
    if "reliability" in cr:
        result.append("reliability-discount")
    return result


# Override direction normalisation
def direction_to_fe(direction: str) -> str:
    if direction == "deescalation":
        return "de-escalation"
    return direction
