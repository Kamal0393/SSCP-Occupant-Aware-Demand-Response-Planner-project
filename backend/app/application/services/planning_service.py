from app.domain.strategies.strategy_interface import (
    DemandResponseStrategy,
    PlanningContext,
)
from app.domain.value_objects.decision import Decision
from app.core.exceptions import OccupancySensorFailureError


class PlanningService:
    """Application service responsible for executing a planning strategy."""

    def __init__(self, strategy: DemandResponseStrategy) -> None:
        self._strategy = strategy

    def generate_plan(
        self,
        context: PlanningContext,
    ) -> list[Decision]:
        if context.occupancy_sensor_status != "available":
            raise OccupancySensorFailureError(
                f"Occupancy sensor data is {context.occupancy_sensor_status}; planning was not run"
            )
        return self._strategy.generate_plan(context)
