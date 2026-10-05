"""Generate an auditable dataset or seed the configured demo database."""

import argparse
import json
from pathlib import Path

from app.infrastructure.data_generation.synthetic import (
    dataset_to_dict,
    generate_synthetic_dataset,
    seed_database,
)
from app.infrastructure.db.session import SessionLocal, initialize_database


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seed", type=int, default=2026, help="deterministic random seed (default: 2026)")
    parser.add_argument("--buildings", "--building-count", dest="building_count", type=int, default=16)
    parser.add_argument("--transformers", dest="transformer_count", type=int, default=4)
    parser.add_argument("--occupants-per-building", type=int, default=1)
    parser.add_argument("--appliances-per-building", type=int, default=4)
    parser.add_argument("--intervals", "--intervals-per-profile", dest="intervals_per_profile",
                        type=int, default=96, help="15-minute samples per profile (default: 96)")
    parser.add_argument("--output", type=Path, help="write JSON dataset here instead of seeding the database")
    args = parser.parse_args()

    dataset = generate_synthetic_dataset(
        seed=args.seed,
        building_count=args.building_count,
        transformer_count=args.transformer_count,
        occupants_per_building=args.occupants_per_building,
        appliances_per_building=args.appliances_per_building,
        intervals_per_profile=args.intervals_per_profile,
    )
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(
            json.dumps(dataset_to_dict(dataset), indent=2, sort_keys=True, ensure_ascii=False) + "\n",
            encoding="utf-8", newline="\n",
        )
        print(
            f"Wrote {args.output}: seed={args.seed}, transformers={len(dataset.transformers)}, "
            f"buildings={len(dataset.buildings)}, occupants={len(dataset.occupants)}, "
            f"appliances={len(dataset.appliances)}, profiles={len(dataset.load_profiles)}"
        )
        return

    initialize_database()
    with SessionLocal() as session:
        seed_database(session, dataset)
    print(
        f"Seeded {len(dataset.transformers)} transformers, {len(dataset.buildings)} buildings, "
        f"{len(dataset.occupants)} occupants, and {len(dataset.events)} DR events (seed={args.seed})."
    )


if __name__ == "__main__":
    main()
