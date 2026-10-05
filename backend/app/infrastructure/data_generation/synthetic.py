"""Deterministic, physically plausible neighborhood demonstration data."""

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import random

from sqlalchemy.orm import Session

from app.domain.entities.appliance import Appliance, ApplianceType
from app.domain.entities.building import Building, BuildingType
from app.domain.entities.dr_event import DemandResponseEvent, DREventStatus
from app.domain.entities.occupant import Occupant
from app.domain.entities.tariff import Tariff
from app.domain.entities.transformer import Transformer
from app.domain.value_objects.comfort_range import ComfortRange
from app.domain.value_objects.load_profile import LoadProfile
from app.infrastructure.db.models import (
    ApplianceModel, BuildingModel, ComfortRangeModel, DREventModel,
    LoadProfileModel, OccupancyPatternModel, OccupantModel, TariffModel,
    TransformerModel,
)

SLOTS_PER_DAY = 96
SLOT_DURATION_MINUTES = 15
SCENARIOS = ("normal", "overloaded", "high_tariff", "emergency")


@dataclass(frozen=True)
class SyntheticGenerationConfig:
    seed: int = 2026
    building_count: int = 16
    transformer_count: int = 4
    occupants_per_building: int = 1
    appliances_per_building: int = 4
    intervals_per_profile: int = SLOTS_PER_DAY


@dataclass(frozen=True)
class SyntheticDataset:
    transformers: tuple[Transformer, ...]
    buildings: tuple[Building, ...]
    occupants: tuple[Occupant, ...]
    appliances: tuple[Appliance, ...]
    comfort_ranges: dict[str, ComfortRange]
    tariffs: tuple[Tariff, ...]
    events: tuple[DemandResponseEvent, ...]
    load_profiles: tuple[LoadProfile, ...]
    occupancy_patterns: dict[str, tuple[bool, ...]]
    scenario_by_transformer: dict[str, str]
    config: SyntheticGenerationConfig = SyntheticGenerationConfig()


def generate_synthetic_dataset(
    seed: int = 2026,
    building_count: int = 16,
    occupants_per_building: int = 1,
    appliances_per_building: int = 4,
    intervals_per_profile: int = SLOTS_PER_DAY,
    transformer_count: int = 4,
) -> SyntheticDataset:
    """Generate a reproducible neighborhood dataset using domain entities.

    Profiles use 15-minute samples. Appliance scheduling and tariffs retain
    the domain's 96-slot daily clock; profiles may span multiple days.
    """
    if transformer_count < 1:
        raise ValueError("transformer_count must be at least 1")
    if building_count < transformer_count:
        raise ValueError("building_count must be at least transformer_count")
    if occupants_per_building < 1:
        raise ValueError("occupants_per_building must be at least 1")
    if appliances_per_building < 1:
        raise ValueError("appliances_per_building must be at least 1")
    if intervals_per_profile < 1:
        raise ValueError("intervals_per_profile must be at least 1")

    config = SyntheticGenerationConfig(
        seed, building_count, transformer_count, occupants_per_building,
        appliances_per_building, intervals_per_profile,
    )
    rng = random.Random(seed)
    transformers: list[Transformer] = []
    buildings: list[Building] = []
    occupants: list[Occupant] = []
    appliances: list[Appliance] = []
    comforts: dict[str, ComfortRange] = {}
    tariffs: list[Tariff] = []
    events: list[DemandResponseEvent] = []
    profiles: list[LoadProfile] = []
    occupancy: dict[str, tuple[bool, ...]] = {}
    scenario_by_transformer: dict[str, str] = {}
    base_time = datetime(2026, 7, 15, 17, tzinfo=timezone.utc)
    building_counts = [building_count // transformer_count] * transformer_count
    for index in range(building_count % transformer_count):
        building_counts[index] += 1

    appliance_templates = (
        ("Refrigerator", ApplianceType.REFRIGERATOR, .16, False, True, None, 0, 1),
        ("HVAC", ApplianceType.HVAC, .62, True, True, None, 0, 1),
        ("Water heater", ApplianceType.WATER_HEATER, .25, True, False, None, 0, 1),
        ("Washer", ApplianceType.WASHING_MACHINE, .13, True, False, 72, 16, 2),
        ("Dishwasher", ApplianceType.DISHWASHER, .12, True, False, 76, 16, 2),
        ("EV charger", ApplianceType.EV_CHARGER, .85, True, False, 80, 24, 4),
    )

    for transformer_index in range(transformer_count):
        scenario = SCENARIOS[transformer_index % len(SCENARIOS)]
        transformer_id = f"TX-{transformer_index + 1:02d}"
        capacity = rng.uniform(72, 88)
        connected: list[str] = []
        scenario_profiles: list[tuple[float, ...]] = []
        for local_index in range(building_counts[transformer_index]):
            number = len(buildings) + 1
            building_id = f"B-{number:03d}"
            connected.append(building_id)
            building_type = (BuildingType.RESIDENTIAL, BuildingType.RESIDENTIAL,
                             BuildingType.MIXED_USE, BuildingType.COMMERCIAL)[local_index % 4]
            fixed_kw = rng.uniform(3.0, 5.5)
            flex_kw = rng.uniform(5.0, 9.5)
            occupant_ids: list[str] = []
            occupant_patterns: list[tuple[bool, ...]] = []
            base_occupied = tuple(
                (slot // 4 >= 6 and slot // 4 < 23)
                if building_type != BuildingType.COMMERCIAL
                else (slot // 4 >= 7 and slot // 4 < 19)
                for slot in range(SLOTS_PER_DAY)
            )
            for occupant_index in range(occupants_per_building):
                occupant_number = len(occupants) + 1
                occupant_id = f"O-{occupant_number:03d}"
                comfort_id = f"CR-{occupant_number:03d}"
                opted_out = occupant_number % 7 == 0 or (scenario == "emergency" and local_index == 0 and occupant_index == 0)
                occupant = Occupant(
                    occupant_id, building_id, f"Household {occupant_number:03d}", comfort_id,
                    opted_out, allow_override=(scenario == "emergency" and local_index == 1 and occupant_index == 0),
                )
                comfort = ComfortRange(
                    comfort_id, "temperature_c", 19.0 + rng.choice([0, .5]),
                    25.0 + rng.choice([0, .5]), rng.choice([21.0, 22.0, 23.0]),
                )
                preferred = min(comfort.max_value, max(comfort.min_value, comfort.preferred_value))
                comfort = ComfortRange(comfort.id, comfort.variable, comfort.min_value,
                                      comfort.max_value, preferred)
                occupants.append(occupant)
                comforts[comfort_id] = comfort
                occupant_ids.append(occupant_id)
                offset = rng.randrange(0, 8)
                daily_pattern = tuple(
                    value and not (slot // 4 < 6 + offset // 4)
                    if building_type != BuildingType.COMMERCIAL else value
                    for slot, value in enumerate(base_occupied)
                )
                occupant_patterns.append(daily_pattern)
                occupancy[occupant_id] = tuple(
                    daily_pattern[slot % SLOTS_PER_DAY]
                    for slot in range(intervals_per_profile)
                )

            building = Building(
                building_id, f"{building_type.value.title()} {number:03d}", transformer_id,
                building_type, rng.uniform(65, 180), fixed_kw, flex_kw, tuple(occupant_ids),
            )
            buildings.append(building)
            for appliance_index in range(appliances_per_building):
                name, appliance_type, share, flexible, running, preferred, shift, duration = appliance_templates[
                    appliance_index % len(appliance_templates)
                ]
                appliances.append(Appliance(
                    f"A-{number:03d}-{appliance_index + 1:02d}", building_id, name,
                    appliance_type, max(.2, flex_kw * share if flexible else fixed_kw * share),
                    flexible, running if appliance_index < len(appliance_templates) else False,
                    preferred, shift, duration,
                ))

            profile_values: list[float] = []
            for slot in range(intervals_per_profile):
                daily_slot = slot % SLOTS_PER_DAY
                hour = daily_slot / 4
                occupancy_factor = sum(pattern[daily_slot] for pattern in occupant_patterns) / occupants_per_building
                occupancy_factor = .45 + .55 * occupancy_factor
                evening_peak = 1.2 if 17 <= hour < 21 else 1.0
                hvac = flex_kw * .48 * occupancy_factor * (1.25 if 14 <= hour < 21 else .75)
                appliance_bump = flex_kw * .16 if 18 <= hour < 20 and local_index % 2 == 0 else 0
                noise = rng.uniform(-.04, .04) * (fixed_kw + flex_kw)
                profile_values.append(round(max(.1, fixed_kw * evening_peak + hvac + appliance_bump + noise), 3))
            profile = tuple(profile_values)
            scenario_profiles.append(profile)
            profiles.append(LoadProfile(building_id, profile))

        summed = tuple(
            round(sum(values[index] for values in scenario_profiles), 3)
            for index in range(intervals_per_profile)
        )
        peak = max(summed)
        if scenario == "normal":
            rated = max(capacity, peak * 1.18)
        elif scenario == "overloaded":
            rated = min(capacity, peak * .78)
        elif scenario == "emergency":
            rated = min(capacity, peak * .68)
        else:
            rated = max(capacity, peak * 1.05)
        transformers.append(Transformer(
            transformer_id, f"Neighborhood Transformer {transformer_index + 1}",
            rated, round(peak, 3), tuple(connected), .10,
        ))
        scenario_by_transformer[transformer_id] = scenario
        profiles.append(LoadProfile(transformer_id, summed))

        rates = {}
        for slot in range(SLOTS_PER_DAY):
            hour = slot / 4
            rate = 5.5 if hour < 16 else (10.0 if 17 <= hour < 21 else 7.0)
            if scenario in ("high_tariff", "overloaded") and 17 <= hour < 21:
                rate = 18.0
            rates[slot] = rate
        tariffs.append(Tariff(f"TAR-{transformer_index + 1:02d}",
            f"{scenario.title()} time-of-use", "INR", rates))
        target = max(3.0, peak - rated * .90)
        if scenario == "normal":
            target = min(5.0, max(2.0, peak * .04))
        event_time = base_time + timedelta(days=transformer_index)
        events.append(DemandResponseEvent(
            f"DR-{transformer_index + 1:02d}", transformer_id, event_time,
            event_time + timedelta(hours=3), round(target, 2),
            DREventStatus.ACTIVE if scenario in ("overloaded", "emergency") else DREventStatus.PLANNED,
        ))

    return SyntheticDataset(
        tuple(transformers), tuple(buildings), tuple(occupants), tuple(appliances),
        comforts, tuple(tariffs), tuple(events), tuple(profiles), occupancy,
        scenario_by_transformer, config,
    )


def dataset_to_dict(dataset: SyntheticDataset) -> dict[str, object]:
    """Serialize a dataset as stable, self-describing JSON-compatible data."""
    config = dataset.config
    start = datetime(2026, 7, 15, 0, tzinfo=timezone.utc)
    return {
        "schema_version": "1.0",
        "generator": "sscp.synthetic_dataset",
        "generation": {
            "seed": config.seed,
            "parameters": {
                "building_count": config.building_count,
                "transformer_count": config.transformer_count,
                "occupants_per_building": config.occupants_per_building,
                "appliances_per_building": config.appliances_per_building,
                "intervals_per_profile": config.intervals_per_profile,
                "interval_minutes": SLOT_DURATION_MINUTES,
            },
            "counts": {
                "transformers": len(dataset.transformers),
                "buildings": len(dataset.buildings),
                "occupants": len(dataset.occupants),
                "appliances": len(dataset.appliances),
                "comfort_ranges": len(dataset.comfort_ranges),
                "tariffs": len(dataset.tariffs),
                "demand_response_events": len(dataset.events),
                "load_profiles": len(dataset.load_profiles),
                "time_series_intervals": sum(len(profile.values_kw) for profile in dataset.load_profiles),
            },
        },
        "transformers": [
            {"id": item.id, "name": item.name, "rated_capacity_kw": item.rated_capacity_kw,
             "current_load_kw": item.current_load_kw,
             "connected_building_ids": list(item.connected_building_ids),
             "safety_margin_pct": item.safety_margin_pct,
             "scenario": dataset.scenario_by_transformer[item.id]}
            for item in dataset.transformers
        ],
        "buildings": [
            {"id": item.id, "name": item.name, "transformer_id": item.transformer_id,
             "building_type": item.building_type.value, "floor_area_sqm": item.floor_area_sqm,
             "fixed_load_kw": item.fixed_load_kw, "flexible_load_kw": item.flexible_load_kw,
             "occupant_ids": list(item.occupant_ids)} for item in dataset.buildings
        ],
        "occupants": [
            {"id": item.id, "building_id": item.building_id, "display_name": item.display_name,
             "comfort_range_id": item.comfort_range_id, "opted_out": item.opted_out,
             "allow_override": item.allow_override} for item in dataset.occupants
        ],
        "comfort_ranges": [
            {"id": item.id, "occupant_id": occupant.id, "variable": item.variable,
             "min_value": item.min_value, "max_value": item.max_value,
             "preferred_value": item.preferred_value, "unit": "degC"}
            for occupant in dataset.occupants
            for item in (dataset.comfort_ranges[occupant.comfort_range_id],)
        ],
        "appliances": [
            {"id": item.id, "building_id": item.building_id, "name": item.name,
             "appliance_type": item.appliance_type.value, "rated_power_kw": item.rated_power_kw,
             "is_flexible": item.is_flexible, "is_running": item.is_running,
             "preferred_slot": item.preferred_slot, "max_shift_slots": item.max_shift_slots,
             "duration_slots": item.duration_slots}
            for item in dataset.appliances
        ],
        "occupancy_patterns": [
            {"occupant_id": occupant_id, "occupied_by_interval": list(pattern)}
            for occupant_id, pattern in sorted(dataset.occupancy_patterns.items())
        ],
        "tariffs": [
            {"id": item.id, "name": item.name, "currency": item.currency,
             "rate_unit": f"{item.currency}/kWh",
             "interval_minutes": SLOT_DURATION_MINUTES,
             "rate_per_slot": {str(slot): item.rate_per_slot[slot] for slot in sorted(item.rate_per_slot)},
             "scenario": dataset.scenario_by_transformer[dataset.transformers[index].id]}
            for index, item in enumerate(dataset.tariffs)
        ],
        "demand_response_events": [
            {"id": item.id, "transformer_id": item.transformer_id,
             "start_time": item.start_time.isoformat(), "end_time": item.end_time.isoformat(),
             "target_reduction_kw": item.target_reduction_kw, "status": item.status.value,
             "scenario": dataset.scenario_by_transformer[item.transformer_id]}
            for item in dataset.events
        ],
        "load_profiles": [
            {"entity_id": profile.entity_id,
             "entity_type": "transformer" if profile.entity_id.startswith("TX-") else "building",
             "interval_minutes": SLOT_DURATION_MINUTES,
             "intervals": [
                 {"timestamp": (start + timedelta(minutes=SLOT_DURATION_MINUTES * index)).isoformat(),
                  "demand_kw": value}
                 for index, value in enumerate(profile.values_kw)
             ]}
            for profile in dataset.load_profiles
        ],
    }

def seed_database(session: Session, dataset: SyntheticDataset | None = None) -> SyntheticDataset:
    """Persist generated source data atomically. No planning outcomes are invented."""
    dataset = dataset or generate_synthetic_dataset()
    try:
        for entity in dataset.transformers:
            session.merge(TransformerModel(id=entity.id, name=entity.name,
                rated_capacity_kw=entity.rated_capacity_kw, current_load_kw=entity.current_load_kw,
                connected_building_ids=list(entity.connected_building_ids), safety_margin_pct=entity.safety_margin_pct))
        session.flush()
        for entity in dataset.buildings:
            session.merge(BuildingModel(id=entity.id, name=entity.name, transformer_id=entity.transformer_id,
                building_type=entity.building_type.value, floor_area_sqm=entity.floor_area_sqm,
                fixed_load_kw=entity.fixed_load_kw, flexible_load_kw=entity.flexible_load_kw,
                occupant_ids=list(entity.occupant_ids)))
        session.flush()
        for entity in dataset.occupants:
            comfort = dataset.comfort_ranges[entity.comfort_range_id]
            session.merge(OccupantModel(id=entity.id, building_id=entity.building_id,
                display_name=entity.display_name, comfort_range_id=entity.comfort_range_id,
                opted_out=entity.opted_out, allow_override=entity.allow_override,
                occupancy_pattern=list(dataset.occupancy_patterns[entity.id]),
                comfort_min=comfort.min_value, comfort_max=comfort.max_value,
                comfort_preferred=comfort.preferred_value))
        session.flush()
        for entity in dataset.occupants:
            comfort = dataset.comfort_ranges[entity.comfort_range_id]
            session.merge(ComfortRangeModel(id=comfort.id, occupant_id=entity.id,
                variable=comfort.variable, min_value=comfort.min_value, max_value=comfort.max_value,
                preferred_value=comfort.preferred_value))
        for entity in dataset.appliances:
            session.merge(ApplianceModel(id=entity.id, building_id=entity.building_id, name=entity.name,
                appliance_type=entity.appliance_type.value, rated_power_kw=entity.rated_power_kw,
                is_flexible=entity.is_flexible, is_running=entity.is_running,
                preferred_slot=entity.preferred_slot, max_shift_slots=entity.max_shift_slots,
                duration_slots=entity.duration_slots))
        session.flush()
        for entity, scenario in zip(dataset.tariffs, dataset.scenario_by_transformer.values()):
            session.merge(TariffModel(id=entity.id, name=entity.name, currency=entity.currency,
                rate_per_slot={str(k): v for k, v in entity.rate_per_slot.items()}, scenario=scenario))
        for entity in dataset.events:
            session.merge(DREventModel(id=entity.id, transformer_id=entity.transformer_id,
                start_time=entity.start_time, end_time=entity.end_time,
                target_reduction_kw=entity.target_reduction_kw, status=entity.status.value,
                scenario=dataset.scenario_by_transformer[entity.transformer_id]))
        session.flush()
        for entity in dataset.load_profiles:
            session.merge(LoadProfileModel(id=f"load-profile:{entity.entity_id}", entity_id=entity.entity_id,
                entity_type="transformer" if entity.entity_id.startswith("TX-") else "building",
                values_kw=list(entity.values_kw)))
        for occupant_id, slots in dataset.occupancy_patterns.items():
            session.merge(OccupancyPatternModel(id=f"occupancy:{occupant_id}", occupant_id=occupant_id,
                occupied_by_slot=list(slots)))
        session.commit()
    except Exception:
        session.rollback()
        raise
    return dataset
