"""
backend/data/generator/trajectories.py

Time-series trajectory builder for synthetic patients.
Each patient gets a physiologically plausible vital-sign trajectory
(T=0 to T=180 min, 5-min intervals = 37 timesteps).

Three trajectory shapes:
  - compensating_then_decompensating: patient holds for a while then deteriorates
  - improving: gradual improvement from T0
  - stable_sudden: stable then rapid deterioration at a random inflection point

Measurements carry the (value, timestamp, source, validity) tuple per Invariant 4.
"""

from __future__ import annotations

import datetime
import numpy as np
from dataclasses import dataclass, field
from typing import Optional

from data.generator.conditions import ClinicalCondition, ConditionVitals


VITALS = ["hr", "rr", "bp_sys", "spo2", "temp_c", "gcs", "pain_score"]

# How much of severity comes from the per-patient latent acuity vs the shape
# profile. Tuned empirically (see plan): higher w makes the latent more visible
# early, which is what makes the task learnable without making it trivial.
SEVERITY_BLEND_W = 0.6

# Per-patient, per-vital constant offset ("this patient runs hot"), as a
# multiple of that vital's std. Without it, severity noise is iid across
# timesteps and a 30-minute slope is pure noise — which would make trend
# features look useless for a reason that has nothing to do with physiology.
BASELINE_OFFSET_SD = 0.5


@dataclass
class Measurement:
    """A single vital reading with provenance — the (value, ts, source, validity) tuple."""
    value: float
    timestamp: datetime.datetime
    source: str         # "recheck_station" | "nurse" | "family" | "self_report" | "sensor"
    validity: str       # "valid" | "sensor_fail" | "stale" | "missing"
    vital: str

    def as_dict(self) -> dict:
        return {
            "value": round(self.value, 2),
            "timestamp": self.timestamp.isoformat(),
            "source": self.source,
            "validity": self.validity,
            "vital": self.vital,
        }


@dataclass
class VitalTimeSeries:
    """Complete trajectory for a single vital sign."""
    vital: str
    readings: list[Measurement] = field(default_factory=list)

    def latest_valid(self) -> Optional[Measurement]:
        for r in reversed(self.readings):
            if r.validity == "valid":
                return r
        return None


@dataclass
class PatientLatent:
    """
    Per-patient latent state. NEVER a model feature — this is the generative
    cause that produces both the observed vitals and the outcome label, so
    exposing any of it to the model is target leakage by construction.

    Serialised under the `_latent` key, which config/feature_registry.yaml
    classifies PROHIBITED and model/features.py never reads.
    """
    acuity: float                   # per-patient severity ceiling a in [0,1]
    frailty: float                  # affects OUTCOME ONLY, never any vital
    inflection_frac: float          # per-patient, drawn ONCE (see _severity_path)
    baseline_offset: dict[str, float]   # per-vital "this patient runs hot" term
    severity_path: list[float]      # severity at each timestep

    def as_dict(self) -> dict:
        return {
            "acuity": round(self.acuity, 4),
            "frailty": round(self.frailty, 4),
            "inflection_frac": round(self.inflection_frac, 4),
            "baseline_offset": {k: round(v, 3) for k, v in self.baseline_offset.items()},
            "severity_path": [round(s, 4) for s in self.severity_path],
        }


@dataclass
class PatientTrajectory:
    """Full time-series trajectory for one patient."""
    patient_id: str
    condition_id: str
    stratum: str
    age_days: int
    t0: datetime.datetime
    series: dict[str, VitalTimeSeries] = field(default_factory=dict)
    latent: Optional[PatientLatent] = None

    def snapshot_at(self, t_minutes: int) -> dict[str, Optional[Measurement]]:
        """Return the most recent valid reading for each vital at time t_minutes."""
        cutoff = self.t0 + datetime.timedelta(minutes=t_minutes)
        result = {}
        for vital, ts in self.series.items():
            readings_before = [r for r in ts.readings if r.timestamp <= cutoff]
            valid_before = [r for r in readings_before if r.validity == "valid"]
            result[vital] = valid_before[-1] if valid_before else None
        return result

    def as_dict(self) -> dict:
        d = {
            "patient_id": self.patient_id,
            "condition_id": self.condition_id,
            "stratum": self.stratum,
            "age_days": self.age_days,
            "t0": self.t0.isoformat(),
            "series": {
                v: [r.as_dict() for r in ts.readings]
                for v, ts in self.series.items()
            },
        }
        if self.latent is not None:
            d["_latent"] = self.latent.as_dict()
        return d


# ---------------------------------------------------------------------------
# Core trajectory generator
# ---------------------------------------------------------------------------

def _apply_correlations(
    vitals: dict[str, float],
    cond_vitals: ConditionVitals,
    rng: np.random.Generator,
    strength: float = 0.3,
) -> dict[str, float]:
    """Nudge correlated vitals to enforce physiological correlations."""
    for (a, b, direction) in cond_vitals.correlations:
        if a not in vitals or b not in vitals:
            continue
        # Compute normalised deviation of a from its mean
        a_dist = getattr(cond_vitals, a)
        dev_a = (vitals[a] - a_dist.mean) / max(a_dist.std, 1e-6)
        # Nudge b in the correlated direction
        b_dist = getattr(cond_vitals, b)
        nudge = direction * dev_a * strength * b_dist.std
        vitals[b] = float(np.clip(vitals[b] + nudge, b_dist.low, b_dist.high))
    return vitals


def _sample_vitals_at_severity(
    cond_vitals: ConditionVitals,
    severity: float,
    rng: np.random.Generator,
    baseline_offset: Optional[dict[str, float]] = None,
) -> dict[str, float]:
    """
    Sample vitals, biased by severity (0=mild, 1=peak severity).
    severity pushes distributions toward their dangerous extremes.

    `baseline_offset` is a per-patient constant (in units of each vital's std)
    held fixed across the whole trajectory, so successive readings of the same
    patient are correlated rather than iid draws around the condition mean.
    """
    result: dict[str, float] = {}
    for vital in VITALS:
        dist = getattr(cond_vitals, vital)
        # Bias: severity shifts mean toward the dangerous end of the range
        # For HR, RR, temp: dangerous = high; for bp_sys, spo2, gcs: dangerous = low
        danger_high = vital in ("hr", "rr", "temp_c", "pain_score")
        bias = severity * dist.std * (1.2 if danger_high else -1.2)
        if baseline_offset:
            bias += baseline_offset.get(vital, 0.0) * dist.std
        v = rng.normal(dist.mean + bias, dist.std * 0.6)
        result[vital] = float(np.clip(v, dist.low, dist.high))

    result = _apply_correlations(result, cond_vitals, rng)
    return result


def build_trajectory(
    patient_id: str,
    condition: ClinicalCondition,
    stratum: str,
    age_days: int,
    t0: datetime.datetime,
    rng: np.random.Generator,
    stale_vitals_hours: float = 0.0,    # if >0, vitals are this many hours old
    zero_history: bool = False,
    spo2_bias_offset: float = 0.0,      # upward SpO2 offset (device bias simulation)
    acuity: Optional[float] = None,     # per-patient latent; None -> legacy behaviour
    frailty: float = 0.0,               # outcome-only latent, never touches a vital
) -> PatientTrajectory:
    """
    Build a full trajectory for one patient.

    Args:
        stale_vitals_hours: if >0, sets timestamps to be that many hours before t0
        zero_history: if True, only a single T0 reading is produced (no history)
        spo2_bias_offset: upward SpO2 offset (simulates pulse-ox bias for darker skin tone)
        acuity: per-patient latent severity ceiling in [0,1]. When supplied, the
            trajectory uses the per-patient severity path (inflection drawn once)
            and attaches a PatientLatent. When None, the legacy per-step path is
            used so existing callers keep their previous behaviour.
        frailty: per-patient outcome modifier. Recorded on the latent and used by
            data/generator/labels.py; deliberately has NO effect on any vital, so
            it creates irreducible outcome noise the model cannot ever recover.
    """
    cond_vitals = condition.vitals_for_stratum(stratum)
    shape = condition.trajectory_shape
    t_step_min = 5
    n_steps = 37  # 0..180 min

    traj = PatientTrajectory(
        patient_id=patient_id,
        condition_id=condition.condition_id,
        stratum=stratum,
        age_days=age_days,
        t0=t0,
        series={v: VitalTimeSeries(vital=v) for v in VITALS},
    )

    if zero_history:
        n_steps = 1  # only T=0

    use_latent = acuity is not None
    baseline_offset: dict[str, float] = {}
    severity_path: list[float] = []
    inflection = 0.0

    if use_latent:
        inflection = float(rng.uniform(0.55, 0.8))          # ONCE per patient
        baseline_offset = {
            v: float(rng.normal(0.0, BASELINE_OFFSET_SD)) for v in VITALS
        }
        severity_path = _severity_path(shape, n_steps, float(acuity), inflection, rng)
        traj.latent = PatientLatent(
            acuity=float(acuity),
            frailty=float(frailty),
            inflection_frac=inflection,
            baseline_offset=baseline_offset,
            severity_path=severity_path,
        )

    for step in range(n_steps):
        t_minutes = step * t_step_min

        # Compute severity at this timestep
        if use_latent:
            severity = severity_path[step]
        else:
            severity = _severity_at(shape, step, n_steps, rng)

        # Sample vitals
        vitals_at_step = _sample_vitals_at_severity(
            cond_vitals, severity, rng, baseline_offset or None
        )

        # Apply SpO2 bias (upward offset — occult hypoxemia under-detection)
        if "spo2" in vitals_at_step:
            vitals_at_step["spo2"] = min(
                100.0,
                vitals_at_step["spo2"] + spo2_bias_offset
            )

        # Determine timestamp
        if stale_vitals_hours > 0 and step == 0:
            ts = t0 - datetime.timedelta(hours=stale_vitals_hours)
        else:
            ts = t0 + datetime.timedelta(minutes=t_minutes)

        # Determine source and validity
        source = _pick_source(step, rng)
        validity = "valid"

        for vital, value in vitals_at_step.items():
            traj.series[vital].readings.append(Measurement(
                value=round(value, 2),
                timestamp=ts,
                source=source,
                validity=validity,
                vital=vital,
            ))

    return traj


def _shape_profile(shape: str, frac: float, inflection: float) -> float:
    """
    Noise-free severity profile in [0,1] at trajectory fraction `frac`.

    `inflection` is supplied by the caller and is drawn ONCE PER PATIENT.
    Drawing it here (the previous behaviour) re-sampled it at every timestep,
    which destroyed the per-patient sudden-deterioration event: the path
    oscillated between the plateau and the ramp instead of deteriorating
    monotonically. That is the signal the whole "deteriorates while waiting"
    thesis depends on, so it has to be a patient-level property.
    """
    if shape == "compensating_then_decompensating":
        plateau_end = 0.55
        if frac < plateau_end:
            return 0.25 + 0.1 * (frac / plateau_end)
        return 0.35 + 0.65 * ((frac - plateau_end) / (1 - plateau_end)) ** 1.5

    if shape == "improving":
        return 0.7 * (1 - frac) + 0.05

    if shape == "stable_sudden":
        if frac < inflection:
            return 0.2
        return 0.2 + 0.8 * ((frac - inflection) / max(1 - inflection, 1e-6))

    return 0.3


def _severity_path(
    shape: str,
    n_steps: int,
    acuity: float,
    inflection: float,
    rng: np.random.Generator,
    blend_w: float = SEVERITY_BLEND_W,
) -> list[float]:
    """
    Full per-patient severity path.

    severity(t) = clip(blend_w * acuity + (1 - blend_w) * shape_profile(t)) + noise

    The blend is what makes the per-patient latent `acuity` partially visible
    from t=0 onward while the shape still drives the time course. Without it
    the latent is invisible in the observation window and the prediction task
    becomes impossible rather than merely hard.
    """
    path = []
    for step in range(n_steps):
        frac = step / max(n_steps - 1, 1)
        prof = _shape_profile(shape, frac, inflection)
        sev = blend_w * acuity + (1.0 - blend_w) * prof
        sev += rng.normal(0, 0.03)
        path.append(float(np.clip(sev, 0.0, 1.0)))
    return path


def _severity_at(shape: str, step: int, n_steps: int, rng: np.random.Generator) -> float:
    """
    Deprecated single-step accessor, kept so existing callers and tests keep
    working. Prefer _severity_path(), which draws the inflection once per
    patient. This wrapper reproduces the old per-step behaviour and therefore
    still has the oscillation defect — do not use it to generate training data.
    """
    frac = step / max(n_steps - 1, 1)
    inflection = rng.uniform(0.55, 0.8)
    sev = _shape_profile(shape, frac, inflection)
    noise = 0.06 if shape == "stable_sudden" else 0.04
    return float(np.clip(sev + rng.normal(0, noise), 0, 1))


def _pick_source(step: int, rng: np.random.Generator) -> str:
    """Pick a realistic measurement source based on step."""
    if step == 0:
        return "recheck_station"  # T0 always from intake station
    sources = ["recheck_station", "nurse", "nurse", "sensor"]
    return rng.choice(sources)
