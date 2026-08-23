"""
medipilot-model/model/artifact.py

Artifact loading, version guards, and the fallback contract.

The whitepaper promises "model service outage -> hard fallback to the frozen
AIIMS-ATP rule card; the UI never presents a blank state." This module is where
that promise is kept: every failure mode below degrades to the hand-coded
scorer rather than raising into the triage API.

Fallback triggers (all of them produce score_source="fallback_heuristic"):
  1. artifact directory absent
  2. manifest unreadable or schema mismatch
  3. sklearn version mismatch (pickles are not portable across versions)
  4. artifact feature_version != code FEATURE_VERSION
  5. artifact feature_names != code feature_names() (order-sensitive)
  6. any exception during predict at serve time

Trigger 4/5 are the important ones: they are the mechanical guard against
serving a model whose feature contract has silently drifted from the extractor
that now builds its inputs.
"""

from __future__ import annotations

import json
import pathlib
import threading
from dataclasses import dataclass, field
from typing import Any, Optional

import sklearn

_ROOT = pathlib.Path(__file__).parent / "artifacts"

_FALLBACK_MODEL_VERSION = "medipilot-heuristic-v0.1.0"
_FALLBACK_CALIBRATION_VERSION = "config-stratum-v0.1.0"

_lock = threading.Lock()
_cached: Optional["Artifact"] = None
_load_attempted = False
_load_reason = "not_attempted"

# Counts serve-time predict failures so /model-status can report them. A model
# exception must never 500 the triage API, but it must also never be invisible.
_fallback_counter = {"predict_errors": 0}


@dataclass
class Artifact:
    path: pathlib.Path
    manifest: dict
    clf: Any
    aux: Any
    calibrators: dict
    methods: dict
    conformal: dict
    thresholds: dict
    feature_names: tuple[str, ...] = field(default_factory=tuple)

    @property
    def model_version(self) -> str:
        return self.manifest.get("model_version", _FALLBACK_MODEL_VERSION)

    @property
    def calibration_version(self) -> str:
        return self.manifest.get("calibration_version", _FALLBACK_CALIBRATION_VERSION)

    @property
    def feature_version(self) -> str:
        return self.manifest.get("feature_version", "unknown")


def _resolve_dir(root: pathlib.Path) -> Optional[pathlib.Path]:
    if not root.exists():
        return None
    pointer = root / "current.txt"
    if pointer.exists():
        name = pointer.read_text(encoding="utf-8").strip()
        cand = root / name
        if (cand / "manifest.json").exists():
            return cand
    dirs = [d for d in root.iterdir() if d.is_dir() and (d / "manifest.json").exists()]
    if not dirs:
        return None
    return sorted(dirs, key=lambda d: d.stat().st_mtime)[-1]


def _load(root: pathlib.Path) -> tuple[Optional[Artifact], str]:
    from model.features import FEATURE_VERSION, feature_names

    d = _resolve_dir(root)
    if d is None:
        return None, "artifact_directory_absent"

    try:
        manifest = json.loads((d / "manifest.json").read_text(encoding="utf-8"))
    except Exception as e:
        return None, f"manifest_unreadable: {type(e).__name__}"

    art_sklearn = manifest.get("sklearn_version")
    if art_sklearn and art_sklearn != sklearn.__version__:
        return None, (
            f"sklearn_version_mismatch: artifact={art_sklearn} "
            f"runtime={sklearn.__version__}"
        )

    if manifest.get("feature_version") != FEATURE_VERSION:
        return None, (
            f"feature_version_mismatch: artifact={manifest.get('feature_version')} "
            f"code={FEATURE_VERSION}"
        )

    try:
        spec = json.loads((d / "feature_spec.json").read_text(encoding="utf-8"))
        names = tuple(spec.get("feature_names", []))
    except Exception as e:
        return None, f"feature_spec_unreadable: {type(e).__name__}"

    if names != tuple(feature_names()):
        return None, "feature_names_mismatch"

    try:
        import joblib
        clf = joblib.load(d / "primary.joblib")
        aux = joblib.load(d / "auxiliary.joblib")
        iso = joblib.load(d / "isotonic.joblib")
        conformal = json.loads((d / "conformal.json").read_text(encoding="utf-8"))
        thresholds = json.loads((d / "thresholds.json").read_text(encoding="utf-8"))
    except Exception as e:
        return None, f"artifact_load_failed: {type(e).__name__}: {e}"

    return Artifact(
        path=d, manifest=manifest, clf=clf, aux=aux,
        calibrators=iso["calibrators"], methods=iso["methods"],
        conformal=conformal, thresholds=thresholds, feature_names=names,
    ), "loaded"


def get_artifact(root: Optional[pathlib.Path] = None, force_reload: bool = False) -> Optional[Artifact]:
    """Cached artifact accessor. Returns None when the model is unavailable."""
    global _cached, _load_attempted, _load_reason
    with _lock:
        if force_reload:
            _cached, _load_attempted = None, False
        if not _load_attempted:
            _cached, _load_reason = _load(root or _ROOT)
            _load_attempted = True
        return _cached


def artifact_status() -> dict:
    """
    Answers "are we running the model or the heuristic right now?" — a
    shadow-mode requirement, not a nicety.
    """
    art = get_artifact()
    return {
        "loaded": art is not None,
        "reason": _load_reason,
        "model_version": art.model_version if art else _FALLBACK_MODEL_VERSION,
        "calibration_version": art.calibration_version if art else _FALLBACK_CALIBRATION_VERSION,
        "feature_version": art.feature_version if art else None,
        "artifact_path": str(art.path) if art else None,
        "predict_errors": _fallback_counter["predict_errors"],
    }


def current_versions() -> tuple[str, str]:
    art = get_artifact()
    if art is None:
        return _FALLBACK_MODEL_VERSION, _FALLBACK_CALIBRATION_VERSION
    return art.model_version, art.calibration_version


def note_predict_error() -> None:
    _fallback_counter["predict_errors"] += 1
