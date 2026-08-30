"""
backend/model/sequence_models.py

PyTorch sequence models for the Track C-G2 comparison.
Includes a mandatory Last-Observation Baseline, GRU, TCN, and a small Transformer.
Also provides SklearnPyTorchWrapper to allow these models to be used transparently
by the existing evaluate.py and leaderboard.py pipeline.
"""
import math
import io
import torch
import torch.nn as nn
from torch.utils.data import DataLoader, TensorDataset
from sklearn.base import BaseEstimator, ClassifierMixin
import numpy as np

# -----------------------------------------------------------------------------
# Architectures
# -----------------------------------------------------------------------------

class LastObservationBaseline(nn.Module):
    """
    Mandatory control arm: uses ONLY the last observed values (from the last valid step).
    Extracts the last step that was not padded (based on the mask or we just assume step k_step).
    Since we right-padded, we need to find the last step where the mask was active, or
    we can just pass the lengths and use gather.
    Actually, since we know padding is zeros and max length is 37, we can just find the
    index of the last non-zero step for each sequence.
    """
    def __init__(self, input_dim: int = 14, hidden_dim: int = 32):
        super().__init__()
        self.fc1 = nn.Linear(input_dim // 2, hidden_dim) # Only use the values, not the mask
        self.relu = nn.ReLU()
        self.fc2 = nn.Linear(hidden_dim, 1)
        
    def forward(self, x, lengths):
        # x is (B, T, D). We want x[b, lengths[b]-1, :7]
        B = x.size(0)
        idx = (lengths - 1).clamp(min=0).view(-1, 1, 1).expand(B, 1, 7)
        # Extract only the 7 vital values (ignore masks)
        x_last = torch.gather(x[:, :, :7], 1, idx).squeeze(1)
        
        out = self.fc1(x_last)
        out = self.relu(out)
        out = self.fc2(out).squeeze(-1)
        return out


class GRURiskModel(nn.Module):
    def __init__(self, input_dim: int = 14, hidden_dim: int = 32, num_layers: int = 1):
        super().__init__()
        self.gru = nn.GRU(input_dim, hidden_dim, num_layers, batch_first=True)
        self.fc = nn.Linear(hidden_dim, 1)
        
    def forward(self, x, lengths):
        # x: (B, T, D)
        packed = nn.utils.rnn.pack_padded_sequence(x, lengths.cpu(), batch_first=True, enforce_sorted=False)
        _, h_n = self.gru(packed)
        # h_n is (num_layers, B, hidden_dim)
        last_h = h_n[-1]
        out = self.fc(last_h).squeeze(-1)
        return out


class Chomp1d(nn.Module):
    def __init__(self, chomp_size):
        super().__init__()
        self.chomp_size = chomp_size

    def forward(self, x):
        return x[:, :, :-self.chomp_size].contiguous()

class TCNRiskModel(nn.Module):
    """
    Temporal Convolutional Network (Bai et al.)
    Using dilated causal convolutions.
    """
    def __init__(self, input_dim: int = 14, num_channels: list = [32, 32], kernel_size: int = 3):
        super().__init__()
        layers = []
        num_levels = len(num_channels)
        for i in range(num_levels):
            dilation_size = 2 ** i
            in_channels = input_dim if i == 0 else num_channels[i-1]
            out_channels = num_channels[i]
            padding = (kernel_size - 1) * dilation_size
            
            layers += [
                nn.Conv1d(in_channels, out_channels, kernel_size, stride=1, padding=padding, dilation=dilation_size),
                Chomp1d(padding),
                nn.ReLU(),
                nn.Dropout(0.2)
            ]
        self.network = nn.Sequential(*layers)
        self.fc = nn.Linear(num_channels[-1], 1)
        
    def forward(self, x, lengths):
        # x: (B, T, D) -> (B, D, T) for Conv1d
        x = x.transpose(1, 2)
        out = self.network(x) # (B, out_channels, T)
        # Gather the output at the last valid time step
        B = out.size(0)
        idx = (lengths - 1).clamp(min=0).view(B, 1, 1).expand(B, out.size(1), 1)
        last_out = torch.gather(out, 2, idx).squeeze(-1)
        return self.fc(last_out).squeeze(-1)


class TransformerRiskModel(nn.Module):
    """
    A small Transformer model for time series (SAnD style).
    """
    def __init__(self, input_dim: int = 14, d_model: int = 32, n_heads: int = 4, num_layers: int = 2):
        super().__init__()
        self.embedding = nn.Linear(input_dim, d_model)
        self.pos_encoder = nn.Parameter(torch.zeros(1, 40, d_model)) # Max len 37
        encoder_layer = nn.TransformerEncoderLayer(d_model=d_model, nhead=n_heads, batch_first=True, dim_feedforward=64)
        self.transformer = nn.TransformerEncoder(encoder_layer, num_layers=num_layers)
        self.fc = nn.Linear(d_model, 1)
        
    def forward(self, x, lengths):
        # x: (B, T, D)
        B, T, _ = x.size()
        emb = self.embedding(x) + self.pos_encoder[:, :T, :]
        
        # Create src_key_padding_mask: True where padded (to ignore)
        mask = torch.arange(T, device=x.device).unsqueeze(0).expand(B, T)
        src_key_padding_mask = mask >= lengths.unsqueeze(1)
        
        out = self.transformer(emb, src_key_padding_mask=src_key_padding_mask)
        
        # Extract the representation of the last valid token
        idx = (lengths - 1).clamp(min=0).view(B, 1, 1).expand(B, 1, out.size(2))
        last_out = torch.gather(out, 1, idx).squeeze(1)
        
        return self.fc(last_out).squeeze(-1)

# -----------------------------------------------------------------------------
# Sklearn Wrapper
# -----------------------------------------------------------------------------

class SklearnPyTorchWrapper(BaseEstimator, ClassifierMixin):
    """
    Wraps a PyTorch model so it can be used directly by sklearn calibration,
    evaluate.py, and leaderboard.py.
    """
    def __init__(self, model_class, model_kwargs=None):
        self.model_class = model_class
        self.model_kwargs = model_kwargs or {}
        self.model = None
        self.is_sequence_model = True  # Marker for evaluate.py
        
    def fit(self, X_seq, y):
        # Training is handled in train_seq.py. This wrapper is primarily for inference.
        pass
        
    def predict_proba(self, X_seq):
        """
        Returns probabilities of class 1. X_seq shape: (N, T, D)
        """
        if self.model is None:
            raise RuntimeError("Model is not initialized or weights not loaded.")
            
        self.model.eval()
        
        # Determine lengths from masks (assume features 7-13 are masks, sum over features)
        # Mask is 0 when missing. The step was masked out completely if all masks are 0.
        # Wait, if all vitals are missing, mask is 0.
        # We can just check where all features + masks are 0.
        masks_sum = np.sum(X_seq[:, :, 7:], axis=2)
        # lengths is the index of the last non-zero mask + 1. 
        # If a sequence has all zeros, length is 1.
        # A robust way is to check the padding. X_seq was zero-padded beyond k_step.
        # So we can just check if the entire vector is 0.
        lengths = np.zeros(X_seq.shape[0], dtype=np.int64)
        for i in range(X_seq.shape[0]):
            nz = np.where(np.abs(X_seq[i]).sum(axis=1) > 0)[0]
            lengths[i] = nz[-1] + 1 if len(nz) > 0 else 1
            
        tensor_x = torch.tensor(X_seq, dtype=torch.float32)
        tensor_lens = torch.tensor(lengths, dtype=torch.int64)
        
        dataset = TensorDataset(tensor_x, tensor_lens)
        loader = DataLoader(dataset, batch_size=256, shuffle=False)
        
        probs = []
        with torch.no_grad():
            for bx, blens in loader:
                logits = self.model(bx, blens)
                p = torch.sigmoid(logits).cpu().numpy()
                probs.append(p)
                
        p1 = np.concatenate(probs)
        # Return (N, 2) array like sklearn
        out = np.zeros((len(p1), 2), dtype=np.float32)
        out[:, 1] = p1
        out[:, 0] = 1.0 - p1
        return out
        
    def __getstate__(self):
        state = self.__dict__.copy()
        if self.model is not None:
            buffer = io.BytesIO()
            torch.save(self.model.state_dict(), buffer)
            state['model_state_dict'] = buffer.getvalue()
        del state['model']
        return state
        
    def __setstate__(self, state):
        model_state_dict = state.pop('model_state_dict', None)
        self.__dict__.update(state)
        self.model = self.model_class(**self.model_kwargs)
        if model_state_dict is not None:
            buffer = io.BytesIO(model_state_dict)
            self.model.load_state_dict(torch.load(buffer, map_location='cpu'))
