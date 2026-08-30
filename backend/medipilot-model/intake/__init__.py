"""
MediPilot Stage 2 — Intake conversation subsystem.

Implements M03 (intake branch), M04 (question tree), M05 (speech &
multilingual adapter), M06 (LLM structurer) and clean interfaces to
M07 (red-flag pass), M08 (age stratification) and M09 (reliability
weighting), per round2-implementation-plan.html.

Scope boundary: this package collects and structures intake information.
It never assigns Red/Yellow/Green and never runs the global risk model
(M10-M14) — those are explicitly out of scope for Stage 2.
"""
