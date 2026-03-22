"""TSP algorithms: NN + 2-opt wrapper"""

from typing import Any, Dict, List

from .utils import (
    nn_route,
    route_length,
    two_opt,
)


def compute_route_for_cluster(
    members: List[int],
    distances: List[List[float]],
    time_per_tree: float,
    walking_speed_kmh: float,
    haversine_multiplier: float = 1.0,
) -> Dict[str, Any]:
    """
    Compute route for a cluster using open-path TSP (Phase 1).

    The route is an open path: censante starts at one end and finishes at another,
    without returning to the start point.
    """
    if not members:
        return {
            "route": [],
            "route_meters": 0.0,
            "service_minutes": 0.0,
            "route_minutes": 0.0,
            "total_minutes": 0.0,
        }
    start = members[0]
    route = nn_route(start, members, distances)
    if len(route) > 2:
        route = two_opt(route, distances, max_iter=50)
    meters = route_length(route, distances)
    route_minutes = (
        meters
        * (60.0 / 1000.0)
        / float(walking_speed_kmh)
        * float(haversine_multiplier)
    )
    service_minutes = len(members) * float(time_per_tree)
    total = route_minutes + service_minutes
    return {
        "route": route,
        "route_meters": meters,
        "service_minutes": service_minutes,
        "route_minutes": route_minutes,
        "total_minutes": total,
    }
