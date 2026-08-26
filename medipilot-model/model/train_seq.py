"""
medipilot-model/model/train_seq.py

Training script for Track C-G2 Sequence Models.
Replicates the calibration, conformal, and threshold pipeline from train.py
but uses PyTorch sequence models.
"""
import argparse
import pathlib
import json
import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import DataLoader, TensorDataset
import numpy as np
import joblib

from sklearn.model_selection import train_test_split

from model.train import (
    ARTIFACT_ROOT, load_dataset, build_matrices, _stratified_split,
    fit_isotonic_per_stratum, apply_calibration, mondrian_conformal_quantiles,
    solve_thresholds, solve_per_stratum_thresholds, FEATURE_NAMES, N_FEATURES
)
from model.sequence_data import build_sequence_matrices
from model.sequence_models import (
    LastObservationBaseline, GRURiskModel, TCNRiskModel, TransformerRiskModel,
    SklearnPyTorchWrapper
)
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.model_selection import cross_val_predict

MODEL_CLASSES = {
    "last-obs": LastObservationBaseline,
    "gru": GRURiskModel,
    "tcn": TCNRiskModel,
    "transformer": TransformerRiskModel,
}

def train_pytorch_model(model_class, X_seq, y, tr_idx, seed=1337, batch_size=256, max_epochs=50, patience=5):
    # Determine sequence lengths
    lengths = np.zeros(X_seq.shape[0], dtype=np.int64)
    for i in range(X_seq.shape[0]):
        nz = np.where(np.abs(X_seq[i]).sum(axis=1) > 0)[0]
        lengths[i] = nz[-1] + 1 if len(nz) > 0 else 1

    # Split tr_idx into train and internal validation
    tr2_idx, val2_idx = train_test_split(tr_idx, test_size=0.15, random_state=seed, stratify=y[tr_idx])

    X_tr = torch.tensor(X_seq[tr2_idx], dtype=torch.float32)
    len_tr = torch.tensor(lengths[tr2_idx], dtype=torch.int64)
    y_tr = torch.tensor(y[tr2_idx], dtype=torch.float32)
    
    X_val = torch.tensor(X_seq[val2_idx], dtype=torch.float32)
    len_val = torch.tensor(lengths[val2_idx], dtype=torch.int64)
    y_val = torch.tensor(y[val2_idx], dtype=torch.float32)
    
    train_ds = TensorDataset(X_tr, len_tr, y_tr)
    train_loader = DataLoader(train_ds, batch_size=batch_size, shuffle=True)
    
    val_ds = TensorDataset(X_val, len_val, y_val)
    val_loader = DataLoader(val_ds, batch_size=batch_size, shuffle=False)
    
    model = model_class()
    
    # Asymmetric loss: upweight positives by 3.0 during training as in train.py
    pos_weight = torch.tensor([3.0])
    criterion = nn.BCEWithLogitsLoss(pos_weight=pos_weight)
    optimizer = optim.Adam(model.parameters(), lr=1e-3, weight_decay=1e-4)
    
    best_val_loss = float('inf')
    best_state = None
    epochs_no_improve = 0
    
    for epoch in range(max_epochs):
        model.train()
        for bx, blens, by in train_loader:
            optimizer.zero_grad()
            logits = model(bx, blens)
            loss = criterion(logits, by)
            loss.backward()
            optimizer.step()
            
        model.eval()
        val_loss = 0.0
        with torch.no_grad():
            for bx, blens, by in val_loader:
                logits = model(bx, blens)
                val_loss += criterion(logits, by).item() * bx.size(0)
        val_loss /= len(val2_idx)
        
        if val_loss < best_val_loss:
            best_val_loss = val_loss
            best_state = model.state_dict()
            epochs_no_improve = 0
        else:
            epochs_no_improve += 1
            if epochs_no_improve >= patience:
                break
                
    model.load_state_dict(best_state)
    
    wrapper = SklearnPyTorchWrapper(model_class)
    wrapper.model = model
    return wrapper

def train_models(data_path: pathlib.Path, seed: int = 1337, out_root: pathlib.Path = ARTIFACT_ROOT,
                 model_kinds: list = None) -> list:
    import time
    print(f"Loading dataset from {data_path}...")
    t0 = time.time()
    records = load_dataset(data_path)
    print(f"Loaded {len(records)} records in {time.time()-t0:.1f}s.")
    
    print("Building flat matrices...")
    t0 = time.time()
    X, y, y_aux, strata, pids, s_max = build_matrices(records)
    print(f"Built flat matrices in {time.time()-t0:.1f}s.")
    
    print("Building sequence matrices...")
    t0 = time.time()
    X_seq = build_sequence_matrices(records)
    print(f"Built sequence matrices in {time.time()-t0:.1f}s.")
    
    print("Splitting data...")
    tr, iso_idx, conf_idx, test_idx = _stratified_split(y, strata, seed)
    
    print("Training auxiliary head...")
    aux = HistGradientBoostingRegressor(max_iter=200, random_state=seed)
    oof = cross_val_predict(aux, X[tr], y_aux[tr], cv=5, method="predict")
    aux.fit(X[tr], y_aux[tr])
    
    aux_col = FEATURE_NAMES.index("aux_derangement_oof")
    for idx in (iso_idx, conf_idx, test_idx):
        X[idx, aux_col] = aux.predict(X[idx])

    if not model_kinds:
        model_kinds = ["last-obs"]
    if "all" in model_kinds:
        model_kinds = list(MODEL_CLASSES.keys())

    results = []
    
    for kind in model_kinds:
        print(f"\n======================================")
        print(f"Training sequence model: {kind}")
        print(f"======================================")
        model_class = MODEL_CLASSES[kind]
        t0 = time.time()
        clf = train_pytorch_model(model_class, X_seq, y, tr, seed=seed)
        print(f"Trained {kind} in {time.time()-t0:.1f}s.")

        def _pred_raw(idx):
            return clf.predict_proba(X_seq[idx])[:, 1]

        # --- calibration, conformal, thresholds ---
        p_iso_raw = _pred_raw(iso_idx)
        calibrators, methods = fit_isotonic_per_stratum(p_iso_raw, y[iso_idx], strata[iso_idx])

        p_conf_raw = _pred_raw(conf_idx)
        p_conf = apply_calibration(calibrators, methods, p_conf_raw, strata[conf_idx])
        conformal = mondrian_conformal_quantiles(p_conf, y[conf_idx], strata[conf_idx])
        thresholds = solve_thresholds(p_conf, y[conf_idx])
        thresholds["per_stratum"] = solve_per_stratum_thresholds(
            p_conf, y[conf_idx], strata[conf_idx]
        )

        # --- persist ---
        artifact_name = f"medipilot-{kind}-100k-s{seed}"
        out = out_root / artifact_name
        out.mkdir(parents=True, exist_ok=True)
        
        joblib.dump(clf, out / "primary.joblib", compress=3)
        joblib.dump(aux, out / "auxiliary.joblib", compress=3)
        joblib.dump({"calibrators": calibrators, "methods": methods},
                    out / "isotonic.joblib", compress=3)
        (out / "conformal.json").write_text(json.dumps(conformal, indent=2), encoding="utf-8")
        (out / "thresholds.json").write_text(json.dumps(thresholds, indent=2), encoding="utf-8")
        
        # Write feature spec for compatibility
        (out / "feature_spec.json").write_text(json.dumps({
            "feature_version": "seq-v1",
            "selected_feature_indices": list(range(N_FEATURES)),
            "is_sequence_model": True
        }, indent=2), encoding="utf-8")

        # SAVE test_split.npz WITH X_seq INCLUDED!
        np.savez_compressed(
            out / "test_split.npz",
            X=X[test_idx], y=y[test_idx], strata=strata[test_idx].astype(str),
            y_aux=y_aux[test_idx], s_max=s_max[test_idx],
            X_seq=X_seq[test_idx]
        )
        print(f"Artifact saved to {out}")
        results.append(str(out))

    return results

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default="data/train_set_100k.jsonl")
    ap.add_argument("--seed", type=int, default=1337)
    ap.add_argument("--models", nargs="+", default=["last-obs"], help="Model architectures or 'all'")
    args = ap.parse_args()

    dirs = train_models(
        pathlib.Path(args.data), seed=args.seed, model_kinds=args.models
    )
    print(f"Finished training sequence models.")
