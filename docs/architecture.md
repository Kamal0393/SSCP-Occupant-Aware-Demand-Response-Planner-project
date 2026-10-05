# Architecture

## Implemented system

The repository currently contains a React + TypeScript operator dashboard, a FastAPI backend, SQLAlchemy persistence, and an OR-Tools CP-SAT solver adapter. Dependencies follow the Clean Architecture direction: Presentation -> Application -> Domain, with Infrastructure implementing persistence and solver adapters used at the outer boundary.

```text
React + TypeScript
       | HTTP/JSON
       v
FastAPI routes and Pydantic schemas
       | request mapping / dependency injection
       v
Application services
  PlanningService | ComparisonService | PlanningAnalysisService
  ExplanationService | PlanningPersistenceService
       | domain contracts and entities
       v
Domain
  entities | value objects | hard/soft constraints | strategies
       ^                                       |
       |                                       | Solver interface
Infrastructure                                v
  SQLAlchemy session/repositories       OR-Tools CP-SAT adapter
  deterministic synthetic generator
       |
       v
 SQLite (local/tests) or PostgreSQL (Docker deployment)
```

## Presentation and API

`frontend/operator-dashboard/src/App.tsx` loads transformer, building, occupant, appliance, tariff, DR event, comfort-range, load-profile, result, and history data through `src/api.ts`. The application pages show the dashboard, resource tables, planning request, optimization results, comparison, explanations, emergency form, and persisted history. API loading and error states are visible in the UI.

`backend/app/api/main.py` installs CORS from `CORS_ORIGINS`, logging, health checks, and handlers for domain, validation, integrity, database, and unexpected errors. Routers under `app/api/routers/` expose resource retrieval/CRUD and planning, comparison, result, decision, explanation, history, and emergency override endpoints. Pydantic schemas validate input and serialize responses. Routes use dependencies for SQLAlchemy sessions and planning authorization.

## Application layer

- `PlanningService` invokes the selected strategy using a `PlanningContext`.
- `ComparisonService` executes baseline and optimized strategies against the same context.
- `PlanningAnalysisService` derives peak, energy, tariff-cost, comfort, modified-decision, and protection metrics from profiles and actual decisions.
- `ExplanationService` maps decision actions and reasoning tags into deterministic operator-readable text.
- `PlanningPersistenceService` stores a result, its decisions/explanations, and audit history.
- `planning_mapper.py` maps validated API requests into domain objects; domain code does not depend on FastAPI or SQLAlchemy.

## Domain and optimization

Domain entities include `Building`, `Occupant`, `Appliance`, `Transformer`, `Tariff`, and `DemandResponseEvent`. Value objects include `ComfortRange`, `LoadProfile`, `Decision`, and `EmergencyOverride`. `PlanningContext` holds the event, transformer, buildings, occupants, comfort ranges, tariff, objective weights, appliances, optional profile, and optional authorized override.

`BaselineStrategy` provides the comparison reference. `OptimizedStrategy` prepares decisions under the strategy/solver abstraction and delegates the optimization problem to the solver interface. `ORToolsSolver` uses CP-SAT for discrete appliance scheduling and selected bounded decisions. Hard constraints include comfort bounds, non-negative reductions, opt-out protections absent an authorized consented override, appliance shift bounds, and override authorization/consent checks. Soft objective weights express the peak/comfort/cost trade-off when those inputs are available. Solver failure/infeasibility is surfaced as explicit decision/status information and API errors as appropriate.

The model uses 96 quarter-hour slots per day. The API converts event timestamps to slot windows. Tariff and load profiles are slot-indexed; energy and cost metrics are estimates derived from the supplied profiles and reductions.

## Infrastructure and persistence

`app/infrastructure/db/models.py` declares SQLAlchemy tables for transformers, buildings, occupants, comfort ranges, appliances, tariffs, DR events, load profiles, occupancy patterns, planning results, decisions, explanations, and history. `session.py` builds engines/sessions from `DATABASE_URL`, enables SQLite foreign keys, and provides schema initialization. Repository contracts and SQLAlchemy repository adapters are under `app/infrastructure/db/repositories/`; domain objects remain database agnostic.

SQLite is the default local/test database. Compose uses PostgreSQL 16. `python -m app.infrastructure.data_generation` creates the configured schema and seeds deterministic input data. It stores no fabricated plan, decision, metric, or explanation. Compose waits for PostgreSQL readiness, then seeds before starting FastAPI. The current initialization uses SQLAlchemy `create_all`; no Alembic migration set is present.

## Synthetic scenarios

`generate_synthetic_dataset(seed=2026)` makes repeatable transformer, building, occupant, comfort, appliance, occupancy, tariff, event, and load-profile inputs. It includes normal demand, transformer overload, high-tariff, and emergency cases; flexible and fixed appliances; opted-out and override-consenting occupants; and varied occupancy/comfort parameters. Seed persistence uses repository-facing SQLAlchemy models and is idempotent for generated source records.

## Error and authorization boundaries

Input validation errors use FastAPI/Pydantic responses. Missing API resources return 404; unauthorized override returns 403; hard-constraint/infeasible conflicts may return 409; database unavailability returns a generic 503; unexpected failures return a generic 500 without stack traces. Detailed stack traces remain server-side logs.

Emergency override requires a configured `OVERRIDE_AUTH_TOKEN` and matching `X-Override-Token`, a non-empty operator identity and justification, and `allow_override` consent. An occupant's `opted_out` flag remains separate. Authorized override decisions and their operator/justification are persisted in planning history.

## Deployment and checks

`docker-compose.yml` defines PostgreSQL, backend, and static Nginx frontend services with database/backend health checks. Backend CORS origins include local Vite and Compose frontend origins. The frontend API URL is a Vite build-time variable; the Compose build defaults to the host API at `http://localhost:8000` for browser access.

Backend tests live in `backend/app/tests/` and cover domain behavior, solver behavior, planning/metrics/explanations, persistence/repositories/synthetic generation, and API workflows. Frontend component tests are in `frontend/operator-dashboard/src/App.test.tsx`. `npm run verify:live` exercises the live API and database without substituting mocked backend responses.

## Current limitations

- Synthetic data does not represent calibrated feeder/building telemetry.
- Load response and occupant comfort are simplified planning approximations.
- Planning uses a single daily 96-slot profile.
- No database migrations or production-grade identity provider are configured.
- The API planning request supplies the scenario context directly; a complete relational scenario assembly workflow is not implemented.
- The frontend's generated JavaScript bundle currently exceeds Vite's 500 kB advisory threshold.
