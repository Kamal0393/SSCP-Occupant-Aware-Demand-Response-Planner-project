from ortools.sat.python import cp_model

from app.domain.strategies.solver_interface import DemandResponseSolver


class ORToolsSolver(DemandResponseSolver):
    """OR-Tools CP-SAT implementation of the demand-response solver."""

    def solve(
        self,
        flexible_loads: dict[str, float],
        target_reduction_kw: float,
        opted_out_building_ids: set[str],
    ) -> dict[str, float]:
        model = cp_model.CpModel()

        scale = 100
        reduction_vars = {}

        for building_id, flexible_load_kw in flexible_loads.items():
            max_reduction = int(round(flexible_load_kw * scale))

            if building_id in opted_out_building_ids:
                max_reduction = 0

            reduction_vars[building_id] = model.new_int_var(
                0,
                max_reduction,
                f"reduction_{building_id}",
            )

        target_reduction = int(
            round(target_reduction_kw * scale)
        )

        model.add(
            sum(reduction_vars.values()) <= target_reduction
        )

        model.maximize(
            sum(reduction_vars.values())
        )

        solver = cp_model.CpSolver()
        status = solver.solve(model)

        if status not in (
            cp_model.OPTIMAL,
            cp_model.FEASIBLE,
        ):
            return {}

        return {
            building_id: (
                solver.value(variable) / scale
            )
            for building_id, variable in reduction_vars.items()
        }