from abc import ABC, abstractmethod
from dataclasses import dataclass, field


@dataclass(frozen=True)
class SchedulableAppliance:
    id: str
    building_id: str
    rated_power_kw: float
    preferred_slot: int
    duration_slots: int
    candidate_slots: tuple[int, ...]


@dataclass(frozen=True)
class OptimizationProblem:
    """Solver input; contains numbers and policy inputs, never infrastructure types."""

    flexible_loads: dict[str, float]
    target_reduction_kw: float
    opted_out_building_ids: set[str]
    capacity_reduction_kw: float = 0.0
    override_building_ids: set[str] = field(default_factory=set)
    maximum_reductions_kw: dict[str, float] = field(default_factory=dict)
    comfort_sensitive_loads_kw: dict[str, float] = field(default_factory=dict)
    maximum_comfort_sensitive_reductions_kw: dict[str, float] = field(default_factory=dict)
    comfort_penalty_per_kw: dict[str, float] = field(default_factory=dict)
    objective_weights: dict[str, float] = field(default_factory=dict)
    tariff_rates: dict[int, float] = field(default_factory=dict)
    schedulable_appliances: tuple[SchedulableAppliance, ...] = ()
    event_slots: tuple[int, ...] = ()


@dataclass(frozen=True)
class OptimizationOutcome:
    reductions_kw: dict[str, float]
    feasible: bool
    required_reduction_kw: float
    available_reduction_kw: float
    status: str
    appliance_slots: dict[str, int] = field(default_factory=dict)
    comfort_sensitive_reductions_kw: dict[str, float] = field(default_factory=dict)


class DemandResponseSolver(ABC):
    """Abstract contract for demand-response optimization solvers."""

    @abstractmethod
    def solve(
        self,
        flexible_loads: dict[str, float],
        target_reduction_kw: float,
        opted_out_building_ids: set[str],
    ) -> dict[str, float]:
        """
        Calculate the reduction assigned to each building.

        Returns:
            Mapping of building_id -> reduction_kw.
        """
        raise NotImplementedError

    def solve_problem(self, problem: OptimizationProblem) -> OptimizationOutcome:
        """Compatibility adapter for existing solvers implementing the original contract."""
        reductions = self.solve(
            flexible_loads=problem.flexible_loads,
            target_reduction_kw=max(problem.target_reduction_kw, problem.capacity_reduction_kw),
            opted_out_building_ids=problem.opted_out_building_ids,
        )
        required = max(problem.target_reduction_kw, problem.capacity_reduction_kw)
        available = sum(reductions.values())
        # Legacy solvers may intentionally return a partial best-effort plan
        # without status diagnostics. Preserve that behavior; capable adapters
        # such as ORToolsSolver provide explicit infeasibility results.
        return OptimizationOutcome(reductions, True, required, available, "legacy_best_effort")
