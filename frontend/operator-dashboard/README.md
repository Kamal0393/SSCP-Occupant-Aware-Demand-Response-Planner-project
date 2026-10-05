# Gridwise Operator Console

React, TypeScript, and Vite interface for the occupant-aware demand response planner. All dashboard values and planning outputs are loaded from the FastAPI backend; the UI does not generate optimization results.

## Start the backend

From the repository root, activate the backend environment and start FastAPI:

```powershell
cd backend
- [x] Clean Architecture skeleton (domain / application / infrastructure / api)
- [x] Domain entities: `Building`, `Occupant`, `Transformer`, `Tariff`, `DemandResponseEvent`
- [x] Value objects: `ComfortRange`, `LoadProfile`, `Decision`
- [x] Hard and soft constraint modules
- [x] `DemandResponseStrategy` abstract interface (baseline/optimized contract)
- [x] FastAPI backend with structured logging and domain-aware error handling
- [x] Docker Compose (backend + PostgreSQL + frontend)
- [x] Unit, solver, API, database, repository, synthetic-data, planning, optimization, and override tests
- [x] Transformer overload detection using transformer and load-profile inputs
- [x] Baseline versus optimized demand-response planning
- [x] Peak reduction, comfort, and tariff trade-off analysis
- [x] Hard comfort bounds, fixed/non-flexible loads, and occupant opt-outs
- [x] Authorized emergency override for occupants with explicit consent
- [x] Persistence of source data, plans, decisions, explanations, and planning history

## Build

```powershell
npm run build
npm run preview
```

The console provides a live network dashboard, resource views, event planning, baseline/optimized comparison, decision explanations, audited emergency override, and persisted planning history. A plan requires persisted occupant comfort ranges. Emergency override additionally requires an active DR event, an overloaded transformer, operator token configured as `OVERRIDE_AUTH_TOKEN` by the backend, and occupant consent where applicable.
