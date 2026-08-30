# Risk Engine bake-off

Common held-out split: **20,000 rows**, prevalence 0.1028, generator seed 4242 (training used 1337, so every row is unseen by every artifact).

Produced by `python -m eval.build_bench_split` followed by `python -m model.leaderboard`. No model was retrained; the committed artifacts were scored as they are.

| model | kind | train n | AUPRC | AUROC | % of oracle AUPRC | green-miss | FNR spread | worst stratum | ECE | calib slope | conformal cov | set size | gates |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| medipilot-gbdt-v0.2.0 | hist | 20000 | 0.1637 | 0.6689 | 40.0988 | 0.0948 | 0.2050 | neonate | 0.0110 | 1.1609 | 0.9060 | 1.0820 | 7/8 |
| medipilot-hist-100k-s1337 | hist | 100000 | 0.1570 | 0.6489 | 38.4580 | 0.0375 | 0.1450 | neonate | 0.0430 | 1.7616 | 0.8986 | 1.0100 | 6/8 |
| medipilot-hist-mono-100k-s1337 | hist-mono | 100000 | 0.1566 | 0.6668 | 38.3628 | 0.0209 | 0.0795 | adolescent | 0.0351 | 1.7940 | 0.8961 | 1.0063 | 6/8 |
| medipilot-xgboost-100k-s1337 | xgboost | 100000 | 0.1549 | 0.6469 | 37.9472 | 0.0078 | 0.0284 | adolescent | 0.0729 | 0.6202 | 0.8974 | 1.0828 | 5/8 |

## Gate detail

| model | gates | failed |
| --- | --- | --- |
| medipilot-gbdt-v0.2.0 | 7/8 | beats_handcoded_baseline |
| medipilot-hist-100k-s1337 | 6/8 | conformal_coverage_ge_090, beats_handcoded_baseline |
| medipilot-hist-mono-100k-s1337 | 6/8 | conformal_coverage_ge_090, beats_handcoded_baseline |
| medipilot-xgboost-100k-s1337 | 5/8 | conformal_coverage_ge_090, ece_lt_005_where_reportable, beats_handcoded_baseline |

## Significance vs the hand-coded baseline

Under-triage compared at four fixed over-triage rates; a win/loss counts only where the bootstrap CIs separate.

| model | wins | losses | ties |
| --- | --- | --- | --- |
| medipilot-gbdt-v0.2.0 | 0.50 | 0.20 | 0.10, 0.30 |
| medipilot-hist-100k-s1337 | 0.50 | 0.30 | 0.10, 0.20 |
| medipilot-hist-mono-100k-s1337 | 0.50 | 0.20, 0.30 | 0.10 |
| medipilot-xgboost-100k-s1337 | 0.50 | - | 0.10, 0.20, 0.30 |

## Not evaluated

`medipilot-last-obs-100k-s1337` is a sequence baseline that unpickles through `model/sequence_models.py`, which imports torch at module scope. torch is installed here but its DLL fails to initialise (WinError 1114), so no row could be produced.
