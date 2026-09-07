from datetime import datetime, timedelta

from app.domain.entities.building import Building, BuildingType
from app.domain.entities.dr_event import DemandResponseEvent
from app.domain.entities.transformer import Transformer
from app.domain.strategies.baseline_strategy import BaselineStrategy
from app.domain.strategies.strategy_interface import PlanningContext
from app.domain.value_objects.decision import ActionType


def create_context(
    buildings: tuple[Building, ...],
    target_reduction_kw: float = 3.0,
) -> PlanningContext:
    start_time = datetime(2026, 8, 14, 18, 0)
    end_time = start_time + timedelta(hours=1)

    event = DemandResponseEvent(
        id="DR1",
        transformer_id="T1",
        start_time=start_time,
        end_time=end_time,
        target_reduction_kw=target_reduction_kw,
    )

    transformer = Transformer(
        id="T1",
        name="Transformer T1",
        rated_capacity_kw=20.0,
        current_load_kw=18.0,
        connected_building_ids=tuple(
            building.id for building in buildings
        ),
    )

    return PlanningContext(
        dr_event=event,
        transformer=transformer,
        buildings=buildings,
        occupants=(),
        comfort_ranges={},
        tariff=None,
    )


def test_baseline_reduces_flexible_load():
    buildings = (
        Building(
            id="B1",
            name="Building 1",
            transformer_id="T1",
            building_type=BuildingType.RESIDENTIAL,
            floor_area_sqm=100,
            fixed_load_kw=2.0,
            flexible_load_kw=4.0,
        ),
    )

    context = create_context(buildings, target_reduction_kw=3.0)

    decisions = BaselineStrategy().generate_plan(context)

    decision = decisions[0]

    assert decision.action == ActionType.REDUCE_SETPOINT
    assert decision.before_value == 4.0
    assert decision.after_value == 1.0
    assert decision.estimated_reduction_kw == 3.0


def test_baseline_never_reduces_fixed_load():
    buildings = (
        Building(
            id="B1",
            name="Building 1",
            transformer_id="T1",
            building_type=BuildingType.RESIDENTIAL,
            floor_area_sqm=100,
            fixed_load_kw=5.0,
            flexible_load_kw=2.0,
        ),
    )

    context = create_context(buildings, target_reduction_kw=1.0)

    decisions = BaselineStrategy().generate_plan(context)

    decision = decisions[0]

    assert decision.before_value == 2.0
    assert decision.after_value == 1.0
    assert decision.estimated_reduction_kw == 1.0


def test_baseline_does_not_reduce_more_than_available_flexible_load():
    buildings = (
        Building(
            id="B1",
            name="Building 1",
            transformer_id="T1",
            building_type=BuildingType.RESIDENTIAL,
            floor_area_sqm=100,
            fixed_load_kw=2.0,
            flexible_load_kw=1.5,
        ),
    )

    context = create_context(buildings, target_reduction_kw=5.0)

    decisions = BaselineStrategy().generate_plan(context)

    decision = decisions[0]

    assert decision.action == ActionType.REDUCE_SETPOINT
    assert decision.before_value == 1.5
    assert decision.after_value == 0.0
    assert decision.estimated_reduction_kw == 1.5


def test_baseline_handles_multiple_buildings_in_id_order():
    buildings = (
        Building(
            id="B2",
            name="Building 2",
            transformer_id="T1",
            building_type=BuildingType.RESIDENTIAL,
            floor_area_sqm=100,
            fixed_load_kw=1.0,
            flexible_load_kw=2.0,
        ),
        Building(
            id="B1",
            name="Building 1",
            transformer_id="T1",
            building_type=BuildingType.RESIDENTIAL,
            floor_area_sqm=100,
            fixed_load_kw=1.0,
            flexible_load_kw=3.0,
        ),
    )

    context = create_context(buildings, target_reduction_kw=4.0)

    decisions = BaselineStrategy().generate_plan(context)

    assert len(decisions) == 2
    assert decisions[0].building_id == "B1"
    assert decisions[1].building_id == "B2"

    assert decisions[0].estimated_reduction_kw == 3.0
    assert decisions[1].estimated_reduction_kw == 1.0


def test_baseline_returns_no_action_after_target_is_reached():
    buildings = (
        Building(
            id="B1",
            name="Building 1",
            transformer_id="T1",
            building_type=BuildingType.RESIDENTIAL,
            floor_area_sqm=100,
            fixed_load_kw=1.0,
            flexible_load_kw=3.0,
        ),
        Building(
            id="B2",
            name="Building 2",
            transformer_id="T1",
            building_type=BuildingType.RESIDENTIAL,
            floor_area_sqm=100,
            fixed_load_kw=1.0,
            flexible_load_kw=3.0,
        ),
    )

    context = create_context(buildings, target_reduction_kw=2.0)

    decisions = BaselineStrategy().generate_plan(context)

    assert decisions[0].action == ActionType.REDUCE_SETPOINT
    assert decisions[0].estimated_reduction_kw == 2.0

    assert decisions[1].action == ActionType.NO_ACTION
    assert decisions[1].estimated_reduction_kw == 0.0


def test_baseline_preserves_objective_weights():
    buildings = (
        Building(
            id="B1",
            name="Building 1",
            transformer_id="T1",
            building_type=BuildingType.RESIDENTIAL,
            floor_area_sqm=100,
            fixed_load_kw=1.0,
            flexible_load_kw=2.0,
        ),
    )

    context = create_context(buildings, target_reduction_kw=1.0)
    context.objective_weights.update(
        {
            "peak_reduction": 0.8,
            "comfort": 0.2,
        }
    )

    decisions = BaselineStrategy().generate_plan(context)

    assert decisions[0].objective_weights_used == {
        "peak_reduction": 0.8,
        "comfort": 0.2,
    }
    