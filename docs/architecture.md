# Architecture

## Overview

The SSCP Occupant-Aware Demand-Response Planner follows **Clean
Architecture**: dependencies point inward, toward the domain. The domain
layer has zero knowledge of FastAPI, PostgreSQL, or OR-Tools — it is pure
Python that could run identically in a CLI, a notebook, or a web service.

```
Presentation (FastAPI, React)
        ↓ depends on
Application (use-case services)
        ↓ depends on
Domain (entities, value objects, constraints, strategies)
        ↑ implemented by
Infrastructure (DB repositories, solver adapter, data generator)
```

Infrastructure *implements* interfaces defined in the domain/application
layers (dependency inversion) — for example, the domain defines
`DemandResponseStrategy` as an abstract contract; `OptimizedStrategy` in
infrastructure/solver fulfills it using OR-Tools underneath, but the
application layer only ever talks to the abstract contract.

## Why this shape

The project has two requirements that push directly on the architecture:

1. **"Compare at least two competing objectives"** and **"baseline vs
   intelligent planner"** — satisfied by making `BaselineStrategy` and
   `OptimizedStrategy` both implement `DemandResponseStrategy`. The
   `ComparisonService` runs both against the same `PlanningContext` and
   diffs their `Decision` lists. Neither strategy needs to know the other
   exists.

2. **"Explain every decision in simple language"** — satisfied by treating
   explanation generation as a *downstream consumer* of a structured
   `Decision` object, not something baked into the solver. The solver
   never writes English; it writes `triggering_constraint`,
   `reasoning_tags`, and `objective_weights_used`. A separate
   `ExplanationService` (Milestone 5) turns that into the sentence shown
   in the UI. This means:
   - The explanation logic is unit-testable without a solver.
   - We could later swap the template-based explainer for an LLM-based one
     without touching the optimizer at all.

## Core domain contracts

| Type | Role |
|---|---|
| `Building`, `Occupant`, `Transformer`, `Tariff`, `DemandResponseEvent` | Entities — things with identity |
| `ComfortRange`, `LoadProfile`, `Decision` | Value objects — immutable, defined by their data |
| `DemandResponseStrategy` | Abstract contract implemented by baseline and optimized planners |
| `PlanningContext` | Immutable bundle of everything a strategy needs — the only thing passed into `generate_plan()` |

## Hard vs. soft constraints

- **Hard constraints** (`domain/constraints/hard_constraints.py`) can never
  be violated by any valid plan: occupant opt-out, comfort hard bounds,
  non-negative load. Violating one raises `HardConstraintViolationError`
  and the plan is invalid.
- **Soft constraints** (`domain/constraints/soft_constraints.py`) return a
  continuous penalty in `[0, 1]` that the optimizer weighs against other
  objectives (e.g. deviating from a preferred temperature, shifting an
  appliance away from its preferred time slot). This is what makes the
  comfort/peak-reduction trade-off a real, tunable thing rather than a
  fixed rule.

## Time modeling

Time is represented as **discrete 15-minute slots** (configurable via
`SLOT_DURATION_MINUTES` in `core/config.py`). The domain layer works
entirely in slot indices, not timestamps — the mapping to wall-clock time
happens only at the API boundary. This keeps generated data,
optimization runs, and experiments independent of any specific calendar
date.

## Error handling philosophy

Every expected failure mode (missing tariff data, occupancy sensor
failure, insufficient reduction capacity, invalid sensor data,
unauthorized override) has its own exception type in
`core/exceptions.py`, inheriting from `SSCPBaseError`. The API layer maps
`SSCPBaseError` subclasses to `422` with a structured `{error_type,
detail}` body. This directly supports the Failure Mode Analysis
deliverable (Milestone 10): each documented failure scenario has a
corresponding, testable exception type from day one, not something
retrofitted at the end.
