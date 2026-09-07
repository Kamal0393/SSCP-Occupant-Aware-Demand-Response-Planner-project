# Occupant-Aware Demand-Response Planner

An industry-style proof of concept for a utility managing overloaded
neighbourhood transformers, built as an SSCP final-year project. The
system reduces peak demand while respecting occupant comfort, opt-out
rights, and scheduling preferences — and explains every recommendation
in plain English.

See [`docs/architecture.md`](docs/architecture.md) for the full design
rationale.

## Project status

**Milestone 1 of 11: Foundations & System Design** — complete.

- [x] Clean Architecture skeleton (domain / application / infrastructure / api)
- [x] Domain entities: `Building`, `Occupant`, `Transformer`, `Tariff`, `DemandResponseEvent`
- [x] Value objects: `ComfortRange`, `LoadProfile`, `Decision`
- [x] Hard and soft constraint modules
- [x] `DemandResponseStrategy` abstract interface (baseline/optimized contract)
- [x] FastAPI skeleton with structured logging and domain-aware error handling
- [x] Docker Compose (backend + Postgres)
- [x] Unit + integration tests (98 automated tests testcases)

## Repository layout

```
backend/app/
  domain/          # Pure Python — entities, value objects, constraints, strategy interface
  application/      # Use-case services (Milestone 3+)
  infrastructure/   # DB repos, OR-Tools adapter, data generator, explanation engine (Milestone 2+)
  api/              # FastAPI routers and app entrypoint
  core/             # Config, logging, exceptions
  tests/
    unit/
    integration/
frontend/
  operator-dashboard/   # React + Tailwind + Recharts (Milestone 7)
  occupant-dashboard/   # React (Milestone 8)
notebooks/experiments/  # Experiment notebook (Milestone 9)
data/
  raw/
  generated/             # Synthetic data output (Milestone 2)
docs/
  architecture.md
  modules/                # Per-module documentation (Purpose/Inputs/Outputs/Workflow/Design decisions)
docker-compose.yml
```

## Running locally

### Full stack (Docker)

```bash
docker compose up --build
```

Backend will be available at `http://localhost:8000`, with `/health` as
a liveness check. Postgres will be available at `localhost:5432`
(user: `sscp_user`, password: `sscp_pass`, db: `sscp_dr_planner`).

### Backend only, without Docker

```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.api.main:app --reload
```

### Running tests

```bash
cd backend
pip install -r requirements.txt
pytest app/tests -v
```

## Tech stack

| Layer | Technology |
|---|---|
| Frontend | React, Tailwind CSS, Recharts |
| Backend | FastAPI |
| Database | PostgreSQL |
| Optimization | OR-Tools (CP-SAT) |
| ML/Analysis | Pandas, NumPy, scikit-learn |
| Deployment | Docker / docker-compose |

## Key design decisions (see `docs/architecture.md` for full rationale)

- **Solver:** OR-Tools CP-SAT — handles the mix of discrete (opt-out,
  override flags) and continuous (setpoint) constraints this project
  needs, with clean infeasibility diagnostics.
- **Time modeling:** discrete 15-minute slots, matching typical tariff
  and telemetry granularity.
- **Explainability:** the optimizer never writes English. It emits a
  structured `Decision` object; a separate explanation service turns
  that into plain-language text. This keeps the two concerns
  independently testable.
