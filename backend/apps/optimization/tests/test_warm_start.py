import numpy as np
import pytest
from apps.optimization.solver import DEFAULT_PENALTIES
from apps.optimization.warm_start import (
    WARM_START_CLUSTER_FIRST,
    WARM_START_GREEDY,
    build_warm_start_routes,
    solver_route_duration_sec,
    split_to_solver_capacity,
)

SANTIAGO_LAT = -33.45
SANTIAGO_LON = -70.65


def uniform_matrix(n, travel=60.0):
    m = np.full((n, n), travel)
    np.fill_diagonal(m, 0.0)
    return m


def line_points(n, step=0.001):
    return [(SANTIAGO_LAT + i * step, SANTIAGO_LON + i * step) for i in range(n)]


def build(source, n=8):
    return build_warm_start_routes(
        source,
        uniform_matrix(n),
        points=line_points(n),
        min_route_time_sec=600,
        max_route_time_sec=100_000,
        service_time_sec=300,
        time_limit_sec=2,
        penalties=DEFAULT_PENALTIES,
    )


def test_greedy_seed_covers_every_node_exactly_once():
    routes = build(WARM_START_GREEDY)

    assert sorted(node for route in routes for node in route) == list(range(8))


def test_cluster_first_seed_covers_every_node_exactly_once():
    routes = build(WARM_START_CLUSTER_FIRST)

    assert sorted(node for route in routes for node in route) == list(range(8))


def test_greedy_seed_routes_fit_the_time_dimension_accounting():
    # Arcs of 60.5s round up to 61s each inside the Time dimension, so a route the
    # builder measured with one rounding must still fit when every arc rounds alone.
    n = 40
    matrix = np.full((n, n), 60.5)
    np.fill_diagonal(matrix, 0.0)
    routes = build_warm_start_routes(
        WARM_START_GREEDY,
        matrix,
        points=line_points(n),
        min_route_time_sec=600,
        max_route_time_sec=3_000,
        service_time_sec=120,
        time_limit_sec=2,
        penalties=DEFAULT_PENALTIES,
    )

    assert sorted(node for route in routes for node in route) == list(range(n))
    for route in routes:
        assert solver_route_duration_sec(route, matrix, 120) <= 3_000


def test_split_keeps_node_order_and_covers_every_node():
    matrix = np.full((6, 6), 100.0)
    np.fill_diagonal(matrix, 0.0)

    split = split_to_solver_capacity(
        [[0, 1, 2, 3, 4, 5]], matrix, service_time_sec=100, max_route_time_sec=500
    )

    assert [node for route in split for node in route] == [0, 1, 2, 3, 4, 5]
    for route in split:
        assert solver_route_duration_sec(route, matrix, 100) <= 500


def test_unknown_source_is_rejected():
    with pytest.raises(ValueError, match="warm start source"):
        build("path-cheapest-arc")
