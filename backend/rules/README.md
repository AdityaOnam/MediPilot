# Safety Floors (`backend/rules/`)

> **All data in this repository is synthetic.**

This directory houses the deterministic safety floors. These are strictly non-ML code blocks that guard against known failure modes of statistical inference.

## The Red Flag Engine
A bilingual (English/Hindi) offline phrase table that detects critical vocabulary unconditionally.
- When a red flag fires, all clinical questioning stops, the acuity is escalated to Red, and a nurse is summoned immediately.
- It sits below the model evaluation layer. It does not rely on network connectivity, avoiding delayed inference during urgent scenarios (e.g. crushing chest pain).

## SpO2 Bias Guard
An invariant check that refuses to use SpO2 as a de-escalation factor. It structurally asserts that a normal pulse-oximeter reading cannot override a distressed patient's self-reported urgency.
