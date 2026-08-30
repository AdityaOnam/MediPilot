# Benchmarking and Evaluation (`backend/eval/`)

> **All data in this repository is synthetic.**

This directory holds the bake-off harnesses used to structurally prove the reliability of the perception layer before trusting it to parse patient complaints.

## Measured Architectures
The evaluation modules pit various LLMs (`groq:openai/gpt-oss-120b`, `groq:openai/gpt-oss-20b`, `local:Qwen2.5-3B-Instruct`) against deterministic baselines across adversarial splits (Hinglish, heavy negations, pediatric cases, and obstetric scenarios).

The goal is to measure:
1. **Symptom F1 Score:** Precision and recall of extracted terminology against the structured schema.
2. **Red Flags Missed:** The single most critical metric. Any structurer failing this metric is structurally discarded in favor of the rule-based safety floors.
3. **Schema Failures:** The frequency of OOD hallucination.

Results of these bake-offs are tabulated in `docs/benchmarks/`.
