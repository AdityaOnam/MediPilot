# Risk Engine (`backend/model/`)

> **All data in this repository is synthetic.**

This directory contains the machine learning pipelines used to classify parsed encounter records into risk bands, taking strictly into account age strata.

## Core Features
1. **Conformal Prediction:** The model output is structurally forbidden from being a "naked score." Every risk value is accompanied by a mathematically sound conformal confidence set.
2. **Age Stratification:** Enforces **Invariant 3**. The model never assumes age. A patient of unknown age is mapped to the most conservative pediatric/geriatric safety stratum until a nurse resolves it.
3. **Out-of-Distribution (OOD) Gate:** The model refuses to score any patient presentation that deviates from the local synthetic distribution. It explicitly abstains and locks the patient at a Yellow floor (forcing human clinician review).
