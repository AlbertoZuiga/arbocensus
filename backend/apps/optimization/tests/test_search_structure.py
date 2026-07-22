import numpy as np
import pytest
from apps.optimization.solver import (
    ArbocensusVRPSolver,
    inverse_permutation,
    node_permutation,
)


def unwrap(result):
    assert result is not None
    return result


def uniform_matrix(n, travel=60.0):
    m = np.full((n, n), travel)
    np.fill_diagonal(m, 0.0)
    return m


def build_solver(n, **kwargs):
    return ArbocensusVRPSolver(
        uniform_matrix(n),
        min_route_time_sec=600,
        max_route_time_sec=100_000,
        service_time_sec=300,
        max_vehicles=kwargs.pop("max_vehicles", 4),
        time_limit_sec=kwargs.pop("time_limit_sec", 5),
        **kwargs,
    )


def test_inverse_permutation_round_trips():
    permutation = node_permutation(20, seed=3)
    inverse = inverse_permutation(permutation)

    assert [permutation[inverse[node]] for node in range(20)] == list(range(20))


def test_allowed_vehicles_keep_disjoint_groups_on_disjoint_routes():
    # Nodes 0-3 may only ride vehicle 0, nodes 4-7 only vehicle 1, so no route can
    # ever mix the two groups however cheap the arcs between them are.
    allowed = [[0]] * 4 + [[1]] * 4
    routes, dropped = unwrap(build_solver(8, allowed_vehicles=allowed).solve())

    assert dropped == []
    assert sorted(node for route in routes for node in route) == list(range(8))
    for route in routes:
        assert len({node < 4 for node in route}) == 1


def test_allowed_vehicles_survive_the_node_permutation():
    allowed = [[0]] * 4 + [[1]] * 4
    routes, dropped = unwrap(
        build_solver(8, allowed_vehicles=allowed, node_seed=7).solve()
    )

    assert dropped == []
    for route in routes:
        assert len({node < 4 for node in route}) == 1


def test_warm_start_solution_still_visits_every_node():
    warm = [[0, 1, 2, 3], [4, 5, 6, 7]]
    routes, dropped = unwrap(build_solver(8, warm_start_routes=warm).solve())

    assert dropped == []
    assert sorted(node for route in routes for node in route) == list(range(8))


def test_warm_start_survives_the_node_permutation():
    warm = [[0, 1, 2, 3], [4, 5, 6, 7]]
    routes, dropped = unwrap(
        build_solver(8, warm_start_routes=warm, node_seed=5).solve()
    )

    assert dropped == []
    assert sorted(node for route in routes for node in route) == list(range(8))


def test_warm_start_with_more_routes_than_vehicles_is_rejected():
    warm = [[node] for node in range(8)]
    solver = build_solver(8, warm_start_routes=warm, max_vehicles=2)

    with pytest.raises(ValueError, match="only 2 vehicles"):
        solver.solve()


def test_infeasible_warm_start_is_rejected_instead_of_silently_ignored():
    # A single route of 8 stops needs 8x300s of service alone, over the T_max below.
    solver = ArbocensusVRPSolver(
        uniform_matrix(8),
        min_route_time_sec=600,
        max_route_time_sec=1_000,
        service_time_sec=300,
        max_vehicles=4,
        time_limit_sec=5,
        warm_start_routes=[list(range(8))],
    )

    with pytest.raises(ValueError, match="not a feasible assignment"):
        solver.solve()
