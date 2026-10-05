# Database and synthetic data

Persistence is implemented under `app/infrastructure/db`; domain objects remain plain dataclasses. SQLAlchemy supports PostgreSQL in Docker and SQLite locally. The default URL is `sqlite:///./sscp_dr_planner.db`; set `DATABASE_URL` to a PostgreSQL URL to switch. See `database.env.example`.

## Generate a dataset

From `backend/`, generate the checked-in demonstration JSON file:

```powershell
python -m app.infrastructure.data_generation --output ../data/synthetic_demo.json --seed 2026 --buildings 16 --transformers 4 --occupants-per-building 1 --appliances-per-building 4 --intervals 96
```

The output parent directory is created when needed. Generation writes source inputs only and does not invent planning outcomes, decisions, or explanations. The JSON contains no wall-clock generation timestamp, so rerunning the same command produces byte-identical data. `--seed` defaults to `2026`; each generated choice and load-noise sample comes from a local `random.Random(seed)` instance. Equal seeds and parameters produce equal output; changing the seed changes randomized capacities, building attributes, preferences, and load samples.

Counts can be changed with `--buildings`, `--transformers`, `--occupants-per-building`, `--appliances-per-building`, and `--intervals`. Buildings are distributed across transformers, so building count must be at least transformer count. At least one occupant, appliance, and interval per profile is required. Transformers cycle through normal, overloaded, high-tariff, and emergency scenarios. Appliance scheduling and daily tariffs use the domain's fixed 96-slot clock; time-series profiles can contain any positive number of 15-minute intervals. Occupancy profiles have the same interval count as load profiles.

To preserve the established database initialization workflow, running the module without `--output` still initializes the configured database and persists generated inputs. The same generation arguments apply in that mode. Direct callers can use `generate_synthetic_dataset(...)`, `dataset_to_dict(...)`, or `seed_database(session, dataset)`.

## Dataset contents and schema

The UTF-8 JSON document has `schema_version` `1.0`, generator identifier `sscp.synthetic_dataset`, `generation` metadata, and entity collections: `transformers`, `buildings`, `occupants`, `comfort_ranges`, `appliances`, `occupancy_patterns`, `tariffs`, `demand_response_events`, and `load_profiles`. JSON booleans, strings, numbers, arrays, and objects correspond to the types below. IDs are stable for a given generation configuration and are local identifiers, not personal information.

| Collection / fields | Type and unit | Relationships and valid range |
|---|---|---|
| `generation.seed` | integer | Explicit random seed used by the generator. |
| `generation.parameters.*` | integers | Requested entity/profile counts; `interval_minutes` is `15`. |
| `generation.counts.*` | integer | Actual collection/profile interval counts in this document. |
| `transformers`: `id`, `name`, `scenario` | string | Scenario is `normal`, `overloaded`, `high_tariff`, or `emergency`. |
| `transformers.rated_capacity_kw`, `current_load_kw` | number, kW | Capacity is positive; load is non-negative and equals that transformer's peak aggregate profile. |
| `transformers.connected_building_ids` | array of strings | References buildings whose `transformer_id` is this transformer. |
| `transformers.safety_margin_pct` | number, fraction | `0.10` in generated records; valid domain range `[0, 1)`. |
| `buildings`: `id`, `name`, `transformer_id`, `building_type` | strings | `transformer_id` references a transformer; type is `residential`, `commercial`, or `mixed_use`. |
| `buildings.floor_area_sqm` | number, square metres | Positive. |
| `buildings.fixed_load_kw`, `flexible_load_kw` | number, kW | Non-negative planning inputs. |
| `buildings.occupant_ids` | array of strings | References one or more occupant records belonging to this building. |
| `occupants`: `id`, `building_id`, `display_name`, `comfort_range_id` | strings | Building and comfort IDs reference their corresponding records; display names are synthetic labels. |
| `occupants.opted_out`, `allow_override` | boolean | Independent opt-out and pre-consented override flags. |
| `comfort_ranges`: `id`, `occupant_id`, `variable`, `unit` | strings | One comfort range is associated with each occupant; variable is `temperature_c`, unit is `degC`. |
| `comfort_ranges.min_value`, `max_value`, `preferred_value` | number, degrees Celsius | `19.0 <= min < max <= 25.5`; preferred value is within the inclusive bounds. |
| `appliances`: `id`, `building_id`, `name`, `appliance_type` | strings | Building reference; type is a domain appliance enum. |
| `appliances.rated_power_kw` | number, kW | Positive. |
| `appliances.is_flexible`, `is_running` | boolean | Whether the load is shiftable and currently running. |
| `appliances.preferred_slot`, `max_shift_slots`, `duration_slots` | integer or null, slots | Daily slot index is `0..95` or null; shift is non-negative; duration is positive. One slot is 15 minutes. |
| `occupancy_patterns.occupant_id` | string | References an occupant. |
| `occupancy_patterns.occupied_by_interval` | array of booleans | Each entry corresponds by index to a 15-minute time-series sample; length equals `intervals_per_profile`. |
| `tariffs`: `id`, `name`, `currency`, `rate_unit`, `scenario` | strings | Currency is `INR`; rate unit is `INR/kWh`; scenario matches its transformer. |
| `tariffs.interval_minutes` | integer, minutes | `15`; `rate_per_slot` is a complete daily 96-slot mapping. |
| `tariffs.rate_per_slot` | object of number, INR/kWh | Keys are daily slots `0..95`; rates are non-negative and use a synthetic time-of-use schedule (5.5, 7, 10, or 18 INR/kWh). |
| `demand_response_events`: `id`, `transformer_id`, `start_time`, `end_time`, `status`, `scenario` | strings | References a transformer; timestamps are ISO 8601 UTC; end is after start; status is `planned` or `active`. |
| `demand_response_events.target_reduction_kw` | number, kW | Positive requested reduction. |
| `load_profiles`: `entity_id`, `entity_type` | string | Entity is a building or transformer, identified by `entity_id`. |
| `load_profiles.interval_minutes` | integer, minutes | `15`; each profile has exactly the configured interval count. |
| `load_profiles.intervals[].timestamp` | string, ISO 8601 UTC | Starts at `2026-07-15T00:00:00+00:00`, advances exactly 15 minutes per sample. |
| `load_profiles.intervals[].demand_kw` | number, kW | Non-negative simulated demand. Transformer values equal the sum of connected building values at the same interval. |

For the committed sample, generation metadata records seed `2026`, 16 buildings, four transformers, one occupant and four appliances per building, and 96 time-series intervals per profile (one day). It contains 16 occupants, 64 appliances, 20 load profiles, and 1,920 load samples across all building and transformer profiles. The file is intentionally small enough for source control and repeatable experiments; it is synthetic, not calibrated utility telemetry.

## Database persistence

Create the schema and populate the default deterministic demonstration scenario from `backend/`:

```powershell
python -m app.infrastructure.data_generation
```

This uses seed `2026`, is safe to rerun for the same generated IDs, and persists inputs only. `create_all` is intended for this academic/demo stage; deployed schema changes should use migrations. `seed_database` owns an atomic transaction for the whole dataset; repository adapters accept a SQLAlchemy `Session` and otherwise leave transaction control to the caller.
