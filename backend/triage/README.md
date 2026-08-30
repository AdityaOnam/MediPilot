# Orchestrator and Triage Logic (`backend/triage/`)

> **All data in this repository is synthetic.**

This module houses the central nervous system of the prototype. It is responsible for safely elevating patient priority, managing queue re-measurement cadences, and providing a mathematically provable audit trail.

## Key Components

1. **`band_engine.py`:** Enforces **Invariant 1: Asymmetric Autonomy**. The system may raise a band autonomously but may never lower a band below a human-assigned level. The engine throws an `AsymmetricAutonomyViolation` if any downstream module attempts to lower a priority.
2. **`audit_log.py`:** Provides an append-only, SHA-256 chained ledger. Every override, state change, and acuity escalation is permanently anchored to prevent retroactive alteration.
3. **`recheck_scheduler.py`:** Implements the dual-clock architecture. Re-scoring runs continuously; re-measurement relies on human nurses and is strictly rationed by wait ceilings.
4. **`surge_controller.py`:** Automatically dilates Green and Yellow wait ceilings during simulated hospital load, whilst refusing to stretch Red SLAs.
