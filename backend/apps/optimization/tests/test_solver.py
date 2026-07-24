import numpy as np
import pytest
from apps.optimization.cost_matrix import UNREACHABLE_PENALTY
from apps.optimization.solver import (
    SOFT_LOWER_PENALTY,
    SOFT_UPPER_PENALTY,
    ArbocensusVRPSolver,
    PenaltyConfig,
    build_open_matrix,
    node_permutation,
)


def unwrap(result):
    assert result is not None
    return result


def uniform_matrix(n, travel=60.0):
    m = np.full((n, n), travel)
    np.fill_diagonal(m, 0.0)
    return m


def route_time(open_matrix, route, service_time_sec):
    nodes = [0] + [node + 1 for node in route] + [0]
    total = 0.0
    for from_node, to_node in zip(nodes[:-1], nodes[1:], strict=True):
        service = service_time_sec if from_node != 0 else 0
        total += open_matrix[from_node][to_node] + service
    return total


def test_all_points_visited():
    solver = ArbocensusVRPSolver(
        uniform_matrix(6),
        min_route_time_sec=600,
        max_route_time_sec=100_000,
        service_time_sec=300,
        max_vehicles=5,
        time_limit_sec=5,
    )
    routes, dropped = unwrap(solver.solve())
    assert dropped == []

    visited = sorted(node for route in routes for node in route)
    assert visited == list(range(6))


def test_dummy_depot_not_in_routes():
    solver = ArbocensusVRPSolver(
        uniform_matrix(6),
        min_route_time_sec=600,
        max_route_time_sec=100_000,
        service_time_sec=300,
        max_vehicles=5,
        time_limit_sec=5,
    )
    routes, _ = unwrap(solver.solve())

    for route in routes:
        for node in route:
            assert 0 <= node < 6


def test_each_node_visited_exactly_once():
    solver = ArbocensusVRPSolver(
        uniform_matrix(8),
        min_route_time_sec=600,
        max_route_time_sec=100_000,
        service_time_sec=300,
        max_vehicles=5,
        time_limit_sec=5,
    )
    routes, dropped = unwrap(solver.solve())
    assert dropped == []

    visited = [node for route in routes for node in route]
    assert sorted(visited) == list(range(8))
    assert len(visited) == len(set(visited))


def test_respects_max_route_time():
    matrix = uniform_matrix(8, travel=120.0)
    max_route_time = 2_000
    solver = ArbocensusVRPSolver(
        matrix,
        min_route_time_sec=500,
        max_route_time_sec=max_route_time,
        service_time_sec=300,
        max_vehicles=8,
        time_limit_sec=10,
    )
    routes, _ = unwrap(solver.solve())

    open_matrix = build_open_matrix(matrix)
    for route in routes:
        assert route_time(open_matrix, route, 300) <= max_route_time


def test_fractional_arc_times_never_exceed_max_route_time():
    matrix = uniform_matrix(5, travel=60.5)
    service_time = 300
    # Budget a truncating callback would compute for a single 5-node route
    # (4 x int(360.5) + 300); its real time is 1742s, i.e. over the budget.
    max_route_time = 1_740

    solver = ArbocensusVRPSolver(
        matrix,
        min_route_time_sec=600,
        max_route_time_sec=max_route_time,
        service_time_sec=service_time,
        max_vehicles=1,
        time_limit_sec=5,
    )
    routes, dropped = unwrap(solver.solve())

    assert len(routes) == 1
    assert len(dropped) == 1

    open_matrix = build_open_matrix(matrix)
    for route in routes:
        assert route_time(open_matrix, route, service_time) <= max_route_time


def test_drops_single_unreachable_node():
    matrix = uniform_matrix(6)
    unreachable = 3
    matrix[:, unreachable] = UNREACHABLE_PENALTY
    matrix[unreachable, :] = UNREACHABLE_PENALTY
    matrix[unreachable, unreachable] = 0.0

    solver = ArbocensusVRPSolver(
        matrix,
        min_route_time_sec=600,
        max_route_time_sec=100_000,
        service_time_sec=300,
        max_vehicles=5,
        time_limit_sec=5,
    )
    routes, dropped = unwrap(solver.solve())

    assert dropped == [unreachable]
    visited = sorted(node for route in routes for node in route)
    assert visited == [n for n in range(6) if n != unreachable]


def test_drops_all_when_time_budget_too_tight():
    solver = ArbocensusVRPSolver(
        uniform_matrix(5),
        min_route_time_sec=1,
        max_route_time_sec=1,
        service_time_sec=300,
        max_vehicles=5,
        time_limit_sec=5,
    )
    routes, dropped = unwrap(solver.solve())

    assert routes == []
    assert sorted(dropped) == list(range(5))


def two_cluster_matrix(per_cluster=3, within=10.0, across=3_000.0):
    n = 2 * per_cluster
    m = np.full((n, n), across)
    for block in (range(per_cluster), range(per_cluster, n)):
        for i in block:
            for j in block:
                m[i][j] = within
    np.fill_diagonal(m, 0.0)
    return m


def total_travel(open_matrix, routes):
    return sum(
        open_matrix[a + 1][b + 1]
        for route in routes
        for a, b in zip(route[:-1], route[1:], strict=True)
    )


def test_penalty_defaults_reproduce_module_constants():
    penalties = PenaltyConfig()

    assert penalties.soft_lower_penalty == SOFT_LOWER_PENALTY
    assert penalties.soft_upper_penalty == SOFT_UPPER_PENALTY
    assert penalties.soft_upper_bound(7_200, 10_800) == 9_000


def test_soft_upper_target_tmax_moves_the_bound_to_max_route_time():
    penalties = PenaltyConfig(soft_upper_target="tmax")

    assert penalties.soft_upper_bound(7_200, 10_800) == 10_800


def test_unknown_soft_upper_target_is_rejected():
    with pytest.raises(ValueError, match="soft_upper_target"):
        PenaltyConfig(soft_upper_target="midpoint_ish")


def test_solver_defaults_to_the_module_penalties():
    solver = ArbocensusVRPSolver(
        uniform_matrix(4),
        min_route_time_sec=600,
        max_route_time_sec=100_000,
        service_time_sec=300,
        max_vehicles=2,
        time_limit_sec=5,
    )

    assert solver.penalties == PenaltyConfig()


def solve_two_clusters(penalties):
    # One vehicle for the six nodes: the only lever left is the visit ORDER, so any
    # extra travel is padding to reach T_min, not a different fleet size.
    matrix = two_cluster_matrix()
    solver = ArbocensusVRPSolver(
        matrix,
        min_route_time_sec=15_000,
        max_route_time_sec=25_000,
        service_time_sec=1_000,
        max_vehicles=1,
        time_limit_sec=10,
        penalties=penalties,
    )
    routes, dropped = unwrap(solver.solve())
    assert dropped == []
    return routes, total_travel(build_open_matrix(matrix), routes)


def test_zero_soft_lower_penalty_stops_padding_routes_with_travel():
    _, padded_travel = solve_two_clusters(PenaltyConfig())
    routes, lean_travel = solve_two_clusters(PenaltyConfig(soft_lower_penalty=0))

    assert lean_travel < padded_travel
    assert sorted(routes[0]) == list(range(6))


def solve_four_close_nodes(penalties):
    solver = ArbocensusVRPSolver(
        uniform_matrix(4, travel=100.0),
        min_route_time_sec=0,
        max_route_time_sec=10_000,
        service_time_sec=2_000,
        max_vehicles=4,
        time_limit_sec=10,
        penalties=penalties,
    )
    routes, _ = unwrap(solver.solve())
    return routes


def test_soft_upper_at_the_midpoint_splits_what_tmax_keeps_in_one_route():
    split = solve_four_close_nodes(PenaltyConfig())
    kept = solve_four_close_nodes(PenaltyConfig(soft_upper_target="tmax"))

    assert len(split) > 1
    assert len(kept) == 1


def solve_seeded(node_seed, matrix):
    solver = ArbocensusVRPSolver(
        matrix,
        min_route_time_sec=600,
        max_route_time_sec=6_000,
        service_time_sec=60,
        max_vehicles=6,
        time_limit_sec=3,
        node_seed=node_seed,
    )
    routes, dropped = unwrap(solver.solve())
    assert dropped == []
    return routes


def scattered_matrix(n, seed=11, scale=400.0):
    rng = np.random.default_rng(seed)
    points = rng.random((n, 2)) * scale
    diffs = points[:, None, :] - points[None, :, :]
    return np.sqrt((diffs**2).sum(axis=2))


def test_node_seed_covers_every_node_under_the_permutation():
    matrix = scattered_matrix(24)
    routes = solve_seeded(3, matrix)
    assert sorted(node for route in routes for node in route) == list(range(24))


def test_node_seeds_are_real_replicates():
    # Without this the sweep's "seeds" are three copies of one run: OR-Tools exposes
    # no RNG seed, so the permutation is the only source of replicate variance.
    matrix = scattered_matrix(24)
    baseline = solve_seeded(1, matrix)
    assert any(solve_seeded(seed, matrix) != baseline for seed in (2, 3, 4, 5))


def test_seed_zero_is_the_identity_permutation():
    # Production never passes a seed, so seed 0 must leave the node order untouched.
    assert node_permutation(24, 0) == list(range(24))


def test_seed_zero_is_deterministic():
    matrix = scattered_matrix(24)
    assert solve_seeded(0, matrix) == solve_seeded(0, matrix)


def test_arc_coef_one_reproduces_the_default_solution():
    def solve(**extra):
        return unwrap(
            ArbocensusVRPSolver(
                uniform_matrix(8),
                min_route_time_sec=600,
                max_route_time_sec=100_000,
                service_time_sec=300,
                max_vehicles=4,
                time_limit_sec=5,
                node_seed=2,
                **extra,
            ).solve()
        )

    assert solve(arc_coef=1) == solve()


def test_arc_coef_does_not_reach_the_time_dimension():
    # T_max is sized to fit every node in one route at the unweighted travel. A
    # coefficient leaking into time_callback would inflate the Time cumul past
    # T_max and force the solver to abandon nodes.
    travel, service, n = 60.0, 300, 8
    t_max = int(n * (travel + service))
    routes, dropped = unwrap(
        ArbocensusVRPSolver(
            uniform_matrix(n, travel),
            min_route_time_sec=600,
            max_route_time_sec=t_max,
            service_time_sec=service,
            max_vehicles=1,
            time_limit_sec=5,
            arc_coef=10,
        ).solve()
    )
    assert dropped == []
    assert sorted(node for route in routes for node in route) == list(range(n))


def test_arc_coef_and_convex_arc_lambda_cannot_be_combined():
    with pytest.raises(ValueError):
        ArbocensusVRPSolver(
            uniform_matrix(8),
            min_route_time_sec=600,
            max_route_time_sec=100_000,
            service_time_sec=300,
            max_vehicles=4,
            time_limit_sec=5,
            convex_arc_lambda=1.0,
            arc_coef=10,
        )
