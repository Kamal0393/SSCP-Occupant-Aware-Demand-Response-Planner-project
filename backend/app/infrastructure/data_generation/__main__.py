"""Initialize the configured database and load deterministic demo inputs."""

from app.infrastructure.data_generation.synthetic import seed_database
from app.infrastructure.db.session import SessionLocal, initialize_database


def main() -> None:
    initialize_database()
    with SessionLocal() as session:
        dataset = seed_database(session)
    print(
        f"Seeded {len(dataset.transformers)} transformers, {len(dataset.buildings)} buildings, "
        f"{len(dataset.occupants)} occupants, and {len(dataset.events)} DR events."
    )


if __name__ == "__main__":
    main()
