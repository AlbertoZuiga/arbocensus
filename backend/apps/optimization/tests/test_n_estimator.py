import math

import numpy as np
from apps.optimization.cost_matrix import UNREACHABLE_PENALTY
from apps.optimization.n_estimator import average_pair_travel, estimate_max_vehicles


def uniform_matrix(real_node_count, travel=30.0):
    size = real_node_count + 1
    matrix = np.full((size, size), travel, dtype=float)
    np.fill_diagonal(matrix, 0.0)
    matrix[0, :] = 0.0
    matrix[:, 0] = 0.0
    return matrix


def test_minimum_is_at_least_one():
    matrix = uniform_matrix(3)
    assert (
        estimate_max_vehicles(matrix, total_service_time_sec=0, min_route_time_sec=3600)
        >= 1
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
    matrix = uniform_matrix(5)
    total_service = 5000
    min_route = 1800

    expected = math.ceil(total_service / min_route) + 5
    assert estimate_max_vehicles(matrix, total_service, min_route) == expected
    assert expected == 8


def test_average_pair_travel_uses_upper_triangle_real_nodes():
    matrix = uniform_matrix(4, travel=42.0)
    assert average_pair_travel(matrix) == 42.0


def test_average_pair_travel_excludes_unreachable_penalty():
    matrix = uniform_matrix(3, travel=20.0)
    matrix[1, 2] = UNREACHABLE_PENALTY
    matrix[2, 1] = UNREACHABLE_PENALTY

    assert average_pair_travel(matrix) == 20.0
