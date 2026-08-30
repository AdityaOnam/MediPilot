# Interface Track (`web/`)

> **All data in this repository is synthetic.**

This directory houses the Next.js 16 (React 19) user interface. It represents the **Interface Track** of the MediPilot architecture.

## The Rendering Boundary
Under the system's core design philosophy, the interface is granted **no clinical authority**. It is purely a projection of the backend's state. 
- It cannot invent a clinical band. 
- It cannot manipulate the re-scoring cadence.
- The `AcuityCard` component throws a runtime error if it receives a score without a mathematically proven conformal confidence set.

## Running Locally (Mock Mode)
By default, the frontend boots in a completely standalone environment (`NEXT_PUBLIC_MP_SOURCE=mock`). It reads directly from the 20-patient synthetic seed corpus in `lib/seed/corpus.ts`. This ensures the UI demo cannot be interrupted by backend failures or missing dependencies.
