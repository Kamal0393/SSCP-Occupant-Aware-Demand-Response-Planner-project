# Database and synthetic data

Persistence is implemented under `app/infrastructure/db`; the domain models remain plain dataclasses. SQLAlchemy supports PostgreSQL in the Docker deployment and SQLite for local academic use. The default URL is `sqlite:///./sscp_dr_planner.db`; set `DATABASE_URL` to a PostgreSQL URL to switch. See `database.env.example`.

Create the schema and populate deterministic demo inputs from the backend directory:

```powershell
python -m app.infrastructure.data_generation
```

This uses seed `2026`, is safe to rerun for the same generated IDs, and persists inputs only. It does not create fake plans or decisions. Applications can call `initialize_database()` and `seed_database(session, dataset)` directly. `create_all` is intended for this academic/demo stage; schema changes for a deployed system should move to Alembic migrations.

The generator creates four neighborhood cases (normal demand, overload, high evening tariff, and emergency DR), with four buildings per case by default. Each includes occupant comfort ranges, opt-out/override examples, 15-minute occupancy and load profiles, flexible and inflexible appliances, tariff rates, and a DR event. Pass a seed to `generate_synthetic_dataset(seed=...)` for repeatable variants.

Repository adapters are exported from `app.infrastructure.db.repositories`. They accept a SQLAlchemy `Session`; transaction commit/rollback remains the caller's responsibility, except `seed_database`, which owns an atomic transaction for the whole dataset.
