from datetime import datetime, timedelta, timezone
import json
from dataclasses import replace

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.domain.entities.appliance import Appliance, ApplianceType
from app.domain.entities.building import Building, BuildingType
from app.domain.entities.dr_event import DemandResponseEvent
from app.domain.entities.occupant import Occupant
from app.domain.entities.tariff import Tariff
from app.domain.entities.transformer import Transformer
from app.domain.value_objects.comfort_range import ComfortRange
from app.domain.value_objects.decision import ActionType, Decision
from app.domain.value_objects.load_profile import LoadProfile
from app.infrastructure.data_generation.synthetic import (
    dataset_to_dict, generate_synthetic_dataset, seed_database,
)
from app.infrastructure.db.models import (
    ApplianceModel, BuildingModel, ComfortRangeModel, DREventModel,
    ExplanationModel, LoadProfileModel, OccupancyPatternModel, OccupantModel,
    PlanningHistoryModel, PlanningResultModel, TariffModel, TransformerModel,
)
from app.infrastructure.db.repositories import (
    ApplianceRepository, BuildingRepository, ComfortRangeRepository,
    DecisionRepository, DREventRepository, ExplanationRecord,
    ExplanationRepository, LoadProfileRepository, OccupantRepository,
    PlanningHistoryRecord, PlanningHistoryRepository, PlanningResultRecord,
    PlanningResultRepository, TariffRepository, TransformerRepository,
)
from app.infrastructure.db.session import create_database_engine, initialize_database


def make_session() -> Session:
    engine = create_database_engine("sqlite:///:memory:")
    initialize_database(engine)
    return Session(engine)


def test_domain_repository_round_trips_and_planning_audit_records():
    with make_session() as session:
        transformer = Transformer("tx", "TX", 100, 45, ("b",))
        building = Building("b", "Building", "tx", BuildingType.RESIDENTIAL, 90, 2, 5, ("o",))
        occupant = Occupant("o", "b", "Household", "comfort")
        appliance = Appliance("a", "b", "HVAC", ApplianceType.HVAC, 2.5, True, True)
        tariff = Tariff("tar", "TOU", "INR", {0: .12, 70: .62})
        now = datetime(2026, 1, 1, tzinfo=timezone.utc)
        event = DemandResponseEvent("dr", "tx", now, now + timedelta(hours=1), 4)
        comfort = ComfortRange("comfort", "temperature_c", 19, 26, 22)

        TransformerRepository(session).add(transformer)
        BuildingRepository(session).add(building)
        OccupantRepository(session).add(occupant)
        ApplianceRepository(session).add(appliance)
        TariffRepository(session).add(tariff)
        DREventRepository(session).add(event)
        ComfortRangeRepository(session).add(comfort)
        LoadProfileRepository(session).add(LoadProfile("b", (2.0, 3.0)))

        assert TransformerRepository(session).get("tx") == transformer
        assert BuildingRepository(session).get("b") == building
        assert OccupantRepository(session).get("o") == occupant
        assert ApplianceRepository(session).get("a") == appliance
        assert TariffRepository(session).get("tar") == tariff
        assert DREventRepository(session).get("dr") == event
        assert ComfortRangeRepository(session).get("comfort") == comfort
        assert LoadProfileRepository(session).get("b") == LoadProfile("b", (2.0, 3.0))

        result = PlanningResultRecord("result", "dr", "optimized", objective_weights={"peak_reduction": .7})
        PlanningResultRepository(session).add(result)
        decision = Decision(id="d1", dr_event_id="dr", building_id="b", slot_index=3,
            action=ActionType.REDUCE_SETPOINT, triggering_constraint="test",
            objective_weights_used={"peak_reduction": .7}, estimated_reduction_kw=1.2)
        DecisionRepository(session).add_for_result(decision, "result")
        ExplanationRepository(session).add(ExplanationRecord("exp1", "d1", "Reduced load for event."))
        PlanningHistoryRepository(session).add(PlanningHistoryRecord(None, "result", "generated"))
        assert DecisionRepository(session).by_result("result") == [decision]
        assert ExplanationRepository(session).get("exp1").text == "Reduced load for event."
        assert PlanningHistoryRepository(session).by_result("result")[0].action == "generated"
        session.commit()


def test_synthetic_generation_is_deterministic_and_covers_required_cases():
    first = generate_synthetic_dataset(seed=17)
    second = generate_synthetic_dataset(seed=17)
    assert first == second
    assert len(first.buildings) >= 12
    assert any(t.is_overloaded for t in first.transformers)
    assert any(not t.is_overloaded for t in first.transformers)
    assert any(o.opted_out for o in first.occupants)
    assert any(o.allow_override for o in first.occupants)
    assert any(a.is_flexible for a in first.appliances)
    assert any(not a.is_flexible for a in first.appliances)
    assert any(scenario == "high_tariff" for scenario in first.scenario_by_transformer.values())
    assert all(len(pattern) == 96 for pattern in first.occupancy_patterns.values())
    assert all(len(profile.values_kw) == 96 for profile in first.load_profiles)
    assert len(first.events) >= 3


def test_synthetic_generation_changes_across_seeds_and_respects_configured_counts():
    first = generate_synthetic_dataset(
        seed=101, building_count=6, transformer_count=3,
        occupants_per_building=2, appliances_per_building=5,
        intervals_per_profile=32,
    )
    repeat = generate_synthetic_dataset(
        seed=101, building_count=6, transformer_count=3,
        occupants_per_building=2, appliances_per_building=5,
        intervals_per_profile=32,
    )
    other_seed = generate_synthetic_dataset(
        seed=102, building_count=6, transformer_count=3,
        occupants_per_building=2, appliances_per_building=5,
        intervals_per_profile=32,
    )

    assert first == repeat
    assert first != other_seed
    assert len(first.transformers) == 3
    assert len(first.buildings) == 6
    assert len(first.occupants) == 12
    assert len(first.appliances) == 30
    assert len(first.events) == len(first.tariffs) == 3
    assert first.config.seed == 101
    assert first.config.intervals_per_profile == 32


def test_synthetic_export_schema_relationships_ranges_and_time_series_consistency():
    dataset = generate_synthetic_dataset(
        seed=37, building_count=8, transformer_count=4,
        occupants_per_building=2, appliances_per_building=4,
        intervals_per_profile=48,
    )
    exported = dataset_to_dict(dataset)

    assert exported["schema_version"] == "1.0"
    assert exported["generation"]["seed"] == 37
    assert exported["generation"]["parameters"]["interval_minutes"] == 15
    assert exported["generation"]["counts"]["time_series_intervals"] == 12 * 48
    assert len(exported["buildings"]) == 8
    assert len(exported["occupants"]) == 16
    assert len(exported["appliances"]) == 32

    transformer_ids = {row["id"] for row in exported["transformers"]}
    building_ids = {row["id"] for row in exported["buildings"]}
    occupant_ids = {row["id"] for row in exported["occupants"]}
    for building in exported["buildings"]:
        assert building["transformer_id"] in transformer_ids
        assert set(building["occupant_ids"]) <= occupant_ids
        assert building["floor_area_sqm"] > 0
        assert building["fixed_load_kw"] >= 0 and building["flexible_load_kw"] >= 0
    for appliance in exported["appliances"]:
        assert appliance["building_id"] in building_ids
        assert appliance["rated_power_kw"] > 0
        assert appliance["preferred_slot"] is None or 0 <= appliance["preferred_slot"] < 96
    for comfort in exported["comfort_ranges"]:
        assert comfort["min_value"] < comfort["max_value"]
        assert comfort["min_value"] <= comfort["preferred_value"] <= comfort["max_value"]
        assert comfort["unit"] == "degC"
    for pattern in exported["occupancy_patterns"]:
        assert len(pattern["occupied_by_interval"]) == 48
        assert all(isinstance(value, bool) for value in pattern["occupied_by_interval"])
    for profile in exported["load_profiles"]:
        assert profile["interval_minutes"] == 15
        assert len(profile["intervals"]) == 48
        assert all(row["demand_kw"] >= 0 for row in profile["intervals"])
        timestamps = [datetime.fromisoformat(row["timestamp"]) for row in profile["intervals"]]
        assert all((right - left).total_seconds() == 15 * 60
                   for left, right in zip(timestamps, timestamps[1:]))
    profiles_by_entity = {profile["entity_id"]: profile["intervals"]
                          for profile in exported["load_profiles"]}
    for transformer in exported["transformers"]:
        transformer_series = profiles_by_entity[transformer["id"]]
        for interval_index, transformer_sample in enumerate(transformer_series):
            building_total = sum(
                profiles_by_entity[building_id][interval_index]["demand_kw"]
                for building_id in transformer["connected_building_ids"]
            )
            assert transformer_sample["demand_kw"] == pytest.approx(building_total, abs=0.001)

    for tariff in exported["tariffs"]:
        assert tariff["rate_unit"] == "INR/kWh"
        assert len(tariff["rate_per_slot"]) == 96
        assert all(rate >= 0 for rate in tariff["rate_per_slot"].values())
    for event in exported["demand_response_events"]:
        assert event["transformer_id"] in transformer_ids
        assert event["target_reduction_kw"] > 0
        assert datetime.fromisoformat(event["end_time"]) > datetime.fromisoformat(event["start_time"])

    encoded = json.dumps(exported, sort_keys=True)
    assert encoded == json.dumps(dataset_to_dict(generate_synthetic_dataset(
        seed=37, building_count=8, transformer_count=4,
        occupants_per_building=2, appliances_per_building=4,
        intervals_per_profile=48,
    )), sort_keys=True)


def test_synthetic_generation_rejects_inconsistent_generation_counts():
    with pytest.raises(ValueError, match="building_count must be at least transformer_count"):
        generate_synthetic_dataset(building_count=2, transformer_count=3)
    with pytest.raises(ValueError, match="intervals_per_profile must be at least 1"):
        generate_synthetic_dataset(intervals_per_profile=0)

def test_overload_demo_combines_opt_out_high_tariff_and_shiftable_appliances():
    dataset = generate_synthetic_dataset()
    overloaded = next(t for t in dataset.transformers if t.id == "TX-02")
    event = next(e for e in dataset.events if e.transformer_id == overloaded.id)
    tariff = next(t for t in dataset.tariffs if t.id == "TAR-02")
    connected = {b.id for b in dataset.buildings if b.transformer_id == overloaded.id}
    occupants = [o for o in dataset.occupants if o.building_id in connected]
    washers = [a for a in dataset.appliances if a.building_id in connected and a.name == "Washer"]
    assert overloaded.is_overloaded
    assert event.status.value == "active"
    assert any(o.opted_out for o in occupants)
    assert tariff.get_rate(72) == 18.0
    assert washers and all(a.is_flexible and not a.is_running and a.max_shift_slots > 0 for a in washers)


def test_seed_database_persists_input_data_without_inventing_plan_results():
    dataset = generate_synthetic_dataset(seed=9)
    with make_session() as session:
        seed_database(session, dataset)
        assert len(session.scalars(select(TransformerModel)).all()) == len(dataset.transformers)
        assert len(session.scalars(select(BuildingModel)).all()) == len(dataset.buildings)
        assert len(session.scalars(select(OccupantModel)).all()) == len(dataset.occupants)
        assert len(session.scalars(select(ApplianceModel)).all()) == len(dataset.appliances)
        assert all(a.preferred_slot == 72 for a in session.scalars(select(ApplianceModel)).all()
                   if a.name == "Washer")
        assert len(session.scalars(select(ComfortRangeModel)).all()) == len(dataset.occupants)
        assert len(session.scalars(select(TariffModel)).all()) == len(dataset.tariffs)
        assert len(session.scalars(select(DREventModel)).all()) == len(dataset.events)
        assert len(session.scalars(select(LoadProfileModel)).all()) == len(dataset.load_profiles)
        assert len(session.scalars(select(OccupancyPatternModel)).all()) == len(dataset.occupants)
        assert session.scalars(select(PlanningResultModel)).all() == []
        assert session.scalars(select(ExplanationModel)).all() == []
        assert session.scalars(select(PlanningHistoryModel)).all() == []


def test_seed_database_rolls_back_all_rows_on_foreign_key_failure():
    dataset = generate_synthetic_dataset(seed=23)
    invalid_dataset = replace(dataset, transformers=())
    with make_session() as session:
        with pytest.raises(IntegrityError):
            seed_database(session, invalid_dataset)
        assert session.scalars(select(TransformerModel)).all() == []
        assert session.scalars(select(BuildingModel)).all() == []


def test_repository_upsert_and_delete_contract():
    with make_session() as session:
        TransformerRepository(session).add(Transformer("tx", "TX", 100, 20, ("b",)))
        BuildingRepository(session).add(
            Building("b", "Building", "tx", BuildingType.RESIDENTIAL, 90, 2, 5, ())
        )
        repository = ApplianceRepository(session)
        appliance = Appliance("a", "b", "Washer", ApplianceType.WASHING_MACHINE, 1.2, True, False)
        repository.add(appliance)
        updated = replace(appliance, rated_power_kw=1.5)
        repository.add(updated)
        assert repository.get("a").rated_power_kw == 1.5
        assert repository.delete("a") is True
        assert repository.get("a") is None
        assert repository.delete("missing") is False
