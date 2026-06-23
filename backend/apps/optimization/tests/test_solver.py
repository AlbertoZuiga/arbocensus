import numpy as np
from apps.optimization.solver import ArbocensusVRPSolver, build_open_matrix


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
    routes = solver.solve()
    assert routes is not None

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
    routes = solver.solve()
    assert routes is not None

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
    routes = solver.solve()
    assert routes is not None

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
    routes = solver.solve()
    assert routes is not None

    open_matrix = build_open_matrix(matrix)
    for route in routes:
        assert route_time(open_matrix, route, 300) <= max_route_time


def test_returns_none_on_infeasible():
    solver = ArbocensusVRPSolver(
        uniform_matrix(5),
        min_route_time_sec=1,
        max_route_time_sec=1,
        service_time_sec=300,
        max_vehicles=5,
        time_limit_sec=5,
    )
    assert solver.solve() is None
