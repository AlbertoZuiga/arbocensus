import numpy as np
from apps.optimization.cost_matrix import UNREACHABLE_PENALTY
from apps.optimization.solver import ArbocensusVRPSolver, build_open_matrix


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
