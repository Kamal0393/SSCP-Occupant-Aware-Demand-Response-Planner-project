from datetime import datetime

from app.application.services.planning_service import PlanningService
from app.domain.entities.building import Building
from app.domain.entities.dr_event import DemandResponseEvent
from app.domain.entities.occupant import Occupant
from app.domain.entities.transformer import Transformer
from app.domain.strategies.strategy_interface import PlanningContext
from app.domain.strategies.baseline_strategy import BaselineStrategy
from app.application.services.explanation_service import ExplanationService


def test_planning_service_generates_plan_with_optimized_strategy():
    buildings = (
        Building(
            id="1",
            name="Building 1",
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
        connected_building_ids=("1",),
    )

    occupants = (
        Occupant(
            id="O1",
            building_id="1",
            display_name="Occupant 1",
            comfort_range_id="CR1",
        ),
    )

    dr_event = DemandResponseEvent(
        id="DR1",
        transformer_id="T1",
        start_time=datetime(2026, 1, 1, 18, 0),
        end_time=datetime(2026, 1, 1, 19, 0),
        target_reduction_kw=3.0,
    )

    context = PlanningContext(
        dr_event=dr_event,
        transformer=transformer,
        buildings=buildings,
        occupants=occupants,
        comfort_ranges={},
        tariff=None,
    )

    service = PlanningService()
    decisions = service.generate_plan(context)

    assert len(decisions) == 1
    assert decisions[0].building_id == "1"
    assert decisions[0].estimated_reduction_kw == 3.0


def test_planning_service_can_use_baseline_strategy():
    buildings = (
        Building(
            id="1",
            name="Building 1",
            transformer_id="T1",
            building_type="residential",
            floor_area_sqm=100.0,
            fixed_load_kw=2.0,
            flexible_load_kw=5.0,
        ),
        Building(
            id="2",
            name="Building 2",
            transformer_id="T1",
            building_type="residential",
            floor_area_sqm=100.0,
            fixed_load_kw=2.0,
            flexible_load_kw=4.0,
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

    dr_event = DemandResponseEvent(
        id="DR2",
        transformer_id="T1",
        start_time=datetime(2026, 1, 1, 18, 0),
        end_time=datetime(2026, 1, 1, 19, 0),
        target_reduction_kw=3.0,
    )

    context = PlanningContext(
        dr_event=dr_event,
        transformer=transformer,
        buildings=buildings,
        occupants=occupants,
        comfort_ranges={},
        tariff=None,
    )

    service = PlanningService(strategy=BaselineStrategy())
    decisions = service.generate_plan(context)

    assert len(decisions) == 2
    assert decisions[0].building_id == "1"
    assert decisions[0].estimated_reduction_kw == 3.0

def test_planning_decisions_can_be_explained():
    buildings = (
        Building(
            id="1",
            name="Building 1",
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
        connected_building_ids=("1",),
    )

    occupants = (
        Occupant(
            id="O1",
            building_id="1",
            display_name="Occupant 1",
            comfort_range_id="CR1",
        ),
    )

    dr_event = DemandResponseEvent(
        id="DR3",
        transformer_id="T1",
        start_time=datetime(2026, 1, 1, 18, 0),
        end_time=datetime(2026, 1, 1, 19, 0),
        target_reduction_kw=3.0,
    )

    context = PlanningContext(
        dr_event=dr_event,
        transformer=transformer,
        buildings=buildings,
        occupants=occupants,
        comfort_ranges={},
        tariff=None,
    )

    planning_service = PlanningService()
    explanation_service = ExplanationService()

    decisions = planning_service.generate_plan(context)
    explanation = explanation_service.explain(decisions[0])

    assert "Building 1" in explanation
    assert "1" in explanation
    assert "3.0 kW" in explanation
