"""
backend/data/generator/missingness.py

Structured missingness mechanisms — not uniform random dropout.

Three distinct mechanisms:
  1. sensor_failure   — reading present but flagged invalid
  2. zero_history     — no prior records at all (first visit patient)
  3. staff_shortage   — reading simply absent (nobody had time)

Also applies SpO2 device bias: a calibrated upward offset for darker-skin flag,
modelling occult hypoxemia under-detection per §5 of the brief.
"""

from __future__ import annotations

import copy
import numpy as np
from dataclasses import dataclass
from typing import Optional

from data.generator.trajectories import PatientTrajectory, Measurement, VITALS


@dataclass
class MissingnessSpec:
    """Configuration for how missingness is applied to a trajectory."""
    mechanism: str              # "sensor_failure" | "zero_history" | "staff_shortage" | "none"
    affected_vitals: list[str]  # which vitals to apply it to ("all" resolved upstream)
    probability: float          # probability per reading that this mechanism fires


def apply_sensor_failure(
    traj: PatientTrajectory,
    vitals: list[str],
    probability: float,
    rng: np.random.Generator,
) -> PatientTrajectory:
    """
    Mark some readings as sensor_fail — reading has a value but is flagged invalid.
    The value field is retained (with random noise added to simulate malfunction)
    but validity = "sensor_fail" means the model must treat it as unreliable.
    """
    for vital in vitals:
        if vital not in traj.series:
            continue
        for reading in traj.series[vital].readings:
            if rng.random() < probability and reading.validity == "valid":
                # Sensor failure: corrupt the value and mark invalid
                noise = rng.normal(0, 8.0)  # large noise = sensor artefact
                reading.value = round(reading.value + noise, 2)
                reading.validity = "sensor_fail"
                reading.source = "sensor"
    return traj


def apply_staff_shortage(
    traj: PatientTrajectory,
    vitals: list[str],
    drop_from_step: int,
    rng: np.random.Generator,
) -> PatientTrajectory:
    """
    Remove readings entirely from `drop_from_step` onward for affected vitals.
    Models the case where staff simply didn't have time to take measurements.
    Readings are truly absent — no value, no validity entry.
    """
    for vital in vitals:
        if vital not in traj.series:
            continue
        ts = traj.series[vital]
        # Keep only readings before the drop point (by index)
        ts.readings = ts.readings[:drop_from_step]
    return traj


def apply_zero_history(
    traj: PatientTrajectory,
) -> PatientTrajectory:
    """
    Reduces trajectory to only the T=0 reading per vital.
    Models a first-visit patient with no prior records.
    """
    for vital in traj.series:
        readings = traj.series[vital].readings
        traj.series[vital].readings = readings[:1] if readings else []
    return traj


def apply_spo2_bias(
    traj: PatientTrajectory,
    offset_mean: float = 2.5,
    offset_std: float = 1.0,
    rng: Optional[np.random.Generator] = None,
) -> PatientTrajectory:
    """
    Apply an upward SpO2 offset to simulate pulse-oximetry bias for darker skin tones.
    This models the documented phenomenon where darker-skinned patients have occult
    hypoxemia under-detected at higher rates (device reads higher than actual).

    The offset is positive (device reads higher than reality), meaning a patient
    who truly has SpO2 = 92% may read as 95-96% on the device.

    Important: the `spo2_bias` flag must be set on the patient record so the
    SpO2 bias guard in rules/spo2_bias_guard.py can enforce that SpO2 alone
    never justifies de-escalation.
    """
    if rng is None:
        rng = np.random.default_rng()

    for reading in traj.series.get("spo2", type("_", (), {"readings": []})()).readings:
        offset = float(np.clip(rng.normal(offset_mean, offset_std), 0.5, 5.0))
        reading.value = min(100.0, round(reading.value + offset, 2))
        # Tag the reading so downstream guards know bias was applied
        reading.source = reading.source + "+spo2_bias"
    return traj


def apply_missingness(
    traj: PatientTrajectory,
    spec: MissingnessSpec,
    rng: np.random.Generator,
) -> PatientTrajectory:
    """Dispatch to the appropriate missingness mechanism."""
    vitals = spec.affected_vitals if spec.affected_vitals != ["all"] else VITALS

    if spec.mechanism == "none":
        return traj
    elif spec.mechanism == "sensor_failure":
        return apply_sensor_failure(traj, vitals, spec.probability, rng)
    elif spec.mechanism == "zero_history":
        return apply_zero_history(traj)
    elif spec.mechanism == "staff_shortage":
        # Drop readings after the first 40% of the trajectory
        n_readings = max(len(traj.series[VITALS[0]].readings), 1)
        drop_from = max(1, int(n_readings * 0.4))
        return apply_staff_shortage(traj, vitals, drop_from, rng)
    else:
        raise ValueError(f"Unknown missingness mechanism: {spec.mechanism!r}")
