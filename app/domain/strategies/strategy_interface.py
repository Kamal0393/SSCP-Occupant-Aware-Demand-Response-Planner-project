"""
Module: strategy_interface.py

Purpose:
    Defines the DemandResponseStrategy abstract base class - the single
    interface both the BaselineStrategy (Milestone 3) and OptimizedStrategy
    (Milestone 4) implement. This is what makes "baseline vs intelligent
    planner" a structural comparison rather than two unrelated code paths:
    the ComparisonService (Milestone 6) can run any two strategies
    interchangeably and diff their outputs.

Inputs:
    A PlanningContext (defined here as a lightweight bundle) containing the
    DR event, transformer state, buildings, occupants, comfort ranges, and
    tariff - everything a strategy needs and nothing it should reach outside
    of to fetch.

Outputs:
    list[Decision] - one or more Decisions describing what the strategy
    proposes to do.

Design decisions:
    - PlanningContext is a frozen dataclass assembled once by the
      application-layer PlanningService, so strategies never talk to the
      database or any infrastructure directly (Clean Architecture: domain
      strategies depend only on domain types).
    - generate_plan is the sole abstract method. Both strategies are required
      to return decisions for buildings they *don't* act on too, via
      ActionType.NO_ACTION or OPT_OUT_RESPECTED - this makes "why wasn't this
      building touched" explainable, not just "why was it touched".
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field

from app.domain.entities.building import Building
from app.domain.entities.dr_event import DemandResponseEvent
from app.domain.entities.occupant import Occupant
from app.domain.entities.tariff import Tariff
from app.domain.entities.transformer import Transformer
from app.domain.value_objects.comfort_range import ComfortRange
from app.domain.value_objects.decision import Decision


@dataclass(frozen=True)
class PlanningContext:
    """
    Immutable bundle of everything a strategy needs to produce a plan.

    Attributes:
        dr_event: The event being planned for.
        transformer: The transformer under stress.
        buildings: All buildings connected to the transformer.
        occupants: All occupants across those buildings.
        comfort_ranges: Mapping of comfort_range_id -> ComfortRange.
        tariff: The active tariff (may be partially missing - see
            MissingTariffDataError usage in tariff.py).
        objective_weights: Weighting between competing objectives, e.g.
            {"peak_reduction": 0.6, "comfort": 0.4}. Exposed here so the
            same strategy can be re-run under different weightings to
            demonstrate the trade-off (mandatory requirement).
    """

    dr_event: DemandResponseEvent
    transformer: Transformer
    buildings: tuple[Building, ...]
    occupants: tuple[Occupant, ...]
    comfort_ranges: dict[str, ComfortRange]
    tariff: Tariff | None
    objective_weights: dict[str, float] = field(
        default_factory=lambda: {"peak_reduction": 0.5, "comfort": 0.5}
    )


class DemandResponseStrategy(ABC):
    """
    Common interface for any planning strategy (baseline or optimized).

    Implementations MUST NOT import from infrastructure or application
    layers - they operate purely on domain types passed in via
    PlanningContext, and return domain Decision objects.
    """

    @abstractmethod
    def generate_plan(self, context: PlanningContext) -> list[Decision]:
        """
        Produce a list of Decisions for the given planning context.

        Every building/occupant in context.buildings / context.occupants
        should be represented by at least one Decision (even if it's
        NO_ACTION or OPT_OUT_RESPECTED), so downstream consumers never have
        to infer "silence" as an implicit decision.
        """
        raise NotImplementedError

    @property
    @abstractmethod
    def strategy_name(self) -> str:
        """Short identifier used in comparisons, logs, and the UI (e.g. 'baseline')."""
        raise NotImplementedError
