from abc import ABC, abstractmethod


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
    