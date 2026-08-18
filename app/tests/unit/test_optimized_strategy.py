from datetime import datetime

from app.domain.entities.building import Building
from app.domain.entities.dr_event import DemandResponseEvent
from app.domain.entities.occupant import Occupant
from app.domain.entities.tariff import Tariff
from app.domain.entities.transformer import Transformer
from app.domain.strategies.optimized_strategy import OptimizedStrategy
from app.domain.strategies.strategy_interface import PlanningContext


def test_optimized_strategy_meets_target_reduction():
    buildings = (
        Building(
            id=1,
            name="Building 1",
            transformer_id="T1",
            building_type="residential",
            floor_area_sqm=100.0,
            fixed_load_kw=2.0,
            flexible_load_kw=5.0,
        ),
        Building(
            id=2,
            name="Building 2",
            transformer_id="T1",
            building_type="residential",
            floor_area_sqm=100.0,
            fixed_load_kw=2.0,
            flexible_load_kw=5.0,
        ),
    )

    transformer = Transformer(
        id="T1",
        name="Transformer T1",
        rated_capacity_kw=20.0,
        current_load_kw=14.0,
        connected_building_ids=("1", "2"),
    )

    occupants = (
        Occupant(
            id="O1",
            building_id="1",
            display_name="Occupant 1",
            comfort_range_id="CR1",
        ),
        Occupant(
            id="O2",
            building_id="2",
            display_name="Occupant 2",
            comfort_range_id="CR1",
        ),
    )

    tariff = Tariff(
        id="TARIFF1",
        name="Test Tariff",
        currency="INR",
        rate_per_slot={0: 5.0},
    )

    dr_event = DemandResponseEvent(
        id="DR1",
        transformer_id="T1",
        start_time=datetime(2026, 1, 1, 18, 0),
        end_time=datetime(2026, 1, 1, 19, 0),
        target_reduction_kw=6.0,
    )

    context = PlanningContext(
        dr_event=dr_event,
        transformer=transformer,
        buildings=buildings,
        occupants=occupants,
        comfort_ranges={},
        tariff=tariff,
    )

    strategy = OptimizedStrategy()
    decisions = strategy.generate_plan(context)

    total_reduction = sum(
        decision.estimated_reduction_kw for decision in decisions
    )

    assert total_reduction == 6.0


def test_optimized_strategy_does_not_exceed_available_flexible_load():
    buildings = (
        Building(
            id=1,
            name="Building 1",
            transformer_id="T1",
            building_type="residential",
            floor_area_sqm=100.0,
            fixed_load_kw=2.0,
            flexible_load_kw=3.0,
        ),
        Building(
            id=2,
            name="Building 2",
            transformer_id="T1",
            building_type="residential",
            floor_area_sqm=100.0,
            fixed_load_kw=2.0,
            flexible_load_kw=2.0,
        ),
    )

    transformer = Transformer(
        id="T1",
        name="Transformer T1",
        rated_capacity_kw=20.0,
        current_load_kw=14.0,
        connected_building_ids=("1", "2"),
    )

    occupants = (
        Occupant(
            id="O1",
            building_id="1",
            display_name="Occupant 1",
            comfort_range_id="CR1",
        ),
        Occupant(
            id="O2",
            building_id="2",
            display_name="Occupant 2",
            comfort_range_id="CR1",
        ),
    )

    tariff = Tariff(
        id="TARIFF1",
        name="Test Tariff",
        currency="INR",
        rate_per_slot={0: 5.0},
    )

    dr_event = DemandResponseEvent(
        id="DR2",
        transformer_id="T1",
        start_time=datetime(2026, 1, 1, 18, 0),
        end_time=datetime(2026, 1, 1, 19, 0),
        target_reduction_kw=10.0,
    )

    context = PlanningContext(
        dr_event=dr_event,
        transformer=transformer,
        buildings=buildings,
        occupants=occupants,
        comfort_ranges={},
        tariff=tariff,
    )

    strategy = OptimizedStrategy()
    decisions = strategy.generate_plan(context)

    total_reduction = sum(
        decision.estimated_reduction_kw for decision in decisions
    )

    assert total_reduction <= 5.0


def test_optimized_strategy_respects_opted_out_occupant():
    buildings = (
        Building(
            id=1,
            name="Building 1",
            transformer_id="T1",
            building_type="residential",
            floor_area_sqm=100.0,
            fixed_load_kw=2.0,
            flexible_load_kw=5.0,
        ),
        Building(
            id=2,
            name="Building 2",
            transformer_id="T1",
            building_type="residential",
            floor_area_sqm=100.0,
            fixed_load_kw=2.0,
            flexible_load_kw=5.0,
        ),
    )

    transformer = Transformer(
        id="T1",
        name="Transformer T1",
        rated_capacity_kw=20.0,
        current_load_kw=14.0,
        connected_building_ids=("1", "2"),
    )

    occupants = (
        Occupant(
            id="O1",
            building_id="1",
            display_name="Opted Out Occupant",
            comfort_range_id="CR1",
            opted_out=True,
        ),
        Occupant(
            id="O2",
            building_id="2",
            display_name="Participating Occupant",
            comfort_range_id="CR1",
            opted_out=False,
        ),
    )

    tariff = Tariff(
        id="TARIFF1",
        name="Test Tariff",
        currency="INR",
        rate_per_slot={0: 5.0},
    )

    dr_event = DemandResponseEvent(
        id="DR3",
        transformer_id="T1",
        start_time=datetime(2026, 1, 1, 18, 0),
        end_time=datetime(2026, 1, 1, 19, 0),
        target_reduction_kw=5.0,
    )

    context = PlanningContext(
        dr_event=dr_event,
        transformer=transformer,
        buildings=buildings,
        occupants=occupants,
        comfort_ranges={},
        tariff=tariff,
    )

    strategy = OptimizedStrategy()
    decisions = strategy.generate_plan(context)

    opted_out_decisions = [
        decision
        for decision in decisions
        if decision.building_id == "1"
    ]

    assert all(
        decision.estimated_reduction_kw == 0.0
        for decision in opted_out_decisions
    )

    assert any(
        decision.building_id == 2
        and decision.estimated_reduction_kw > 0
        for decision in decisions
    )