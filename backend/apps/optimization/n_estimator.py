import math

import numpy as np
from apps.optimization.cost_matrix import UNREACHABLE_PENALTY

VEHICLE_BUFFER = 5


def average_pair_travel(matrix):
    real_nodes = np.asarray(matrix, dtype=float)[1:, 1:]
    upper = real_nodes[np.triu_indices_from(real_nodes, k=1)]
    reachable = upper[upper < UNREACHABLE_PENALTY]
    if reachable.size == 0:
        return 0.0
    return float(reachable.mean())


def estimate_max_vehicles(matrix, total_service_time_sec, min_route_time_sec):
    real_node_count = len(matrix) - 1
    total_travel = real_node_count * average_pair_travel(matrix)
    total_work = total_service_time_sec + total_travel
    n_est = math.ceil(total_work / min_route_time_sec) + VEHICLE_BUFFER
    return max(1, n_est)
