

### Model Bake-off Update
We successfully evaluated XGBoost and HistGBDT with monotonic constraints on the 100k dataset. The results show that while XGBoost passed all gates, it slightly underperformed the unconstrained HistGBDT on AUPRC. Hist-Mono failed one of the 8 honesty gates, disqualifying it. The unconstrained HistGBDT trained on 100k records (seed 1337) remains the top model.
