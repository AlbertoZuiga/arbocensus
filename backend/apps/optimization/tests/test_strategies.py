import numpy as np
from apps.optimization.solver import build_open_matrix
from apps.optimization.strategies import solve_spatial_term

SANTIAGO_LAT = -33.45
SANTIAGO_LON = -70.65


def uniform_matrix(n, travel=60.0):
    m = np.full((n, n), travel)
    np.fill_diagonal(m, 0.0)
    return m


def line_points(n, step=0.001):
    return [(SANTIAGO_LAT + i * step, SANTIAGO_LON + i * step) for i in range(n)]


def route_time(open_matrix, route, service_time_sec):
    nodes = [0, *[node + 1 for node in route], 0]
    total = 0.0
    for from_node, to_node in zip(nodes[:-1], nodes[1:], strict=True):
        service = service_time_sec if from_node != 0 else 0
        total += open_matrix[from_node][to_node] + service
    return total


def test_spatial_term_visits_every_node_once():
    n = 8
    routes = solve_spatial_term(
        uniform_matrix(n),
        points=line_points(n),
        min_route_time_sec=600,
        max_route_time_sec=100_000,
        service_time_sec=300,
        max_vehicles=5,
        time_limit_sec=5,
    )
    assert routes is not None
    visited = [node for route in routes for node in route]
    assert sorted(visited) == list(range(n))
    assert len(visited) == len(set(visited))


def test_spatial_term_excludes_dummy_depot():
    n = 6
    routes = solve_spatial_term(
        uniform_matrix(n),
        points=line_points(n),
        min_route_time_sec=600,
        max_route_time_sec=100_000,
        service_time_sec=300,
        max_vehicles=5,
        time_limit_sec=5,
    )
    assert routes is not None
    for route in routes:
        for node in route:
            assert 0 <= node < n


def test_spatial_term_respects_max_route_time():
    n = 8
    matrix = uniform_matrix(n, travel=120.0)
    max_route_time = 2_000
    routes = solve_spatial_term(
        matrix,
        points=line_points(n),
        min_route_time_sec=500,
        max_route_time_sec=max_route_time,
        service_time_sec=300,
        max_vehicles=8,
        time_limit_sec=10,
    )
    assert routes is not None
    open_matrix = build_open_matrix(matrix)
    for route in routes:
        assert route_time(open_matrix, route, 300) <= max_route_time
