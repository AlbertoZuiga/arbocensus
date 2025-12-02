"""TSP algorithms: NN + 2-opt wrapper"""
from typing import Any, Dict, List

from .utils import nn_tour, tour_length, two_opt


def compute_route_for_cluster(members: List[int], distances: List[List[float]], time_per_tree: float, walking_speed_kmh: float, haversine_multiplier: float = 1.0) -> Dict[str, Any]:
    if not members:
        return {'route': [], 'route_meters': 0.0, 'service_minutes': 0.0, 'route_minutes': 0.0, 'total_minutes': 0.0}
    start = members[0]
    tour = nn_tour(start, members, distances)
    if len(tour) > 2:
        tour = two_opt(tour, distances, max_iter=50)
    meters = tour_length(tour, distances)
    route_minutes = meters * (60.0 / 1000.0) / float(walking_speed_kmh) * float(haversine_multiplier)
    service_minutes = len(members) * float(time_per_tree)
    total = route_minutes + service_minutes
    return {'route': tour, 'route_meters': meters, 'service_minutes': service_minutes, 'route_minutes': route_minutes, 'total_minutes': total}
