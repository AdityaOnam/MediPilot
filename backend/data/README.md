# Synthetic Generation Pipeline (`backend/data/`)

> **All data in this repository is synthetic.**

Under India’s DPDP Act 2023, patient data must not leave the institution. Therefore, this repository relies entirely on a generated dataset.

## The Generation Philosophy
This is not a dump of raw LLM outputs. To avoid circular labeling loops (where the model learns its own biases rather than clinical realities), the generator uses:
1. Hardcoded, clinical dependency graphs.
2. Stratified parameter sampling (e.g. realistic heart rate ranges injected with systematic noise).
3. Synthetic patient narratives anchored strictly to the sampled physiological parameters.

## The Demo Corpus
`corpus_20.json` contains 20 curated test patients, hand-engineered to provoke every extreme boundary of the triage engine (neonates with fevers, red-flag phrases, OOD abstentions). Each record demonstrates exactly one safety behavior.

## The 100k Training Corpus
The full dataset used to train and calibrate the risk engine is available as a compressed archive: `train_set_100k.zip`. It contains 100,000 synthetically generated patient encounters, fully preserving the strict clinical dependencies and age stratification logic outlined above.
