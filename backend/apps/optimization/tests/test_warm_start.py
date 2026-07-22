import numpy as np
import pytest
from apps.optimization.solver import DEFAULT_PENALTIES
from apps.optimization.warm_start import (
    WARM_START_CLUSTER_FIRST,
    WARM_START_GREEDY,
    build_warm_start_routes,
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


def test_unknown_source_is_rejected():
    with pytest.raises(ValueError, match="warm start source"):
        build("path-cheapest-arc")
