from apps.optimization.greedy import solve_greedy
from apps.optimization.strategies import solve_cluster_first

WARM_START_GREEDY = "greedy"
WARM_START_CLUSTER_FIRST = "cluster_first"
WARM_START_SOURCES = (WARM_START_GREEDY, WARM_START_CLUSTER_FIRST)


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
        return solve_greedy(
            matrix,
            max_route_time_sec=max_route_time_sec,
            service_time_sec=service_time_sec,
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
