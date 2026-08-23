"""
medipilot-model/data/generator/conditions.py

Clinical condition archetypes with joint vital distributions per age stratum.
Vitals are NOT sampled independently — each condition defines a correlated
joint distribution so that the generated combinations are physiologically
plausible.
"""

from __future__ import annotations
import numpy as np
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class VitalDistribution:
    """
    Parameterises a single vital sign as a truncated normal distribution.
    mean, std: distribution parameters
    low, high: hard physiological clipping bounds
    """
    mean: float
    std: float
    low: float
    high: float

    def sample(self, rng: np.random.Generator) -> float:
        v = rng.normal(self.mean, self.std)
        return float(np.clip(v, self.low, self.high))


@dataclass
class ConditionVitals:
    """Per-stratum vital distributions for a clinical condition."""
    hr: VitalDistribution
    rr: VitalDistribution
    bp_sys: VitalDistribution
    spo2: VitalDistribution
    temp_c: VitalDistribution
    gcs: VitalDistribution          # Glasgow Coma Scale 3–15
    pain_score: VitalDistribution   # 0–10

    # Correlation structure: list of (vital_a, vital_b, direction)
    # direction: +1 means they move together, -1 means inversely
    correlations: list[tuple[str, str, float]] = field(default_factory=list)


@dataclass
class ClinicalCondition:
    """
    A clinical presentation archetype.
    vitals_by_stratum: maps stratum name → ConditionVitals
    If a stratum is missing, falls back to 'adult'.
    """
    condition_id: str
    label: str
    typical_band: str                   # red / yellow / green
    red_flag_observations: list[str]    # from red_flags.yaml keys
    vitals_by_stratum: dict[str, ConditionVitals]
    trajectory_shape: str               # compensating_then_decompensating / improving / stable_sudden
    notes: str = ""

    def vitals_for_stratum(self, stratum: str) -> ConditionVitals:
        return self.vitals_by_stratum.get(stratum, self.vitals_by_stratum["adult"])


# ---------------------------------------------------------------------------
# Condition definitions
# ---------------------------------------------------------------------------

def _make_conditions() -> dict[str, ClinicalCondition]:
    """Build all condition archetypes. Returns dict keyed by condition_id."""
    return {c.condition_id: c for c in [

        # ── C01: Sepsis ────────────────────────────────────────────────────
        ClinicalCondition(
            condition_id="C01",
            label="Sepsis / Severe infection",
            typical_band="red",
            red_flag_observations=["altered_consciousness"],
            trajectory_shape="compensating_then_decompensating",
            vitals_by_stratum={
                "adult": ConditionVitals(
                    hr=VitalDistribution(118, 18, 90, 160),
                    rr=VitalDistribution(24, 4, 18, 40),
                    bp_sys=VitalDistribution(95, 15, 60, 130),
                    spo2=VitalDistribution(94, 3, 80, 99),
                    temp_c=VitalDistribution(38.8, 0.8, 36.0, 41.0),
                    gcs=VitalDistribution(13, 2, 8, 15),
                    pain_score=VitalDistribution(6, 2, 2, 10),
                    correlations=[("hr", "rr", 0.7), ("bp_sys", "hr", -0.6)],
                ),
                "geriatric": ConditionVitals(
                    hr=VitalDistribution(95, 12, 60, 140),   # may not tachycardia
                    rr=VitalDistribution(22, 4, 14, 36),
                    bp_sys=VitalDistribution(100, 20, 60, 150),
                    spo2=VitalDistribution(93, 4, 80, 99),
                    temp_c=VitalDistribution(37.8, 1.0, 35.5, 40.0),  # may be afebrile
                    gcs=VitalDistribution(12, 3, 8, 15),
                    pain_score=VitalDistribution(4, 2, 0, 9),  # stoic/atypical
                    correlations=[("hr", "rr", 0.5), ("bp_sys", "hr", -0.4)],
                ),
                "child": ConditionVitals(
                    hr=VitalDistribution(140, 20, 100, 200),
                    rr=VitalDistribution(32, 6, 20, 60),
                    bp_sys=VitalDistribution(85, 15, 55, 120),
                    spo2=VitalDistribution(93, 4, 80, 99),
                    temp_c=VitalDistribution(39.2, 0.8, 37.5, 41.5),
                    gcs=VitalDistribution(13, 2, 8, 15),
                    pain_score=VitalDistribution(7, 2, 3, 10),
                    correlations=[("hr", "rr", 0.8), ("bp_sys", "hr", -0.7)],
                ),
                "infant": ConditionVitals(
                    hr=VitalDistribution(155, 20, 110, 200),
                    rr=VitalDistribution(48, 8, 30, 70),
                    bp_sys=VitalDistribution(75, 12, 50, 100),
                    spo2=VitalDistribution(92, 5, 78, 99),
                    temp_c=VitalDistribution(39.5, 0.7, 38.0, 41.5),
                    gcs=VitalDistribution(12, 2, 8, 15),
                    pain_score=VitalDistribution(8, 2, 4, 10),
                    correlations=[("hr", "rr", 0.85), ("bp_sys", "hr", -0.7)],
                ),
            },
        ),

        # ── C02: Acute coronary syndrome ──────────────────────────────────
        ClinicalCondition(
            condition_id="C02",
            label="Acute coronary syndrome (ACS)",
            typical_band="red",
            red_flag_observations=["chest_pain_with_sweating_radiation_breathlessness"],
            trajectory_shape="stable_sudden",
            vitals_by_stratum={
                "adult": ConditionVitals(
                    hr=VitalDistribution(88, 20, 40, 150),
                    rr=VitalDistribution(20, 4, 12, 36),
                    bp_sys=VitalDistribution(140, 30, 80, 200),
                    spo2=VitalDistribution(95, 3, 82, 99),
                    temp_c=VitalDistribution(37.0, 0.3, 36.2, 38.0),
                    gcs=VitalDistribution(15, 1, 12, 15),
                    pain_score=VitalDistribution(7, 2, 3, 10),
                    correlations=[("rr", "spo2", -0.5)],
                ),
                "geriatric": ConditionVitals(
                    hr=VitalDistribution(75, 15, 40, 120),
                    rr=VitalDistribution(18, 4, 12, 30),
                    bp_sys=VitalDistribution(145, 35, 80, 220),
                    spo2=VitalDistribution(94, 4, 80, 99),
                    temp_c=VitalDistribution(37.0, 0.3, 36.0, 38.0),
                    gcs=VitalDistribution(15, 1, 12, 15),
                    pain_score=VitalDistribution(4, 3, 0, 9),  # may present silently
                    correlations=[("rr", "spo2", -0.5)],
                ),
            },
        ),

        # ── C03: Stroke / TIA ─────────────────────────────────────────────
        ClinicalCondition(
            condition_id="C03",
            label="Stroke / TIA",
            typical_band="red",
            red_flag_observations=["sudden_onesided_weakness_facial_droop_speech_change",
                                   "altered_consciousness",
                                   "difficulty_speaking_full_sentences"],
            trajectory_shape="stable_sudden",
            vitals_by_stratum={
                "adult": ConditionVitals(
                    hr=VitalDistribution(82, 16, 50, 140),
                    rr=VitalDistribution(18, 4, 12, 30),
                    bp_sys=VitalDistribution(175, 30, 120, 260),
                    spo2=VitalDistribution(95, 4, 82, 99),
                    temp_c=VitalDistribution(37.1, 0.4, 36.2, 38.5),
                    gcs=VitalDistribution(11, 4, 3, 15),
                    pain_score=VitalDistribution(3, 3, 0, 8),
                    correlations=[("bp_sys", "gcs", -0.4)],
                ),
                "geriatric": ConditionVitals(
                    hr=VitalDistribution(78, 14, 50, 120),
                    rr=VitalDistribution(18, 4, 12, 28),
                    bp_sys=VitalDistribution(180, 35, 120, 280),
                    spo2=VitalDistribution(94, 4, 80, 99),
                    temp_c=VitalDistribution(37.2, 0.5, 36.0, 38.5),
                    gcs=VitalDistribution(10, 4, 3, 15),
                    pain_score=VitalDistribution(2, 2, 0, 7),
                    correlations=[("bp_sys", "gcs", -0.5)],
                ),
            },
        ),

        # ── C04: Paediatric febrile illness ───────────────────────────────
        ClinicalCondition(
            condition_id="C04",
            label="Paediatric febrile illness (serious)",
            typical_band="red",
            red_flag_observations=[],
            trajectory_shape="compensating_then_decompensating",
            vitals_by_stratum={
                "child": ConditionVitals(
                    hr=VitalDistribution(135, 18, 90, 200),
                    rr=VitalDistribution(30, 7, 18, 55),
                    bp_sys=VitalDistribution(92, 12, 65, 120),
                    spo2=VitalDistribution(95, 3, 86, 99),
                    temp_c=VitalDistribution(38.8, 0.5, 37.8, 41.0),
                    gcs=VitalDistribution(14, 2, 10, 15),
                    pain_score=VitalDistribution(6, 2, 2, 10),
                    correlations=[("hr", "temp_c", 0.7), ("rr", "temp_c", 0.6)],
                ),
                "infant": ConditionVitals(
                    hr=VitalDistribution(158, 20, 110, 210),
                    rr=VitalDistribution(50, 10, 30, 75),
                    bp_sys=VitalDistribution(70, 12, 45, 95),
                    spo2=VitalDistribution(94, 4, 82, 99),
                    temp_c=VitalDistribution(39.2, 0.6, 38.0, 41.5),
                    gcs=VitalDistribution(13, 2, 8, 15),
                    pain_score=VitalDistribution(8, 2, 4, 10),
                    correlations=[("hr", "temp_c", 0.8), ("rr", "temp_c", 0.75)],
                ),
                "adult": ConditionVitals(   # fallback, rarely used
                    hr=VitalDistribution(105, 15, 70, 150),
                    rr=VitalDistribution(22, 4, 14, 36),
                    bp_sys=VitalDistribution(110, 15, 80, 150),
                    spo2=VitalDistribution(96, 2, 90, 99),
                    temp_c=VitalDistribution(38.8, 0.5, 37.8, 41.0),
                    gcs=VitalDistribution(15, 1, 12, 15),
                    pain_score=VitalDistribution(5, 2, 2, 9),
                    correlations=[("hr", "temp_c", 0.6)],
                ),
            },
        ),

        # ── C05: Geriatric febrile illness ────────────────────────────────
        ClinicalCondition(
            condition_id="C05",
            label="Geriatric febrile illness (atypical sepsis)",
            typical_band="yellow",   # may appear mild → key test case
            red_flag_observations=[],
            trajectory_shape="compensating_then_decompensating",
            notes="Normal-looking vitals despite systemic illness — geriatric calibration escalates this",
            vitals_by_stratum={
                "geriatric": ConditionVitals(
                    hr=VitalDistribution(82, 12, 58, 110),    # may NOT tachycardia
                    rr=VitalDistribution(18, 4, 12, 28),
                    bp_sys=VitalDistribution(118, 20, 80, 160),
                    spo2=VitalDistribution(95, 3, 86, 99),
                    temp_c=VitalDistribution(38.5, 0.4, 37.8, 40.0),
                    gcs=VitalDistribution(14, 2, 10, 15),
                    pain_score=VitalDistribution(3, 2, 0, 8),  # may not report
                    correlations=[("hr", "temp_c", 0.3)],      # weak correlation
                ),
                "adult": ConditionVitals(
                    hr=VitalDistribution(105, 15, 80, 150),
                    rr=VitalDistribution(22, 4, 16, 36),
                    bp_sys=VitalDistribution(108, 18, 80, 145),
                    spo2=VitalDistribution(95, 3, 87, 99),
                    temp_c=VitalDistribution(38.5, 0.4, 37.8, 40.0),
                    gcs=VitalDistribution(15, 1, 13, 15),
                    pain_score=VitalDistribution(5, 2, 2, 9),
                    correlations=[("hr", "temp_c", 0.65)],
                ),
            },
        ),

        # ── C06: Anaphylaxis ──────────────────────────────────────────────
        ClinicalCondition(
            condition_id="C06",
            label="Anaphylaxis",
            typical_band="red",
            red_flag_observations=["difficulty_speaking_full_sentences"],
            trajectory_shape="stable_sudden",
            vitals_by_stratum={
                "adult": ConditionVitals(
                    hr=VitalDistribution(125, 20, 90, 180),
                    rr=VitalDistribution(26, 6, 16, 45),
                    bp_sys=VitalDistribution(80, 20, 50, 120),
                    spo2=VitalDistribution(91, 5, 75, 98),
                    temp_c=VitalDistribution(37.5, 0.5, 36.5, 38.5),
                    gcs=VitalDistribution(13, 3, 8, 15),
                    pain_score=VitalDistribution(5, 3, 1, 10),
                    correlations=[("hr", "bp_sys", -0.75), ("rr", "spo2", -0.7)],
                ),
                "child": ConditionVitals(
                    hr=VitalDistribution(145, 22, 100, 200),
                    rr=VitalDistribution(38, 8, 22, 65),
                    bp_sys=VitalDistribution(72, 18, 45, 110),
                    spo2=VitalDistribution(89, 6, 72, 97),
                    temp_c=VitalDistribution(37.5, 0.5, 36.5, 38.5),
                    gcs=VitalDistribution(12, 3, 7, 15),
                    pain_score=VitalDistribution(7, 2, 3, 10),
                    correlations=[("hr", "bp_sys", -0.8), ("rr", "spo2", -0.75)],
                ),
            },
        ),

        # ── C07: Epigastric pain / ambiguous (gastritis vs inferior MI) ───
        ClinicalCondition(
            condition_id="C07",
            label="Epigastric pain — ambiguous (gastritis vs ACS)",
            typical_band="yellow",   # genuinely ambiguous → low confidence
            red_flag_observations=[],
            trajectory_shape="stable_sudden",
            notes="Deciding evidence absent at T0 — model should reflect ambiguity",
            vitals_by_stratum={
                "adult": ConditionVitals(
                    hr=VitalDistribution(92, 14, 60, 130),
                    rr=VitalDistribution(18, 3, 12, 26),
                    bp_sys=VitalDistribution(130, 25, 90, 190),
                    spo2=VitalDistribution(97, 2, 90, 99),
                    temp_c=VitalDistribution(37.0, 0.4, 36.2, 38.0),
                    gcs=VitalDistribution(15, 0.5, 14, 15),
                    pain_score=VitalDistribution(5, 2, 2, 9),
                    correlations=[],  # deliberately low correlation — ambiguity
                ),
                "geriatric": ConditionVitals(
                    hr=VitalDistribution(82, 14, 55, 115),
                    rr=VitalDistribution(17, 3, 12, 24),
                    bp_sys=VitalDistribution(145, 30, 90, 220),
                    spo2=VitalDistribution(96, 3, 88, 99),
                    temp_c=VitalDistribution(37.0, 0.4, 36.0, 38.0),
                    gcs=VitalDistribution(15, 1, 13, 15),
                    pain_score=VitalDistribution(3, 2, 0, 8),
                    correlations=[],
                ),
            },
        ),

        # ── C08: SpO2-bias case — occult hypoxemia ────────────────────────
        ClinicalCondition(
            condition_id="C08",
            label="Respiratory distress with SpO2 bias risk",
            typical_band="yellow",
            red_flag_observations=[],
            trajectory_shape="compensating_then_decompensating",
            notes="SpO2 reads normal (96%) but patient is distressed — SpO2 alone cannot lower band",
            vitals_by_stratum={
                "adult": ConditionVitals(
                    hr=VitalDistribution(108, 16, 80, 150),
                    rr=VitalDistribution(24, 5, 16, 40),
                    bp_sys=VitalDistribution(118, 20, 85, 160),
                    spo2=VitalDistribution(96, 1, 93, 99),  # reads normal (bias)
                    temp_c=VitalDistribution(37.2, 0.4, 36.3, 38.2),
                    gcs=VitalDistribution(15, 1, 13, 15),
                    pain_score=VitalDistribution(6, 2, 3, 10),
                    correlations=[("hr", "rr", 0.6)],
                ),
            },
        ),

        # ── C09: Stale vitals / freshness decay case ──────────────────────
        ClinicalCondition(
            condition_id="C09",
            label="Patient with stale vitals (3h old readings)",
            typical_band="yellow",
            red_flag_observations=[],
            trajectory_shape="improving",
            notes="Vitals 3h old — confidence should be decayed and recheck raised",
            vitals_by_stratum={
                "adult": ConditionVitals(
                    hr=VitalDistribution(85, 12, 60, 120),
                    rr=VitalDistribution(17, 3, 12, 24),
                    bp_sys=VitalDistribution(122, 18, 90, 160),
                    spo2=VitalDistribution(97, 2, 92, 99),
                    temp_c=VitalDistribution(37.1, 0.3, 36.4, 38.0),
                    gcs=VitalDistribution(15, 0.5, 14, 15),
                    pain_score=VitalDistribution(4, 2, 1, 8),
                    correlations=[],
                ),
            },
        ),

        # ── C10: Zero history / first visit ───────────────────────────────
        ClinicalCondition(
            condition_id="C10",
            label="First visit — zero prior history",
            typical_band="yellow",
            red_flag_observations=[],
            trajectory_shape="improving",
            notes="No prior records — system must handle gracefully",
            vitals_by_stratum={
                "adult": ConditionVitals(
                    hr=VitalDistribution(88, 14, 62, 120),
                    rr=VitalDistribution(18, 3, 12, 26),
                    bp_sys=VitalDistribution(128, 20, 90, 170),
                    spo2=VitalDistribution(97, 2, 92, 99),
                    temp_c=VitalDistribution(37.0, 0.4, 36.3, 38.0),
                    gcs=VitalDistribution(15, 0.5, 14, 15),
                    pain_score=VitalDistribution(4, 2, 1, 8),
                    correlations=[],
                ),
            },
        ),

        # ── C11: Out-of-distribution presentation ─────────────────────────
        ClinicalCondition(
            condition_id="C11",
            label="Out-of-distribution / unusual presentation",
            typical_band="yellow",    # abstention expected
            red_flag_observations=[],
            trajectory_shape="stable_sudden",
            notes="OOD: unusual combination — model should abstain, hold at Yellow",
            vitals_by_stratum={
                "adult": ConditionVitals(
                    hr=VitalDistribution(55, 5, 42, 65),     # very low
                    rr=VitalDistribution(32, 4, 26, 40),     # high
                    bp_sys=VitalDistribution(155, 10, 140, 175),  # elevated
                    spo2=VitalDistribution(99, 1, 97, 100),  # normal
                    temp_c=VitalDistribution(34.5, 0.5, 33.5, 35.5),  # hypothermia
                    gcs=VitalDistribution(15, 0.5, 14, 15),
                    pain_score=VitalDistribution(2, 1, 0, 4),
                    correlations=[],
                ),
            },
        ),

        # ── C12: Obstetric emergency ──────────────────────────────────────
        ClinicalCondition(
            condition_id="C12",
            label="Obstetric emergency (bleeding in pregnancy / active labour)",
            typical_band="red",
            red_flag_observations=["active_labour_or_bleeding_pregnancy"],
            trajectory_shape="compensating_then_decompensating",
            vitals_by_stratum={
                "adolescent": ConditionVitals(
                    hr=VitalDistribution(118, 18, 85, 160),
                    rr=VitalDistribution(22, 5, 14, 38),
                    bp_sys=VitalDistribution(95, 20, 60, 140),
                    spo2=VitalDistribution(95, 3, 85, 99),
                    temp_c=VitalDistribution(37.2, 0.4, 36.3, 38.5),
                    gcs=VitalDistribution(14, 2, 10, 15),
                    pain_score=VitalDistribution(8, 2, 4, 10),
                    correlations=[("hr", "bp_sys", -0.7)],
                ),
                "adult": ConditionVitals(
                    hr=VitalDistribution(115, 18, 80, 160),
                    rr=VitalDistribution(22, 5, 14, 38),
                    bp_sys=VitalDistribution(98, 22, 60, 145),
                    spo2=VitalDistribution(95, 3, 85, 99),
                    temp_c=VitalDistribution(37.2, 0.4, 36.3, 38.5),
                    gcs=VitalDistribution(14, 2, 10, 15),
                    pain_score=VitalDistribution(8, 2, 4, 10),
                    correlations=[("hr", "bp_sys", -0.7)],
                ),
            },
        ),

        # ── C13: Poisoning / Overdose ─────────────────────────────────────
        ClinicalCondition(
            condition_id="C13",
            label="Poisoning or drug overdose",
            typical_band="red",
            red_flag_observations=["poisoning_overdose_or_snakebite",
                                   "altered_consciousness"],
            trajectory_shape="compensating_then_decompensating",
            vitals_by_stratum={
                "adult": ConditionVitals(
                    hr=VitalDistribution(108, 25, 45, 175),
                    rr=VitalDistribution(14, 6, 6, 30),
                    bp_sys=VitalDistribution(95, 25, 55, 150),
                    spo2=VitalDistribution(91, 7, 70, 99),
                    temp_c=VitalDistribution(36.8, 0.8, 35.0, 39.5),
                    gcs=VitalDistribution(9, 4, 3, 15),
                    pain_score=VitalDistribution(3, 3, 0, 9),
                    correlations=[("spo2", "rr", 0.7), ("gcs", "rr", 0.6)],
                ),
                "adolescent": ConditionVitals(
                    hr=VitalDistribution(112, 25, 45, 180),
                    rr=VitalDistribution(13, 6, 5, 30),
                    bp_sys=VitalDistribution(90, 25, 50, 145),
                    spo2=VitalDistribution(90, 8, 68, 99),
                    temp_c=VitalDistribution(36.8, 0.8, 35.0, 39.5),
                    gcs=VitalDistribution(8, 4, 3, 15),
                    pain_score=VitalDistribution(3, 3, 0, 9),
                    correlations=[("spo2", "rr", 0.7), ("gcs", "rr", 0.6)],
                ),
            },
        ),

        # ── C14: Trauma / penetrating injury ──────────────────────────────
        ClinicalCondition(
            condition_id="C14",
            label="Trauma / penetrating injury",
            typical_band="red",
            red_flag_observations=["uncontrolled_bleeding_or_penetrating_injury"],
            trajectory_shape="compensating_then_decompensating",
            vitals_by_stratum={
                "adult": ConditionVitals(
                    hr=VitalDistribution(122, 22, 80, 180),
                    rr=VitalDistribution(24, 6, 14, 42),
                    bp_sys=VitalDistribution(88, 25, 50, 140),
                    spo2=VitalDistribution(93, 5, 76, 99),
                    temp_c=VitalDistribution(36.5, 0.6, 35.0, 38.0),
                    gcs=VitalDistribution(12, 4, 3, 15),
                    pain_score=VitalDistribution(8, 2, 4, 10),
                    correlations=[("hr", "bp_sys", -0.8), ("spo2", "bp_sys", 0.6)],
                ),
            },
        ),

        # ── C15: Benign illness / anxiety ─────────────────────────────────
        ClinicalCondition(
            condition_id="C15",
            label="Benign viral illness / anxiety / panic",
            typical_band="green",
            red_flag_observations=[],
            trajectory_shape="improving",
            vitals_by_stratum={
                "adult": ConditionVitals(
                    hr=VitalDistribution(88, 12, 62, 118),
                    rr=VitalDistribution(18, 3, 12, 26),
                    bp_sys=VitalDistribution(128, 18, 95, 165),
                    spo2=VitalDistribution(98, 1, 95, 100),
                    temp_c=VitalDistribution(37.3, 0.4, 36.5, 38.0),
                    gcs=VitalDistribution(15, 0.3, 14, 15),
                    pain_score=VitalDistribution(3, 2, 0, 7),
                    correlations=[],
                ),
                "child": ConditionVitals(
                    hr=VitalDistribution(100, 14, 72, 140),
                    rr=VitalDistribution(22, 4, 15, 34),
                    bp_sys=VitalDistribution(105, 14, 80, 135),
                    spo2=VitalDistribution(98, 1, 95, 100),
                    temp_c=VitalDistribution(37.4, 0.5, 36.5, 38.5),
                    gcs=VitalDistribution(15, 0.3, 14, 15),
                    pain_score=VitalDistribution(3, 2, 0, 7),
                    correlations=[],
                ),
                "geriatric": ConditionVitals(
                    hr=VitalDistribution(82, 10, 58, 100),
                    rr=VitalDistribution(17, 3, 12, 24),
                    bp_sys=VitalDistribution(138, 20, 100, 175),
                    spo2=VitalDistribution(97, 2, 92, 99),
                    temp_c=VitalDistribution(37.2, 0.4, 36.2, 38.2),
                    gcs=VitalDistribution(15, 0.5, 14, 15),
                    pain_score=VitalDistribution(2, 2, 0, 6),
                    correlations=[],
                ),
            },
        ),
    ]}


# Module-level singleton
CONDITIONS: dict[str, ClinicalCondition] = _make_conditions()
