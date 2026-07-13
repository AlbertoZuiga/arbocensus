import math

import numpy as np


def solve_greedy(matrix, *, max_route_time_sec, service_time_sec):
    matrix = np.asarray(matrix, dtype=float)
    n = matrix.shape[0]
    unvisited = np.ones(n, dtype=bool)

    routes = []
    while unvisited.any():
        current = int(np.argmax(unvisited))
        unvisited[current] = False
        route = [current]
        travel = 0.0

        while unvisited.any():
            nearest = int(np.argmin(np.where(unvisited, matrix[current], np.inf)))
            arc = float(matrix[current][nearest])
            # Same accounting as Route.total_estimated_time_sec, so that the routes
            # this baseline produces are directly comparable with the solver's.
            candidate = math.ceil(travel + arc) + (len(route) + 1) * service_time_sec
            if candidate > max_route_time_sec:
                break
            travel += arc
            route.append(nearest)
            unvisited[nearest] = False
            current = nearest

        routes.append(route)

    return routes
