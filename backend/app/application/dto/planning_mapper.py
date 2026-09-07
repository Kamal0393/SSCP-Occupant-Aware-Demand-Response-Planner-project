from app.api.schemas.planning import PlanningRequestSchema
from app.domain.entities.building import Building
from app.domain.entities.dr_event import DemandResponseEvent
from app.domain.entities.occupant import Occupant
from app.domain.entities.tariff import Tariff
from app.domain.entities.transformer import Transformer
from app.domain.strategies.strategy_interface import PlanningContext
from app.domain.value_objects.comfort_range import ComfortRange


def to_domain_context(request: PlanningRequestSchema) -> PlanningContext:
    dr_event = DemandResponseEvent(
        id=request.dr_event.id,
        transformer_id=request.dr_event.transformer_id,
        start_time=request.dr_event.start_time,
        end_time=request.dr_event.end_time,
        target_reduction_kw=request.dr_event.target_reduction_kw,
        status=request.dr_event.status,
    )

    transformer = Transformer(
        id=request.transformer.id,
        name=request.transformer.name,
        rated_capacity_kw=request.transformer.rated_capacity_kw,
        current_load_kw=request.transformer.current_load_kw,
        connected_building_ids=request.transformer.connected_building_ids,
        safety_margin_pct=request.transformer.safety_margin_pct,
    )

    buildings = tuple(
        Building(
            id=building.id,
            name=building.name,
            transformer_id=building.transformer_id,
            building_type=building.building_type,
            floor_area_sqm=building.floor_area_sqm,
            fixed_load_kw=building.fixed_load_kw,
            flexible_load_kw=building.flexible_load_kw,
            occupant_ids=building.occupant_ids,
        )
        for building in request.buildings
    )

    occupants = tuple(
        Occupant(
            id=occupant.id,
            building_id=occupant.building_id,
            display_name=occupant.display_name,
            comfort_range_id=occupant.comfort_range_id,
            opted_out=occupant.opted_out,
            allow_override=occupant.allow_override,
        )
        for occupant in request.occupants
    )

    comfort_ranges = {
        range_id: ComfortRange(
            id=comfort.id,
            variable=comfort.variable,
            min_value=comfort.min_value,
            max_value=comfort.max_value,
            preferred_value=comfort.preferred_value,
        )
        for range_id, comfort in request.comfort_ranges.items()
    }

    tariff = None
    if request.tariff is not None:
        tariff = Tariff(
            id=request.tariff.id,
            name=request.tariff.name,
            currency=request.tariff.currency,
            rate_per_slot=request.tariff.rate_per_slot,
        )

    return PlanningContext(
        dr_event=dr_event,
        transformer=transformer,
        buildings=buildings,
        occupants=occupants,
        comfort_ranges=comfort_ranges,
        tariff=tariff,
        objective_weights={
            "peak_reduction": request.objective_weights.peak_reduction,
            "comfort": request.objective_weights.comfort,
        },
    )