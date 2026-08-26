"""
medipilot-model/model/sequence_data.py

Extracts sequence tensors from the raw patient trajectories.
Pads sequences to MAX_LEN, extracts 7 core vitals, forward-fills missing values,
and appends 7 missingness-mask channels (resulting in D=14).
"""
import datetime
import numpy as np

VITALS = ("hr", "rr", "bp_sys", "spo2", "temp_c", "gcs", "pain_score")
MAX_LEN = 37
N_SEQ_FEATURES = len(VITALS) * 2  # 7 values + 7 masks

def build_sequence_matrices(records: list[dict], max_len: int = MAX_LEN) -> np.ndarray:
    """
    Builds a tensor of shape (N, max_len, N_SEQ_FEATURES) from the records.
    For each patient, we use `k_step` to determine the visible sequence length.
    Readings at step > k_step are masked out (0s).
    Missing vitals at valid steps are forward-filled, but their mask channel is 0.
    """
    N = len(records)
    X_seq = np.zeros((N, max_len, N_SEQ_FEATURES), dtype=np.float32)

    for i, r in enumerate(records):
        traj = r.get("trajectory", {})
        series = traj.get("series", {})
        t0_iso = traj.get("t0")
        if not t0_iso:
            continue
            
        t0 = datetime.datetime.fromisoformat(t0_iso)
        k_step = min(r.get("k_step", max_len - 1), max_len - 1)
        
        # Track last known value for forward fill
        last_val = {v: 0.0 for v in VITALS}
        
        # Pre-group readings by time step offset
        # A step is (timestamp - t0) // 5 minutes
        step_readings = {step: {} for step in range(max_len)}
        for v in VITALS:
            for reading in series.get(v, []):
                ts = datetime.datetime.fromisoformat(reading["timestamp"])
                minutes_diff = (ts - t0).total_seconds() / 60.0
                step = int(round(minutes_diff / 5.0))
                if 0 <= step < max_len:
                    step_readings[step][v] = reading["value"]
        
        for step in range(k_step + 1):
            for v_idx, v in enumerate(VITALS):
                val_idx = v_idx
                mask_idx = v_idx + len(VITALS)
                
                if v in step_readings[step]:
                    # Observation present
                    val = step_readings[step][v]
                    last_val[v] = val
                    X_seq[i, step, val_idx] = val
                    X_seq[i, step, mask_idx] = 1.0
                else:
                    # Observation missing -> forward fill
                    X_seq[i, step, val_idx] = last_val[v]
                    X_seq[i, step, mask_idx] = 0.0
                    
    return X_seq

def build_sequence_from_patient_record(record, max_len: int = MAX_LEN) -> np.ndarray:
    X_seq = np.zeros((1, max_len, N_SEQ_FEATURES), dtype=np.float32)
    t0_iso = record.arrived_at if record.arrived_at else None
    if not t0_iso:
        return X_seq
    t0 = datetime.datetime.fromisoformat(t0_iso)
    if t0.tzinfo is None:
        t0 = t0.replace(tzinfo=datetime.timezone.utc)

    # We don't have k_step for a live patient. We just map all available readings to steps.
    step_readings = {step: {} for step in range(max_len)}
    max_step_seen = 0
    
    if record.vitals_history:
        for v in VITALS:
            for tup in record.vitals_history.get(v, []):
                val, ts_iso, _, _ = tup
                ts = datetime.datetime.fromisoformat(ts_iso)
                if ts.tzinfo is None:
                    ts = ts.replace(tzinfo=datetime.timezone.utc)
                minutes_diff = (ts - t0).total_seconds() / 60.0
                step = int(round(minutes_diff / 5.0))
                if 0 <= step < max_len:
                    step_readings[step][v] = val
                    max_step_seen = max(max_step_seen, step)

    last_val = {v: 0.0 for v in VITALS}
    for step in range(max_step_seen + 1):
        for v_idx, v in enumerate(VITALS):
            val_idx, mask_idx = v_idx, v_idx + len(VITALS)
            if v in step_readings[step]:
                last_val[v] = step_readings[step][v]
                X_seq[0, step, val_idx] = last_val[v]
                X_seq[0, step, mask_idx] = 1.0
            else:
                X_seq[0, step, val_idx] = last_val[v]
                X_seq[0, step, mask_idx] = 0.0
                
    return X_seq
