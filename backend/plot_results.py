import pathlib
import json
import numpy as np
import matplotlib.pyplot as plt
import joblib
from sklearn.metrics import roc_curve, precision_recall_curve, auc
import sys

# Load artifact
d = pathlib.Path("model/artifacts/medipilot-gbdt-v0.2.0")
if not d.exists():
    print("Artifact not found!")
    sys.exit(1)

test = np.load(d / "test_split.npz", allow_pickle=True)
X, y, strata = test["X"], test["y"], test["strata"]

clf = joblib.load(d / "primary.joblib")
iso = joblib.load(d / "isotonic.joblib")
spec = json.loads((d / "feature_spec.json").read_text(encoding="utf-8"))

sel = spec.get("selected_feature_indices") or list(range(X.shape[1]))
p_raw = clf.predict_proba(X[:, sel])[:, 1]

# Re-implement calibration apply
p = np.empty_like(p_raw, dtype=float)
calibrators = iso["calibrators"]
methods = iso["methods"]
n_max = max(len(p_raw), 2)

for i, (pr, s) in enumerate(zip(p_raw, strata)):
    method = methods.get(str(s), "pooled_fallback")
    cal = calibrators.get(str(s)) if method != "pooled_fallback" else calibrators["__pooled__"]
    if cal is None:
        cal = calibrators["__pooled__"]
        method = "isotonic"
    if method == "platt":
        pc = float(np.clip(pr, 1e-6, 1 - 1e-6))
        z = np.log(pc / (1 - pc))
        p[i] = float(cal.predict_proba(np.array([[z]]))[0, 1])
    else:
        p[i] = float(cal.predict(np.array([pr]))[0])
p = np.clip(p, 1.0 / (2 * n_max), 1.0 - 1.0 / (2 * n_max))

# 1. Plot ROC
fpr, tpr, _ = roc_curve(y, p)
roc_auc = auc(fpr, tpr)
plt.figure(figsize=(6, 5))
plt.plot(fpr, tpr, color='darkorange', lw=2, label=f'ROC curve (area = {roc_auc:.3f})')
plt.plot([0, 1], [0, 1], color='navy', lw=2, linestyle='--')
plt.xlim([0.0, 1.0])
plt.ylim([0.0, 1.05])
plt.xlabel('False Positive Rate')
plt.ylabel('True Positive Rate')
plt.title('Receiver Operating Characteristic')
plt.legend(loc="lower right")
plt.savefig("roc_curve.png", dpi=300, bbox_inches="tight")
plt.close()

# 2. Plot PR Curve
prec, rec, _ = precision_recall_curve(y, p)
pr_auc = auc(rec, prec)
prevalence = float(y.mean())
plt.figure(figsize=(6, 5))
plt.plot(rec, prec, color='green', lw=2, label=f'PR curve (area = {pr_auc:.3f})')
plt.axhline(prevalence, color='navy', lw=2, linestyle='--', label=f'Prevalence ({prevalence:.3f})')
plt.xlim([0.0, 1.0])
plt.ylim([0.0, 1.05])
plt.xlabel('Recall (Sensitivity)')
plt.ylabel('Precision (PPV)')
plt.title('Precision-Recall Curve')
plt.legend(loc="lower left")
plt.savefig("pr_curve.png", dpi=300, bbox_inches="tight")
plt.close()

# 3. Calibration Curve
from sklearn.calibration import calibration_curve
prob_true, prob_pred = calibration_curve(y, p, n_bins=10, strategy='quantile')
plt.figure(figsize=(6, 5))
plt.plot(prob_pred, prob_true, marker='o', linewidth=1, label='Calibrated model')
plt.plot([0, 1], [0, 1], linestyle='--', color='gray', label='Perfectly calibrated')
plt.xlabel('Mean predicted probability')
plt.ylabel('Fraction of positives')
plt.title('Reliability Diagram (Calibration Curve)')
plt.legend(loc="upper left")
plt.savefig("calib_curve.png", dpi=300, bbox_inches="tight")
plt.close()

print("Plots saved: roc_curve.png, pr_curve.png, calib_curve.png")
