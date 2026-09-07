from app.infrastructure.solver.ortools_solver import ORToolsSolver


def test_ortools_solver_meets_target_reduction():
    solver = ORToolsSolver()

    reductions = solver.solve(
        flexible_loads={
            "1": 5.0,
            "2": 5.0,
        },
        target_reduction_kw=6.0,
        opted_out_building_ids=set(),
    )

    assert sum(reductions.values()) == 6.0


def test_ortools_solver_does_not_exceed_available_load():
    solver = ORToolsSolver()

    reductions = solver.solve(
        flexible_loads={
            "1": 3.0,
            "2": 2.0,
        },
        target_reduction_kw=10.0,
        opted_out_building_ids=set(),
    )

    assert sum(reductions.values()) <= 5.0


def test_ortools_solver_respects_opted_out_buildings():
    solver = ORToolsSolver()

    reductions = solver.solve(
        flexible_loads={
            "1": 5.0,
            "2": 5.0,
        },
        target_reduction_kw=5.0,
        opted_out_building_ids={"1"},
    )

    assert reductions["1"] == 0.0
    assert reductions["2"] == 5.0


def test_ortools_solver_does_not_exceed_non_opted_out_load():
    solver = ORToolsSolver()

    reductions = solver.solve(
        flexible_loads={
            "1": 4.0,
            "2": 3.0,
        },
        target_reduction_kw=10.0,
        opted_out_building_ids={"1"},
    )

    assert sum(reductions.values()) <= 3.0
    assert reductions["1"] == 0.0