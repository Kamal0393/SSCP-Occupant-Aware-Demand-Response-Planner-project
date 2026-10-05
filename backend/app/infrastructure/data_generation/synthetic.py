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


def generate_synthetic_dataset(seed: int = 2026, buildings_per_scenario: int = 4) -> SyntheticDataset:
    """Generate repeatable inputs for normal, overload, tariff, and emergency cases."""
    if buildings_per_scenario < 2:
        raise ValueError("buildings_per_scenario must be at least 2")
    rng = random.Random(seed)
    scenarios = ("normal", "overloaded", "high_tariff", "emergency")
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

    for scenario_index, scenario in enumerate(scenarios):
        transformer_id = f"TX-{scenario_index + 1:02d}"
        capacity = rng.uniform(72, 88)
        connected: list[str] = []
        scenario_buildings: list[Building] = []
        scenario_profiles: list[tuple[float, ...]] = []
        scenario_appliance_profiles: dict[str, tuple[float, ...]] = {}

        for local_index in range(buildings_per_scenario):
            number = scenario_index * buildings_per_scenario + local_index + 1
            building_id = f"B-{number:03d}"
            connected.append(building_id)
            building_type = (BuildingType.RESIDENTIAL, BuildingType.RESIDENTIAL,
                             BuildingType.MIXED_USE, BuildingType.COMMERCIAL)[local_index % 4]
            fixed_kw = rng.uniform(3.0, 5.5)
            flex_kw = rng.uniform(5.0, 9.5)
            occupant_id = f"O-{number:03d}"
            comfort_id = f"CR-{number:03d}"
            opted_out = (number % 7 == 0) or (scenario == "emergency" and local_index == 0)
            occupant = Occupant(occupant_id, building_id, f"Household {number:02d}",
                                comfort_id, opted_out, allow_override=(scenario == "emergency" and local_index == 1))
            comfort = ComfortRange(comfort_id, "temperature_c", 19.0 + rng.choice([0, .5]),
                                   25.0 + rng.choice([0, .5]), rng.choice([21.0, 22.0, 23.0]))
            # Keep the preferred point inside the sampled hard bounds.
            preferred = min(comfort.max_value, max(comfort.min_value, comfort.preferred_value))
            comfort = ComfortRange(comfort.id, comfort.variable, comfort.min_value,
                                   comfort.max_value, preferred)
            occupants.append(occupant)
            comforts[comfort_id] = comfort
            offset = rng.randrange(0, 8)
            occupied = tuple(
                (slot // 4 >= 6 and slot // 4 < 23) if building_type != BuildingType.COMMERCIAL
                else (slot // 4 >= 7 and slot // 4 < 19)
                for slot in range(SLOTS_PER_DAY)
            )
            # Small deterministic variation in arrival/departure for residential patterns.
            if building_type != BuildingType.COMMERCIAL and offset:
                occupied = tuple(value and not (slot // 4 < 6 + offset // 4)
                                 for slot, value in enumerate(occupied))
            occupancy[occupant_id] = occupied
            building = Building(building_id, f"{building_type.value.title()} {number:02d}",
                                transformer_id, building_type, rng.uniform(65, 180),
                                fixed_kw, flex_kw, (occupant_id,))
            buildings.append(building)
            scenario_buildings.append(building)

            # Fixed refrigerator/security load and controllable HVAC/water heating.
            appliances.extend((
                Appliance(f"A-{number:03d}-FR", building_id, "Refrigerator", ApplianceType.REFRIGERATOR,
                         max(0.3, fixed_kw * .16), False, True),
                Appliance(f"A-{number:03d}-HV", building_id, "HVAC", ApplianceType.HVAC,
                         flex_kw * .62, True, True),
                Appliance(f"A-{number:03d}-WH", building_id, "Water heater", ApplianceType.WATER_HEATER,
                         flex_kw * .25, True, local_index % 2 == 0),
                Appliance(f"A-{number:03d}-WM", building_id, "Washer", ApplianceType.WASHING_MACHINE,
                         flex_kw * .13, True, False, preferred_slot=72,
                         max_shift_slots=16, duration_slots=2),
            ))

            values: list[float] = []
            for slot in range(SLOTS_PER_DAY):
                hour = slot / 4
                occupancy_factor = 1.0 if occupied[slot] else .45
                evening_peak = 1.2 if 17 <= hour < 21 else 1.0
                hvac = flex_kw * .48 * occupancy_factor * (1.25 if 14 <= hour < 21 else .75)
                appliance_bump = flex_kw * .16 if (18 <= hour < 20 and local_index % 2 == 0) else 0
                noise = rng.uniform(-.04, .04) * (fixed_kw + flex_kw)
                values.append(max(0.1, (fixed_kw * evening_peak + hvac + appliance_bump + noise)))
            profile = tuple(round(value, 3) for value in values)
            scenario_profiles.append(profile)
            profiles.append(LoadProfile(building_id, profile))

        summed = [sum(values[i] for values in scenario_profiles) for i in range(SLOTS_PER_DAY)]
        peak = max(summed)
        if scenario == "normal":
            rated = max(capacity, peak * 1.18)
        elif scenario == "overloaded":
            rated = min(capacity, peak * .78)
        elif scenario == "emergency":
            rated = min(capacity, peak * .68)
        else:
            rated = max(capacity, peak * 1.05)
        transformer = Transformer(transformer_id, f"Neighborhood Transformer {scenario_index + 1}",
                                  rated, round(peak, 3), tuple(connected), .10)
        transformers.append(transformer)
        scenario_by_transformer[transformer_id] = scenario
        profiles.append(LoadProfile(transformer_id, tuple(round(value, 3) for value in summed)))

        rates = {}
        for slot in range(SLOTS_PER_DAY):
            hour = slot / 4
            # Approximate retail time-of-use rates in INR per kWh.
            rate = 5.5 if hour < 16 else (10.0 if 17 <= hour < 21 else 7.0)
            if scenario in ("high_tariff", "overloaded") and 17 <= hour < 21:
                rate = 18.0
            rates[slot] = rate
        tariffs.append(Tariff(f"TAR-{scenario_index + 1:02d}", f"{scenario.title()} time-of-use", "INR", rates))

        target = max(3.0, peak - rated * .90)
        if scenario == "normal":
            target = min(5.0, max(2.0, peak * .04))
        if scenario == "emergency":
            # Keep the scenario demanding but achievable by the consented
            # emergency override path while preserving hard comfort limits.
            target = max(target, peak - rated * .90)
        event_time = base_time + timedelta(days=scenario_index)
        events.append(DemandResponseEvent(f"DR-{scenario_index + 1:02d}", transformer_id,
            event_time, event_time + timedelta(hours=3), round(target, 2),
            DREventStatus.ACTIVE if scenario in ("overloaded", "emergency") else DREventStatus.PLANNED))

    return SyntheticDataset(tuple(transformers), tuple(buildings), tuple(occupants), tuple(appliances),
        comforts, tuple(tariffs), tuple(events), tuple(profiles), occupancy, scenario_by_transformer)


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
