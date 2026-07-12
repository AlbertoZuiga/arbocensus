import math

import numpy as np
from apps.optimization.cost_matrix import UNREACHABLE_PENALTY

VEHICLE_BUFFER = 5


def mean_nearest_neighbor_travel(matrix):
    real_nodes = np.asarray(matrix, dtype=float)[1:, 1:]
    masked = np.where(
        (real_nodes >= UNREACHABLE_PENALTY) | np.eye(real_nodes.shape[0], dtype=bool),
        np.inf,
        real_nodes,
    )
    row_minima = masked.min(axis=1)
    reachable_minima = row_minima[np.isfinite(row_minima)]
    if reachable_minima.size == 0:
        return 0.0
    return float(reachable_minima.mean())


def estimate_max_vehicles(
    matrix, total_service_time_sec, min_route_time_sec, buffer=VEHICLE_BUFFER
):
    real_node_count = len(matrix) - 1
    total_travel = real_node_count * mean_nearest_neighbor_travel(matrix)
    total_work = total_service_time_sec + total_travel
    n_est = math.ceil(total_work / min_route_time_sec) + buffer
    return max(1, min(n_est, real_node_count))
