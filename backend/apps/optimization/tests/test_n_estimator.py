import math

import numpy as np
from apps.optimization.cost_matrix import UNREACHABLE_PENALTY
from apps.optimization.n_estimator import (
    VEHICLE_BUFFER,
    estimate_max_vehicles,
    mean_nearest_neighbor_travel,
)


def uniform_matrix(real_node_count, travel=30.0):
    size = real_node_count + 1
    matrix = np.full((size, size), travel, dtype=float)
    np.fill_diagonal(matrix, 0.0)
    matrix[0, :] = 0.0
    matrix[:, 0] = 0.0
    return matrix


def mean_pair_travel(matrix):
    real_nodes = np.asarray(matrix, dtype=float)[1:, 1:]
    upper = real_nodes[np.triu_indices_from(real_nodes, k=1)]
    reachable = upper[upper < UNREACHABLE_PENALTY]
    return float(reachable.mean())


def test_zero_work_falls_back_to_buffer():
    matrix = uniform_matrix(VEHICLE_BUFFER + 1, travel=0.0)
    assert (
        estimate_max_vehicles(matrix, total_service_time_sec=0, min_route_time_sec=3600)
        == VEHICLE_BUFFER
    )


def test_travel_time_raises_estimate():
    no_travel = uniform_matrix(10, travel=0.0)
    with_travel = uniform_matrix(10, travel=600.0)
    assert estimate_max_vehicles(
        with_travel, total_service_time_sec=3600, min_route_time_sec=1800
    ) > estimate_max_vehicles(
        no_travel, total_service_time_sec=3600, min_route_time_sec=1800
    )


def test_more_service_time_means_more_or_equal_vehicles():
    matrix = uniform_matrix(10)
    min_route = 1800
    previous = 0
    for total_service in (1800, 3600, 7200, 18000, 36000):
        current = estimate_max_vehicles(matrix, total_service, min_route)
        assert current >= previous
        previous = current


def test_ceil_plus_buffer_arithmetic():
    real_nodes = 10
    travel = 30.0
    matrix = uniform_matrix(real_nodes, travel=travel)
    total_service = 5000
    min_route = 1800

    total_work = total_service + real_nodes * travel
    expected = math.ceil(total_work / min_route) + VEHICLE_BUFFER
    assert estimate_max_vehicles(matrix, total_service, min_route) == expected
    assert expected == 8


def test_estimate_capped_at_real_node_count():
    real_nodes = 12
    matrix = uniform_matrix(real_nodes, travel=30.0)
    estimate = estimate_max_vehicles(
        matrix, total_service_time_sec=100_000, min_route_time_sec=1800
    )
    assert 1 <= estimate <= real_nodes
    assert estimate == real_nodes


def test_buffer_param_overrides_default_solver_headroom():
    real_nodes = 10
    travel = 30.0
    matrix = uniform_matrix(real_nodes, travel=travel)
    total_service = 5000
    min_route = 1800

    total_work = total_service + real_nodes * travel
    assert estimate_max_vehicles(
        matrix, total_service, min_route, buffer=0
    ) == math.ceil(total_work / min_route)


def test_mean_nearest_neighbor_travel_excludes_diagonal():
    matrix = np.array(
        [
            [0.0, 0.0, 0.0, 0.0],
            [0.0, 0.0, 10.0, 20.0],
            [0.0, 15.0, 0.0, 30.0],
            [0.0, 40.0, 25.0, 0.0],
        ]
    )
    # row minima over real nodes (excluding self=0): 10.0, 15.0, 25.0
    assert mean_nearest_neighbor_travel(matrix) == (10.0 + 15.0 + 25.0) / 3


def test_mean_nearest_neighbor_travel_excludes_unreachable_penalty():
    matrix = uniform_matrix(3, travel=20.0)
    matrix[1, 2] = UNREACHABLE_PENALTY
    matrix[2, 1] = UNREACHABLE_PENALTY

    assert mean_nearest_neighbor_travel(matrix) == 20.0


def test_nearest_neighbor_estimate_lower_than_average_pair_estimate_on_sparse_matrix():
    real_node_count = 20
    matrix = uniform_matrix(real_node_count, travel=20.0)
    real_nodes = matrix[1:, 1:]
    # a few far outliers inflate the pairwise average without affecting
    # each node's nearest neighbor, since a close neighbor (20.0) remains
    for i, j in ((0, 1), (2, 3), (4, 5)):
        real_nodes[i, j] = real_nodes[j, i] = 5000.0
    matrix[1:, 1:] = real_nodes

    total_service = 3600
    min_route = 1000
    nn_travel = real_node_count * mean_nearest_neighbor_travel(matrix)
    avg_travel = real_node_count * mean_pair_travel(matrix)
    assert nn_travel < avg_travel

    nn_estimate = min(
        math.ceil((total_service + nn_travel) / min_route) + VEHICLE_BUFFER,
        real_node_count,
    )
    avg_estimate = min(
        math.ceil((total_service + avg_travel) / min_route) + VEHICLE_BUFFER,
        real_node_count,
    )
    assert estimate_max_vehicles(matrix, total_service, min_route) == nn_estimate
    assert nn_estimate < avg_estimate
