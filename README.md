# Occupant-Aware Demand-Response Planner

A demonstration system for a utility operator managing overloaded neighbourhood transformers. It compares a baseline plan with an OR-Tools plan, estimates load and cost impact, respects comfort limits and occupant opt-outs, and provides an authenticated emergency override path for occupants who have separately consented to it.

## Problem statement

Residential, commercial, and mixed-use buildings share distribution transformers whose peak demand can exceed rated capacity. A utility needs to reduce or shift flexible demand while maintaining occupant comfort, respecting opt-out choices, and providing an auditable explanation of each planning decision.

## Objectives

- [x] Clean Architecture skeleton (domain / application / infrastructure / api)
- [x] Domain entities: `Building`, `Occupant`, `Transformer`, `Tariff`, `DemandResponseEvent`
- [x] Value objects: `ComfortRange`, `LoadProfile`, `Decision`
- [x] Hard and soft constraint modules
- [x] `DemandResponseStrategy` abstract interface (baseline/optimized contract)
- [x] FastAPI skeleton with structured logging and domain-aware error handling
- [x] Docker Compose (backend + Postgres)
- [x] Unit + integration tests (98 automated tests testcases)
- Identify transformer overload using transformer and load-profile inputs.
- Compare baseline actions with an optimized demand-response plan.
- Balance transformer peak reduction against comfort and tariff preferences.
- Respect hard comfort bounds, fixed/non-flexible loads, and opt-outs.
- Support authorized emergency override only for occupants who allow it.
- Persist source data, plans, decisions, explanations, and planning history.

## Architecture

The implementation follows Presentation -> Application -> Domain <- Infrastructure. React is the operator presentation. FastAPI validates requests and delegates to application services. Domain entities, constraints, strategies, and value objects implement planning rules. SQLAlchemy repositories and the OR-Tools adapter implement infrastructure contracts. See [docs/architecture.md](docs/architecture.md) for the implementation details.

## Project structure

```text
backend/app/api/                 FastAPI routes, schemas, dependencies
backend/app/application/         Planning, comparison, persistence, explanations
backend/app/domain/              Entities, constraints, strategies, value objects
backend/app/infrastructure/db/   SQLAlchemy models, sessions, repositories
backend/app/infrastructure/solver/ OR-Tools solver adapter
backend/app/infrastructure/data_generation/ Deterministic synthetic scenarios
backend/app/tests/               Unit and API/persistence integration tests
frontend/operator-dashboard/     React + TypeScript + Vite operator console
docs/architecture.md             Actual architecture and data flow
docker-compose.yml               PostgreSQL, API, and frontend services
```

## Technology stack

- Python 3.11, FastAPI, Pydantic, SQLAlchemy
- PostgreSQL for the compose deployment; SQLite for local development/tests
- OR-Tools CP-SAT for constrained planning
- React, TypeScript, Vite, Recharts, and Nginx for the operator UI
- Docker Compose for the complete demo stack

## Installation and environment

Python setup (from `backend/`):

```bash
python -m venv .venv
# Windows PowerShell: .\.venv\Scripts\Activate.ps1
# macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
```

Frontend setup (from `frontend/operator-dashboard/`):

```bash
npm ci
```

Copy `backend/database.env.example` to `backend/.env` only if local overrides are needed. Copy `frontend/operator-dashboard/.env.example` to its `.env` to set the API URL for Vite. `.env` files are local configuration and must not be committed. Relevant backend variables:

| Variable | Default | Purpose |
|---|---|---|
| `DATABASE_URL` | `sqlite:///./sscp_dr_planner.db` | SQLAlchemy database URL; set a PostgreSQL URL for deployment |
| `DATABASE_ECHO` | `false` | SQL statement logging |
| `ENVIRONMENT` | `development` | Environment label returned by health check |
| `LOG_LEVEL` | `INFO` | Application log level |
| `CORS_ORIGINS` | localhost Vite origins | JSON array of allowed browser origins |
| `OVERRIDE_AUTH_TOKEN` | unset | Shared operator token; override endpoint rejects requests while unset |

Never use the compose development database password or an example override token as production credentials.

## Database setup and seed data

The configured SQLAlchemy engine and session live in infrastructure. For SQLite/local execution, schema setup and deterministic seed data can be initialized with:

```bash
cd backend
python -m app.infrastructure.data_generation
```

This creates tables and seeds source inputs with seed `2026`; it does not invent planning outcomes. To export the reproducible sample JSON dataset and configure generation counts, see [backend/DATABASE_AND_SYNTHETIC_DATA.md](backend/DATABASE_AND_SYNTHETIC_DATA.md). PostgreSQL is initialized and seeded when the backend container starts after the database health check succeeds. Schema creation uses SQLAlchemy `create_all`; a versioned migration system is not currently included.

## Run the backend

From `backend/` after installing requirements:

```bash
uvicorn app.api.main:app --reload
```

API base URL is `http://localhost:8000`; interactive API docs are at `/docs`; liveness endpoint is `/health`. The API uses the configured database. For an empty local database, run the seed command above before opening the dashboard.

## Run the frontend

From `frontend/operator-dashboard/`:

```bash
npm ci
npm run dev
```

Vite serves the UI on `http://localhost:5173`. `VITE_API_URL` selects the FastAPI origin and defaults to `http://localhost:8000`. The dashboard reads resources, planning results, explanations, and history from FastAPI; it does not use a mock API in the normal application flow.

## Docker execution

From the repository root:

```bash
docker compose up --build
```

The UI is served at `http://localhost:8080`, FastAPI at `http://localhost:8000`, and PostgreSQL at `localhost:5432`. Compose defaults are for a local academic demonstration only. Override `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB`, `POSTGRES_PORT`, `BACKEND_PORT`, `FRONTEND_PORT`, `OVERRIDE_AUTH_TOKEN`, and other documented settings through the shell or an untracked root `.env`. To stop services use `docker compose down`; to also remove the demo database volume use `docker compose down -v` (this deletes persisted demo data).

## API usage

Resource retrieval endpoints include `GET /api/buildings`, `/api/occupants`, `/api/appliances`, `/api/transformers`, `/api/tariffs`, `/api/dr-events`, `/api/comfort-ranges`, and `/api/load-profiles`. Planning endpoints include:

- `POST /api/planning/generate` — calculate and persist an optimized plan.
- `POST /api/planning/compare` — calculate baseline and optimized plans and their measured metrics.
- `POST /api/planning/emergency-override` — authorized emergency workflow.
- `GET /api/planning/results`, `/api/planning/results/{id}`, and `/api/planning/results/{id}/decisions`.
- `GET /api/planning/results/{id}/explanations` and `/api/planning/history` (optionally scoped by result ID).

Use `/docs` for the request and response schemas. Planning requests carry the transformer, DR event, connected buildings and occupants, comfort ranges, tariff, appliances, objective weights, and optionally a transformer load profile. See [docs/api_workflows.md](docs/api_workflows.md) for comparison response metrics and the authorized emergency-override request/response examples.

## Planning and optimization workflow

Select a transformer, event, and tariff; provide its connected building and occupant data; then submit a planning request. The backend calculates baseline and optimized decisions from those inputs and the OR-Tools solver. Metrics include baseline/optimized peak and energy, peak change, estimated cost change when tariff data is available, comfort impact, modified decisions, protected decisions, opt-out decisions, and infeasibility status. These values are derived from the execution data and decisions.

Hard constraints preserve comfort hard bounds and non-negative load. Opted-out occupants remain protected in normal planning. Flexible appliance tasks can move within their allowed shift window, and tariff rates can influence scheduling. Soft objectives trade transformer peak reduction against comfort/preference preservation and available cost impact. Explanations are generated from each returned decision and persisted with planning history.

## Opt-out and emergency override

An occupant opt-out is a protection, not a synonym for emergency authorization. Emergency override additionally requires an operator token in the `X-Override-Token` header, an operator ID, a meaningful justification, and occupant-level `allow_override` consent. Without a configured `OVERRIDE_AUTH_TOKEN`, the API denies the emergency request. Overrides and their actor/justification are recorded in planning history; comfort hard bounds still apply.

## Reproducible planning experiment

The executed [baseline vs optimized experiment notebook](notebooks/baseline_vs_optimized_experiment.ipynb) measures the generated overloaded-transformer case (seed 2026), including peak reduction against target, comfort, opt-out allocation, tariff cost, and current error behavior. It records actual outputs and limitations; see [notebooks/README.md](notebooks/README.md) for setup and interpretation.

## Testing and verification

Backend unit, solver, API, database, repository, synthetic data, planning, and override tests:

```bash
cd backend
python -m pytest -q -p no:cacheprovider
```

Frontend critical-component tests and production build:

```bash
cd frontend/operator-dashboard
npm ci
npm test
npm run build
```

With the API running and seeded, run the no-mock live backend workflow check:

```bash
# PowerShell
$env:DEMO_OVERRIDE_TOKEN = "<same value as OVERRIDE_AUTH_TOKEN>"
npm run verify:live
```

The live check reads current API resources, finds a viable overloaded demo scenario, runs comparison and planning, verifies opt-out and appliance decisions, reads explanations/history, and exercises the authorized emergency endpoint.

## Demo workflow

1. Start the compose stack and wait for the frontend/backend health checks.
2. Open `http://localhost:8080`; the deterministic seed includes normal, overloaded, high-tariff, and emergency scenarios.
3. Select the overloaded transformer and active DR event; inspect its connected resources and load profile.
4. Run planning, then review optimization results, baseline comparison, explanations, protected decisions, and history.
5. To demonstrate emergency handling, configure the operator token and use the emergency form on the emergency scenario. The token must also be passed to the API; the demo does not bypass authorization.

## Limitations

- Synthetic profiles and comfort settings demonstrate workflow behavior; they are not field measurements or a validated utility forecast.
- HVAC flexibility and comfort response use simplified kW/setpoint proxies.
- Planning operates on discrete 15-minute slots and a one-day tariff profile.
- Database tables are created from SQLAlchemy metadata; no migration workflow is configured.
- Operator-token authentication is a demonstration control, not a production identity/access-management system.
- API requests include their planning input context; resource CRUD and planning are not yet joined through a fully normalized scenario-selection API.

## Future work

- Add Alembic migrations and a managed secrets/authentication setup.
- Validate models against utility telemetry and calibrated building response.
- Add authorization roles, audit retention policy, and operational monitoring.
- Expand scenario, solver infeasibility, and browser end-to-end coverage.
- Code-split the frontend bundle and add accessibility/performance checks.
