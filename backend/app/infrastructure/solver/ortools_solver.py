from ortools.sat.python import cp_model

from app.domain.strategies.solver_interface import (
    DemandResponseSolver,
    OptimizationOutcome,
    OptimizationProblem,
)


class ORToolsSolver(DemandResponseSolver):
    """OR-Tools CP-SAT implementation of the demand-response solver."""

    def solve(
        self,
        flexible_loads: dict[str, float],
        target_reduction_kw: float,
        opted_out_building_ids: set[str],
    ) -> dict[str, float]:
        legacy_target = min(
            target_reduction_kw,
            sum(load for building_id, load in flexible_loads.items()
                if building_id not in opted_out_building_ids),
        )
        return self.solve_problem(OptimizationProblem(
            flexible_loads=flexible_loads,
            target_reduction_kw=legacy_target,
            opted_out_building_ids=opted_out_building_ids,
            objective_weights={"peak_reduction": 1.0, "comfort": 0.0},
        )).reductions_kw

    def solve_problem(self, problem: OptimizationProblem) -> OptimizationOutcome:
        scale = 100
        target_kw = max(problem.target_reduction_kw, problem.capacity_reduction_kw)
        if target_kw < 0 or any(value < 0 for value in problem.flexible_loads.values()):
            return OptimizationOutcome({}, False, target_kw, 0.0, "invalid_input")

        general_capacities: dict[str, int] = {}
        sensitive_capacities: dict[str, int] = {}
        for building_id, flexible_kw in problem.flexible_loads.items():
            capacity_kw = min(
                flexible_kw,
                problem.maximum_reductions_kw.get(building_id, flexible_kw),
            )
            sensitive_load_kw = min(capacity_kw, problem.comfort_sensitive_loads_kw.get(building_id, 0.0))
            sensitive_kw = min(
                sensitive_load_kw,
                problem.maximum_comfort_sensitive_reductions_kw.get(building_id, sensitive_load_kw),
            )
            general_kw = max(0.0, capacity_kw - sensitive_load_kw)
            if building_id in problem.opted_out_building_ids and building_id not in problem.override_building_ids:
                capacity_kw = 0.0
                sensitive_kw = 0.0
                general_kw = 0.0
            sensitive_capacities[building_id] = max(0, int(round(sensitive_kw * scale)))
            general_capacities[building_id] = max(0, int(round(general_kw * scale)))

        available = (sum(general_capacities.values()) + sum(sensitive_capacities.values())) / scale
        potential_schedule_relief = sum(
            appliance.rated_power_kw
            for appliance in problem.schedulable_appliances
            if appliance.preferred_slot in problem.event_slots
            and any(slot not in problem.event_slots for slot in appliance.candidate_slots)
        )
        if available + potential_schedule_relief + 1e-9 < target_kw:
            return OptimizationOutcome({}, False, target_kw, available + potential_schedule_relief,
                                       "infeasible_reduction_capacity")

        model = cp_model.CpModel()
        general_variables = {
            building_id: model.new_int_var(0, capacity, f"general_reduction_{building_id}")
            for building_id, capacity in general_capacities.items()
        }
        sensitive_variables = {
            building_id: model.new_int_var(0, capacity, f"comfort_reduction_{building_id}")
            for building_id, capacity in sensitive_capacities.items()
        }
        total = sum(general_variables.values()) + sum(sensitive_variables.values())
        model.add(total <= int(round(target_kw * scale)))

        weights = problem.objective_weights or {"peak_reduction": 1.0, "comfort": 0.0}
        peak_weight = max(0.0, weights.get("peak_reduction", 0.5))
        comfort_weight = max(0.0, weights.get("comfort", 0.5))
        # Each variable unit is 0.01 kW. Normalize the comfort term to a
        # 0..1 loss per building so weights express an interpretable tradeoff.
        objective_terms = []
        for index, (building_id, variable) in enumerate(general_variables.items()):
            coefficient = int(round(1000 * peak_weight / scale)) * 1000 - index
            objective_terms.append(coefficient * variable)
        for index, (building_id, variable) in enumerate(sensitive_variables.items()):
            discomfort = max(0.0, problem.comfort_penalty_per_kw.get(building_id, 0.0))
            coefficient = int(round(1000 * (peak_weight - comfort_weight * discomfort) / scale))
            coefficient = coefficient * 1000 - index - len(general_variables)
            objective_terms.append(coefficient * variable)

        schedule_variables = {}
        schedule_relief_terms = []
        energy_cost_weight = max(0.0, weights.get(
            "energy_cost", 0.25 if problem.tariff_rates else 0.0
        ))
        for appliance in problem.schedulable_appliances:
            candidates = appliance.candidate_slots or (appliance.preferred_slot,)
            choices = {
                slot: model.new_bool_var(f"schedule_{appliance.id}_{slot}")
                for slot in candidates
            }
            model.add(sum(choices.values()) == 1)
            schedule_variables[appliance.id] = choices
            for slot, choice in choices.items():
                cost = (problem.tariff_rates.get(slot, 0.0)
                        * appliance.rated_power_kw * appliance.duration_slots * 0.25)
                outside_event = slot not in problem.event_slots
                event_relief = (peak_weight * appliance.rated_power_kw * 500_000
                                if appliance.preferred_slot in problem.event_slots and outside_event else 0)
                shift_penalty = comfort_weight * abs(slot - appliance.preferred_slot) * 1000
                schedule_score = event_relief - energy_cost_weight * cost * 100_000 - shift_penalty
                objective_terms.append(int(round(schedule_score)) * choice)
                if appliance.preferred_slot in problem.event_slots and slot not in problem.event_slots:
                    schedule_relief_terms.append(int(round(appliance.rated_power_kw * scale)) * choice)
        model.add(total + sum(schedule_relief_terms) >= int(round(target_kw * scale)))
        model.maximize(sum(objective_terms))

        solver = cp_model.CpSolver()
        solver.parameters.num_search_workers = 1
        status = solver.solve(model)
        if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
            return OptimizationOutcome({}, False, target_kw, available, "infeasible")

        sensitive_reductions = {key: solver.value(value) / scale
                                for key, value in sensitive_variables.items()}
        reductions = {
            key: (solver.value(general_variables[key]) + solver.value(sensitive_variables[key])) / scale
            for key in general_variables
        }
        appliance_slots = {
            appliance_id: next(slot for slot, choice in choices.items() if solver.value(choice))
            for appliance_id, choices in schedule_variables.items()
        }
        shifted_relief = sum(
            appliance.rated_power_kw
            for appliance in problem.schedulable_appliances
            if appliance.preferred_slot in problem.event_slots
            and appliance_slots.get(appliance.id) not in problem.event_slots
        )
        return OptimizationOutcome(reductions, True, target_kw,
                                   sum(reductions.values()) + shifted_relief,
                                   "optimal" if status == cp_model.OPTIMAL else "feasible",
                                   appliance_slots, sensitive_reductions)
