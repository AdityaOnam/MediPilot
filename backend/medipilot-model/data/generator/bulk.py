"""
medipilot-model/data/generator/bulk.py

N-parameterised training-set generator.

`build_corpus()` produces the fixed 20-record demo corpus. This produces the
training population: thousands of patients sampled over (condition, stratum,
missingness), each with a per-patient latent and an outcome-derived label.

STRATUM COVERAGE
----------------
Five conditions (C08-C11, C14) define vitals only for "adult", and
`ClinicalCondition.vitals_for_stratum()` SILENTLY falls back to the adult
distribution for anything else. Sampling (condition x stratum) freely would
therefore mint "neonates" carrying adult trauma physiology, and any per-stratum
fairness metric computed on those rows would be measuring nonsense.

So: sampling is restricted to explicitly-defined (condition, stratum) pairs, and
every row records `stratum_is_fallback` for audit. Coverage is narrower and
honest rather than broad and fabricated.

Usage:
    python -m data.generator.bulk --n 20000 --out data/train_set.jsonl
"""

from __future__ import annotations

import argparse
import datetime
import json
import pathlib
from typing import Optional

import numpy as np

from data.generator.conditions import CONDITIONS
from data.generator.trajectories import build_trajectory, VITALS
from data.generator.missingness import MissingnessSpec, apply_missingness, apply_spo2_bias
from data.generator.labels import (
    LabelSpec, load_spec, draw_acuity, draw_frailty, derive_labels,
    solve_beta0, LABEL_NAME_PRIMARY, LABEL_NAME_SECONDARY,
)

UTC = datetime.timezone.utc
_T0 = datetime.datetime(2026, 8, 22, 8, 0, 0, tzinfo=UTC)

# Approximate age ranges per stratum, in days.
_STRATUM_AGE_DAYS = {
    "neonate": (0, 27),
    "infant": (28, 364),
    "child": (365, 4379),
    "adolescent": (4380, 6569),
    "adult": (6570, 23724),
    "geriatric": (23725, 36500),
}

# Missingness mixture. Reflects a real ED: most patients have a full set, a
# minority have a failed sensor, a few arrive with no history at all.
_MISSINGNESS_MIX = [
    (None, 0.60),
    ("sensor_failure", 0.18),
    ("staff_shortage", 0.16),
    ("zero_history", 0.06),
]


def _defined_pairs() -> list[tuple[str, str]]:
    """(condition_id, stratum) pairs with an EXPLICIT vitals distribution."""
    pairs = []
    for cid, cond in CONDITIONS.items():
        for stratum in cond.vitals_by_stratum:
            pairs.append((cid, stratum))
    return pairs


def _sample_age_days(stratum: str, rng: np.random.Generator) -> int:
    lo, hi = _STRATUM_AGE_DAYS.get(stratum, _STRATUM_AGE_DAYS["adult"])
    return int(rng.integers(lo, hi + 1))


def _pick_missingness(rng: np.random.Generator) -> Optional[str]:
    r = float(rng.random())
    acc = 0.0
    for name, p in _MISSINGNESS_MIX:
        acc += p
        if r < acc:
            return name
    return None


def generate_dataset(
    n: int = 20000,
    seed: int = 1337,
    spec: Optional[LabelSpec] = None,
    solve_prevalence: bool = True,
) -> tuple[list[dict], LabelSpec, dict]:
    """
    Generate n labelled patients.

    Two passes. The first builds trajectories and the latent quantities the
    label depends on; beta0 is then solved by bisection so the mean event
    probability equals the target prevalence; the second pass draws outcomes.
    Solving on the probability mean rather than on sampled outcomes keeps this
    deterministic and independent of the draw.
    """
    spec = spec or load_spec()
    rng = np.random.default_rng(seed)
    pairs = _defined_pairs()

    staged: list[dict] = []
    s_max_all, s_mean_all, frailty_all = [], [], []

    for i in range(n):
        cid, stratum = pairs[int(rng.integers(len(pairs)))]
        cond = CONDITIONS[cid]
        age_days = _sample_age_days(stratum, rng)

        acuity = draw_acuity(cond.typical_band, rng)
        frailty = draw_frailty(stratum, rng, spec)

        mech = _pick_missingness(rng)
        zero_history = mech == "zero_history"
        stale_hours = float(rng.uniform(2.0, 4.0)) if rng.random() < 0.05 else 0.0
        spo2_bias = bool(rng.random() < 0.12)

        traj = build_trajectory(
            patient_id=f"S{i:07d}",
            condition=cond,
            stratum=stratum,
            age_days=age_days,
            t0=_T0,
            rng=rng,
            stale_vitals_hours=stale_hours,
            zero_history=zero_history,
            acuity=acuity,
            frailty=frailty,
        )

        if spo2_bias:
            traj = apply_spo2_bias(traj, offset_mean=2.5, rng=rng)

        if mech in ("sensor_failure", "staff_shortage"):
            traj = apply_missingness(
                traj,
                MissingnessSpec(
                    mechanism=mech,
                    affected_vitals=["all"] if mech == "staff_shortage"
                    else list(rng.choice(VITALS, size=2, replace=False)),
                    probability=0.45,
                ),
                rng,
            )

        sev = traj.latent.severity_path
        lab = derive_labels(sev, frailty, rng, spec)

        s_max_all.append(lab.s_max_future)
        s_mean_all.append(lab.s_mean_future)
        frailty_all.append(frailty)

        staged.append({
            "patient_id": traj.patient_id,
            "condition_id": cid,
            "stratum": stratum,
            "stratum_is_fallback": False,   # only defined pairs are sampled
            "age_days": age_days,
            "k_step": lab.k_step,
            "missingness": mech or "none",
            "spo2_bias_risk": spo2_bias,
            "stale_vitals_hours": stale_hours,
            "zero_history": zero_history,
            "s_max_future": lab.s_max_future,
            "s_mean_future": lab.s_mean_future,
            "frailty": frailty,
            "acuity": acuity,
            LABEL_NAME_SECONDARY: lab.derangement,
            "trajectory": traj.as_dict(),
        })

    s_max_arr = np.array(s_max_all)
    s_mean_arr = np.array(s_mean_all)
    frailty_arr = np.array(frailty_all)

    if solve_prevalence:
        spec = LabelSpec(**{**spec.as_dict(),
                            "beta0": solve_beta0(s_max_arr, s_mean_arr, frailty_arr, spec)})

    # Second pass: draw outcomes under the solved intercept.
    rng2 = np.random.default_rng(seed + 1)
    lin = spec.beta1 * s_max_arr + spec.beta2 * s_mean_arr + spec.beta3 * frailty_arr
    p_event = 1.0 / (1.0 + np.exp(-(spec.beta0 + lin)))
    outcomes = (rng2.random(len(p_event)) < p_event).astype(int)

    for rec, p, y in zip(staged, p_event, outcomes):
        rec["p_event"] = float(p)
        rec[LABEL_NAME_PRIMARY] = int(y)

    meta = {
        "n": n,
        "seed": seed,
        "prevalence": float(outcomes.mean()),
        "mean_p_event": float(p_event.mean()),
        "beta0_solved": float(spec.beta0),
        "n_defined_pairs": len(pairs),
        "horizon_minutes": 180,
        "label_primary": LABEL_NAME_PRIMARY,
        "label_secondary": LABEL_NAME_SECONDARY,
    }
    return staged, spec, meta


def write_jsonl(records: list[dict], out: pathlib.Path) -> None:
    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        for r in records:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")


def main() -> None:
    ap = argparse.ArgumentParser(description="Generate the MediPilot training set.")
    ap.add_argument("--n", type=int, default=20000)
    ap.add_argument("--seed", type=int, default=1337)
    ap.add_argument("--out", type=str, default="data/train_set.jsonl")
    args = ap.parse_args()

    records, spec, meta = generate_dataset(n=args.n, seed=args.seed)
    out = pathlib.Path(args.out)
    write_jsonl(records, out)

    meta_path = out.with_suffix(".meta.json")
    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump({"meta": meta, "label_spec": spec.as_dict()}, f, indent=2)

    print(f"Wrote {len(records)} records -> {out}")
    print(f"  prevalence      : {meta['prevalence']:.4f} (target "
          f"{spec.target_prevalence:.3f})")
    print(f"  beta0 solved    : {meta['beta0_solved']:.4f}")
    print(f"  defined pairs   : {meta['n_defined_pairs']}")
    print(f"  meta            -> {meta_path}")


if __name__ == "__main__":
    main()
