"""
medipilot-model/data/generator/corpus.py

Builds the fixed 20-record demo corpus (P-01…P-20) and commits it to
data/corpus_20.json.

P-01…P-10 map directly to the §10 acceptance cases in the brief.
P-11…P-20 cover additional strata/conditions for generalisation and training.

Run this file directly to regenerate the corpus:
    python -m data.generator.corpus
"""

from __future__ import annotations

import datetime
import json
import pathlib
import numpy as np

from data.generator.conditions import CONDITIONS
from data.generator.trajectories import build_trajectory
from data.generator.missingness import (
    MissingnessSpec, apply_missingness, apply_spo2_bias
)

# Fixed seed for reproducibility — corpus is deterministic
_RNG_SEED = 42
_T0_BASE = datetime.datetime(2026, 8, 22, 8, 0, 0, tzinfo=datetime.timezone.utc)


def _t0(offset_minutes: int = 0) -> datetime.datetime:
    return _T0_BASE + datetime.timedelta(minutes=offset_minutes)


# ---------------------------------------------------------------------------
# Corpus specifications
# Each entry maps to: patient_id, label, condition, stratum, age_days,
# plus special overrides (stale, zero_history, spo2_bias, reliability_flags)
# ---------------------------------------------------------------------------

CORPUS_SPECS = [
    # ── §10 Acceptance cases (P-01…P-10) ────────────────────────────────

    {
        "patient_id": "P-01",
        "case_id": "deteriorates_while_waiting",
        "label": "Adult chest discomfort — Yellow at arrival, deteriorates while waiting",
        "condition_id": "C02",   # ACS
        "stratum": "adult",
        "age_days": 365 * 42,    # 42-year-old
        "trajectory_shape_override": "compensating_then_decompensating",
        "t0_offset_min": 0,
        "reliability_flags": {"non_assisted_arrival": True},
        "notes": "Loop A must autonomously escalate partway through wait",
    },
    {
        "patient_id": "P-02",
        "case_id": "age_pair_paediatric",
        "label": "3-year-old at 38.5°C, tachypnoeic, poor feeding",
        "condition_id": "C04",   # paediatric febrile
        "stratum": "child",
        "age_days": 365 * 3 + 90,   # ~3.25 years
        "t0_offset_min": 10,
        "reliability_flags": {"non_assisted_arrival": False},
        "notes": "Paediatric stratum — must escalate",
        "red_flag_observations": ["infant_not_feeding_floppy_inconsolable"],
    },
    {
        "patient_id": "P-03",
        "case_id": "age_pair_geriatric",
        "label": "75-year-old at 38.5°C, unremarkable HR",
        "condition_id": "C05",   # geriatric febrile (atypical)
        "stratum": "geriatric",
        "age_days": 365 * 75 + 5,
        "t0_offset_min": 20,
        "reliability_flags": {"non_assisted_arrival": True, "stoic_presentation": True},
        "notes": "Geriatric stratum — same temp, different reasoning than P-02",
    },
    {
        "patient_id": "P-04",
        "case_id": "ambiguous_epigastric_pain",
        "label": "Adult epigastric pain — ambiguous (gastritis vs inferior MI)",
        "condition_id": "C07",
        "stratum": "adult",
        "age_days": 365 * 55,
        "t0_offset_min": 30,
        "reliability_flags": {},
        "notes": "Deciding evidence absent at T0 — low confidence, not forced to a band",
    },
    {
        "patient_id": "P-05",
        "case_id": "spo2_bias_dark_skin",
        "label": "Adult, dark skin, SpO2 reads 96%, distressed",
        "condition_id": "C08",
        "stratum": "adult",
        "age_days": 365 * 35,
        "t0_offset_min": 40,
        "spo2_bias": True,
        "spo2_bias_offset_mean": 3.0,
        "reliability_flags": {},
        "notes": "SpO2 reads high due to device bias — SpO2 alone must NOT lower band",
        "patient_flags": {"spo2_bias_risk": True},
    },
    {
        "patient_id": "P-06",
        "case_id": "stale_vitals_3h",
        "label": "Adult — last vitals 3 hours old",
        "condition_id": "C09",
        "stratum": "adult",
        "age_days": 365 * 48,
        "t0_offset_min": 50,
        "stale_vitals_hours": 3.0,
        "reliability_flags": {},
        "notes": "Same numbers as fresh, but confidence visibly decayed, recheck raised",
    },
    {
        "patient_id": "P-07",
        "case_id": "zero_history",
        "label": "Adult — first visit, zero history",
        "condition_id": "C10",
        "stratum": "adult",
        "age_days": 365 * 38,
        "t0_offset_min": 60,
        "zero_history": True,
        "reliability_flags": {"non_assisted_arrival": True},
        "notes": "Scores correctly with no prior record at all",
    },
    {
        "patient_id": "P-08",
        "case_id": "ood_abstention",
        "label": "Out-of-distribution presentation — unusual vital combination",
        "condition_id": "C11",
        "stratum": "adult",
        "age_days": 365 * 50,
        "t0_offset_min": 70,
        "reliability_flags": {},
        "notes": "Model abstains explicitly — holds at Yellow, never Green",
        "force_ood": True,
    },
    {
        "patient_id": "P-09",
        "case_id": "nurse_override_full_record",
        "label": "Nurse overrides Yellow→Red on physical finding system couldn't see",
        "condition_id": "C07",
        "stratum": "adult",
        "age_days": 365 * 62,
        "t0_offset_min": 80,
        "reliability_flags": {},
        "notes": "Override record must have all §9 fields; physical finding not in vitals",
        "pending_override": {
            "clinician_id": "N-201",
            "clinician_role": "senior_nurse",
            "system_band": "yellow",
            "clinician_band": "red",
            "direction": "escalation",
            "reason_code": "physical_finding_not_captured",
            "reason_text": "Peritoneal signs on palpation — absent in vitals; clinical judgement overrides.",
        },
    },
    {
        "patient_id": "P-10",
        "case_id": "missed_rechecks_under_surge",
        "label": "Green patient misses two consecutive rechecks under surge load",
        "condition_id": "C15",   # benign illness
        "stratum": "adult",
        "age_days": 365 * 28,
        "t0_offset_min": 90,
        "reliability_flags": {},
        "notes": "Escalates to Yellow on missed-recheck rule, not on vitals change",
        "simulate_missed_rechecks": 2,
    },

    # ── Generalisation cases (P-11…P-20) ────────────────────────────────

    {
        "patient_id": "P-11",
        "case_id": "neonate_fever_floppy",
        "label": "Neonate — fever + floppy",
        "condition_id": "C04",
        "stratum": "neonate",
        "age_days": 14,
        "t0_offset_min": 100,
        "reliability_flags": {"non_assisted_arrival": False},
        "red_flag_observations": ["infant_not_feeding_floppy_inconsolable"],
        "notes": "Neonate stratum — fever is emergency by default",
    },
    {
        "patient_id": "P-12",
        "case_id": "infant_sepsis",
        "label": "Infant sepsis",
        "condition_id": "C01",
        "stratum": "infant",
        "age_days": 180,   # 6 months
        "t0_offset_min": 110,
        "reliability_flags": {},
        "notes": "Infant — tachypnoea earliest sign, BP very late",
    },
    {
        "patient_id": "P-13",
        "case_id": "adolescent_poisoning_redflag",
        "label": "Adolescent poisoning",
        "condition_id": "C13",
        "stratum": "adolescent",
        "age_days": 365 * 16,
        "t0_offset_min": 120,
        "reliability_flags": {"communication_barrier": True},
        "red_flag_observations": ["poisoning_overdose_or_snakebite"],
        "notes": "Red-flag rule fires independent of model",
    },
    {
        "patient_id": "P-14",
        "case_id": "adult_stroke_redflag",
        "label": "Adult stroke",
        "condition_id": "C03",
        "stratum": "adult",
        "age_days": 365 * 58,
        "t0_offset_min": 130,
        "reliability_flags": {"difficulty_speaking_full_sentences": True},
        "red_flag_observations": ["sudden_onesided_weakness_facial_droop_speech_change"],
        "notes": "Red-flag fires; model also high-risk",
    },
    {
        "patient_id": "P-15",
        "case_id": "adult_anaphylaxis_redflag",
        "label": "Adult anaphylaxis",
        "condition_id": "C06",
        "stratum": "adult",
        "age_days": 365 * 29,
        "t0_offset_min": 140,
        "reliability_flags": {},
        "red_flag_observations": ["difficulty_speaking_full_sentences"],
        "notes": "Anaphylaxis — rapid SpO2 + BP drop",
    },
    {
        "patient_id": "P-16",
        "case_id": "geriatric_silent_mi",
        "label": "Geriatric silent MI",
        "condition_id": "C02",
        "stratum": "geriatric",
        "age_days": 365 * 80,
        "t0_offset_min": 150,
        "reliability_flags": {"stoic_presentation": True, "analgesia_given": True},
        "notes": "Geriatric ACS — stoic, analgesia masks pain; calibration must escalate",
    },
    {
        "patient_id": "P-17",
        "case_id": "adult_trauma_redflag",
        "label": "Adult trauma",
        "condition_id": "C14",
        "stratum": "adult",
        "age_days": 365 * 25,
        "t0_offset_min": 160,
        "reliability_flags": {},
        "red_flag_observations": ["uncontrolled_bleeding_or_penetrating_injury"],
        "notes": "Penetrating injury red flag",
    },
    {
        "patient_id": "P-18",
        "case_id": "geriatric_communication_barrier",
        "label": "Geriatric with communication barrier",
        "condition_id": "C05",
        "stratum": "geriatric",
        "age_days": 365 * 72,
        "t0_offset_min": 170,
        "reliability_flags": {"communication_barrier": True, "health_literacy_signal": True},
        "notes": "Reassurance reliability discounted; uncertainty widened",
    },
    {
        "patient_id": "P-19",
        "case_id": "adolescent_obstetric_redflag",
        "label": "Adolescent obstetric emergency",
        "condition_id": "C12",
        "stratum": "adolescent",
        "age_days": 365 * 17,
        "t0_offset_min": 180,
        "reliability_flags": {},
        "red_flag_observations": ["active_labour_or_bleeding_pregnancy"],
        "notes": "Obstetric red flag",
    },
    {
        "patient_id": "P-20",
        "case_id": "green_baseline",
        "label": "Adult benign illness — Green baseline",
        "condition_id": "C15",
        "stratum": "adult",
        "age_days": 365 * 34,
        "t0_offset_min": 190,
        "reliability_flags": {},
        "notes": "Green baseline; verifies system doesn't over-triage benign presentations",
    },
]


def build_corpus(seed: int = _RNG_SEED) -> list[dict]:
    """Build all 20 corpus records and return as list of dicts."""
    rng = np.random.default_rng(seed)
    records = []

    for spec in CORPUS_SPECS:
        cid = spec["condition_id"]
        condition = CONDITIONS[cid]

        # Allow trajectory shape override (for P-01 ACS which deteriorates)
        if "trajectory_shape_override" in spec:
            import copy as _copy
            condition = _copy.copy(condition)
            object.__setattr__(condition, "trajectory_shape", spec["trajectory_shape_override"])

        stratum = spec["stratum"]
        age_days = spec["age_days"]
        t0 = _t0(spec.get("t0_offset_min", 0))

        traj = build_trajectory(
            patient_id=spec["patient_id"],
            condition=condition,
            stratum=stratum,
            age_days=age_days,
            t0=t0,
            rng=rng,
            stale_vitals_hours=spec.get("stale_vitals_hours", 0.0),
            zero_history=spec.get("zero_history", False),
        )

        # Apply SpO2 bias if flagged
        if spec.get("spo2_bias", False):
            traj = apply_spo2_bias(
                traj,
                offset_mean=spec.get("spo2_bias_offset_mean", 2.5),
                rng=rng,
            )

        # Apply missingness per condition defaults (sensor_failure for OOD)
        if spec.get("force_ood", False):
            ms = MissingnessSpec(
                mechanism="sensor_failure",
                affected_vitals=["spo2", "gcs"],
                probability=0.6,
            )
            traj = apply_missingness(traj, ms, rng)

        record = {
            "patient_id": spec["patient_id"],
            # Stable semantic key for cross-track integration (F5) — the
            # other two tracks (speech/LLM, frontend) should key off this,
            # not the numeric patient_id, since corpus generation order can
            # renumber cases without this ID changing.
            "case_id": spec["case_id"],
            "label": spec["label"],
            "condition_id": cid,
            "stratum": stratum,
            "age_days": age_days,
            "t0": t0.isoformat(),
            "notes": spec.get("notes", ""),
            "reliability_flags": spec.get("reliability_flags", {}),
            "patient_flags": spec.get("patient_flags", {}),
            "red_flag_observations": spec.get("red_flag_observations", []),
            "pending_override": spec.get("pending_override"),
            "simulate_missed_rechecks": spec.get("simulate_missed_rechecks", 0),
            "stale_vitals_hours": spec.get("stale_vitals_hours", 0.0),
            "zero_history": spec.get("zero_history", False),
            "force_ood": spec.get("force_ood", False),
            "trajectory": traj.as_dict(),
        }
        records.append(record)

    return records


def save_corpus(records: list[dict], output_path: pathlib.Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(records, f, indent=2, ensure_ascii=False)
    print(f"Corpus written: {output_path} ({len(records)} records)")


if __name__ == "__main__":
    root = pathlib.Path(__file__).parent.parent
    out = root / "corpus_20.json"
    records = build_corpus()
    save_corpus(records, out)
