"""
backend/data/generator/labels.py

Outcome-derived labels for supervised training.

The whitepaper is explicit that the model must train on OUTCOMES, not on band
labels: imitating triage labels encodes their ~32% mistriage rate. This module
derives the outcome from the per-patient latent, never from the assigned band.

WHY THIS IS NOT CIRCULAR
------------------------
The naive approach — label = f(severity) — produces a fake result. Measured on
this generator, late-window peak severity is essentially a lookup on
trajectory_shape, which is a per-condition constant; a model trained on that
label scores AUROC 0.988 from t=0 vitals alone, because it is really doing
condition identification. Three structural choices prevent that here:

  1. The label lives strictly in the FUTURE relative to the features. Features
     come from steps <= k; the label is computed from severity over (k, end].
     Because the inflection point is now per-patient and random, the future is
     genuinely underdetermined by the observation window.

  2. A `frailty` latent enters the outcome and NEVER touches any vital. No
     feature set can recover it, so it puts a hard floor under Bayes error.

  3. The outcome is a BERNOULLI DRAW, not a threshold. Two patients with
     identical conditions and near-identical vitals can differ in outcome.

Together these bound the achievable AUC well below 1.0. `severity_oracle_auc()`
computes that ceiling explicitly so the trained model can be reported as a
fraction of it — a model that approaches or exceeds the oracle has leakage.

NAMING
------
The head is `critical_composite_h180`, not `critical_24h`. The synthetic horizon
is 180 minutes. Calling it "24h" anywhere in code or an evaluation table would
be a false claim about what was actually measured; the 24-hour composite is the
real-data analogue described in the whitepaper.
"""

from __future__ import annotations

import math
import pathlib
from dataclasses import dataclass, asdict
from typing import Optional

import numpy as np
import yaml


_CONFIG_PATH = pathlib.Path(__file__).parent.parent.parent / "config" / "label_spec.yaml"

HORIZON_MINUTES = 180
LABEL_NAME_PRIMARY = "critical_composite_h180"
LABEL_NAME_SECONDARY = "derangement_h60"


@dataclass
class LabelSpec:
    """Frozen label-generation parameters. Hashed into the artifact manifest."""
    beta0: float          # intercept, solved to hit target prevalence
    beta1: float          # weight on peak future severity
    beta2: float          # weight on mean future severity
    beta3: float          # weight on frailty (outcome-only latent)
    frailty_sd: float
    target_prevalence: float
    k_min_step: int       # earliest prediction index
    k_max_step: int       # latest prediction index
    short_horizon_steps: int   # window for the secondary derangement label

    def as_dict(self) -> dict:
        return asdict(self)


def default_spec() -> LabelSpec:
    """Defaults used when config/label_spec.yaml is absent."""
    return LabelSpec(
        beta0=-4.0,
        beta1=10.0,
        beta2=4.0,
        beta3=0.4,
        frailty_sd=1.0,
        target_prevalence=0.10,
        k_min_step=6,      # 30 min
        k_max_step=18,     # 90 min
        short_horizon_steps=12,
    )


def load_spec(path: pathlib.Path = _CONFIG_PATH) -> LabelSpec:
    if not path.exists():
        return default_spec()
    with open(path, encoding="utf-8") as f:
        cfg = yaml.safe_load(f) or {}
    d = default_spec().as_dict()
    d.update(cfg.get("label_spec", {}))
    return LabelSpec(**d)


# ---------------------------------------------------------------------------
# Frailty — the outcome-only latent
# ---------------------------------------------------------------------------

# Strata where a given physiologic derangement carries worse outcomes at the
# same vitals. This is the outcome-side analogue of reassurance_decay, and it is
# why a trained model can legitimately learn a stratum effect from data.
_FRAILTY_MU = {
    "neonate": 0.5,
    "infant": 0.3,
    "child": 0.0,
    "adolescent": 0.0,
    "adult": 0.0,
    "geriatric": 0.5,
}


def draw_frailty(stratum: str, rng: np.random.Generator, spec: Optional[LabelSpec] = None) -> float:
    spec = spec or default_spec()
    mu = _FRAILTY_MU.get(stratum, 0.0)
    return float(rng.normal(mu, spec.frailty_sd))


def draw_acuity(typical_band: str, rng: np.random.Generator) -> float:
    """
    Per-patient severity ceiling, drawn from a condition-conditional Beta.

    Crucially this is a DISTRIBUTION, not a constant: two patients with the same
    condition get different acuities, so condition identity alone does not
    determine the outcome.
    """
    alpha, beta = {
        "red": (4.0, 2.2),
        "yellow": (2.4, 3.2),
        "green": (1.5, 5.0),
    }.get(typical_band, (2.4, 3.2))
    return float(rng.beta(alpha, beta))


# ---------------------------------------------------------------------------
# Label derivation
# ---------------------------------------------------------------------------

def _sigmoid(x: float) -> float:
    if x >= 0:
        return 1.0 / (1.0 + math.exp(-x))
    e = math.exp(x)
    return e / (1.0 + e)


@dataclass
class DerivedLabels:
    k_step: int                    # prediction index; features use steps <= k
    p_event: float                 # true event probability (NEVER a feature)
    critical: int                  # primary binary label
    derangement: float             # secondary continuous label
    s_max_future: float            # peak severity after k (NEVER a feature)
    s_mean_future: float


def derive_labels(
    severity_path: list[float],
    frailty: float,
    rng: np.random.Generator,
    spec: Optional[LabelSpec] = None,
    k_step: Optional[int] = None,
) -> DerivedLabels:
    """
    Derive both labels from the per-patient severity path.

    Everything returned other than `k_step` is PROHIBITED as a model feature.
    """
    spec = spec or default_spec()
    n = len(severity_path)

    if k_step is None:
        k_hi = min(spec.k_max_step, max(spec.k_min_step, n - 2))
        k_step = int(rng.integers(spec.k_min_step, k_hi + 1)) if k_hi >= spec.k_min_step else 0
    k_step = max(0, min(k_step, n - 1))

    future = severity_path[k_step + 1:]
    if not future:                      # zero-history patients have n == 1
        future = severity_path[k_step:]

    s_max = float(max(future))
    s_mean = float(np.mean(future))

    logit = spec.beta0 + spec.beta1 * s_max + spec.beta2 * s_mean + spec.beta3 * frailty
    p_event = _sigmoid(logit)
    critical = int(rng.random() < p_event)

    short = severity_path[k_step + 1: k_step + 1 + spec.short_horizon_steps] or future
    derangement = float(max(short))

    return DerivedLabels(
        k_step=k_step,
        p_event=p_event,
        critical=critical,
        derangement=derangement,
        s_max_future=s_max,
        s_mean_future=s_mean,
    )


# ---------------------------------------------------------------------------
# Prevalence solver + oracle ceiling
# ---------------------------------------------------------------------------

def solve_beta0(
    s_max: np.ndarray,
    s_mean: np.ndarray,
    frailty: np.ndarray,
    spec: LabelSpec,
    tol: float = 1e-4,
    max_iter: int = 200,
) -> float:
    """
    Bisect beta0 so the mean event probability equals the target prevalence.

    Solving on the probability mean (rather than on sampled outcomes) makes this
    deterministic and independent of the draw.
    """
    lin = spec.beta1 * s_max + spec.beta2 * s_mean + spec.beta3 * frailty

    def prev_at(b0: float) -> float:
        return float(np.mean(1.0 / (1.0 + np.exp(-(b0 + lin)))))

    lo, hi = -30.0, 30.0
    for _ in range(max_iter):
        mid = (lo + hi) / 2.0
        p = prev_at(mid)
        if abs(p - spec.target_prevalence) < tol:
            return mid
        if p < spec.target_prevalence:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2.0


def severity_oracle_auc(s_max: np.ndarray, y: np.ndarray) -> dict:
    """
    Ceiling achievable by a model that knows the true future peak severity.

    This is the anti-self-congratulation control: report the trained model's
    metrics as a fraction of these. A trained model that approaches or exceeds
    the oracle has leakage, and that is a mechanical detection, not a judgement.
    """
    from sklearn.metrics import roc_auc_score, average_precision_score

    if len(np.unique(y)) < 2:
        return {"oracle_auroc": float("nan"), "oracle_auprc": float("nan")}
    return {
        "oracle_auroc": float(roc_auc_score(y, s_max)),
        "oracle_auprc": float(average_precision_score(y, s_max)),
    }
