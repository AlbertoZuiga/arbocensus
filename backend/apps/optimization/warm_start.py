import math

from apps.optimization.greedy import solve_greedy
from apps.optimization.strategies import solve_cluster_first

WARM_START_GREEDY = "greedy"
WARM_START_CLUSTER_FIRST = "cluster_first"
WARM_START_SOURCES = (WARM_START_GREEDY, WARM_START_CLUSTER_FIRST)


def solver_route_duration_sec(route, matrix, service_time_sec):
    # The Time dimension rounds up each arc separately, so a sum of rounded arcs can
    # exceed the rounded sum a route builder checked against T_max. Seeds have to be
    # measured the way the model measures them or they read back as infeasible.
    transits = sum(
        math.ceil(matrix[a][b] + service_time_sec)
        for a, b in zip(route[:-1], route[1:], strict=True)
    )
    return transits + service_time_sec


def split_to_solver_capacity(routes, matrix, *, service_time_sec, max_route_time_sec):
    split = []
    for route in routes:
        current = []
        for node in route:
            candidate = [*current, node]
            duration = solver_route_duration_sec(candidate, matrix, service_time_sec)
            if current and duration > max_route_time_sec:
                split.append(current)
                current = [node]
            else:
                current = candidate
        if current:
            split.append(current)
    return split


def build_warm_start_routes(
    source,
    matrix,
    *,
    points,
    min_route_time_sec,
    max_route_time_sec,
    service_time_sec,
    time_limit_sec,
    penalties,
    node_seed=0,
):
    if source == WARM_START_GREEDY:
        return split_to_solver_capacity(
            solve_greedy(
                matrix,
                max_route_time_sec=max_route_time_sec,
                service_time_sec=service_time_sec,
            ),
            matrix,
            service_time_sec=service_time_sec,
            max_route_time_sec=max_route_time_sec,
        )
    if source == WARM_START_CLUSTER_FIRST:
        result = solve_cluster_first(
            matrix,
            points=points,
            min_route_time_sec=min_route_time_sec,
            max_route_time_sec=max_route_time_sec,
            service_time_sec=service_time_sec,
            time_limit_sec=time_limit_sec,
            penalties=penalties,
            node_seed=node_seed,
        )
        if result is None:
            raise ValueError("cluster_first produced no warm start solution")
        routes, _ = result
        return routes
    raise ValueError(f"warm start source must be one of {WARM_START_SOURCES}")
