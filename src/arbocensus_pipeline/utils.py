import math
from typing import List

EARTH_RADIUS_M = 6371000.0


def haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = (
        math.sin(dphi / 2.0) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2.0) ** 2
    )
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return EARTH_RADIUS_M * c


def nn_route(
    start: int,
    nodes: List[int],
    distances: List[List[float]]
) -> List[int]:
    """
    Nearest neighbor algorithm for open path (census route).
    Starts at 'start' and visits all nodes exactly once, but does not return to start.
    """
    if not nodes:
        return []
    unvisited = set(nodes)
    route = [start]
    unvisited.remove(start)
    curr = start
    while unvisited:
        nxt = min(unvisited, key=lambda x, curr=curr: distances[curr][x])
        route.append(nxt)
        unvisited.remove(nxt)
        curr = nxt
    return route

def route_length(
    route: List[int],
    distances: List[List[float]]
) -> float:
    """
    Calculate the total length of an open path (does not return to start).
    Unlike route_length, this does NOT add the distance from last node to first.
    """
    if not route or len(route) == 1:
        return 0.0
    s = 0.0
    for i in range(len(route) - 1):
        s += distances[route[i]][route[i + 1]]
    return s

def two_opt(
    route: List[int], distances: List[List[float]], max_iter: int = 100
) -> List[int]:
    """
    Local search improvement (2-opt) for open path.
    Swaps edges to reduce path length without closing the loop.
    """
    if len(route) <= 2:
        return route

    best = route[:]
    best_len = route_length(best, distances)
    improved = True
    it = 0

    while improved and it < max_iter:
        improved = False
        it += 1
        n = len(best)
        for i in range(1, n - 2):
            for j in range(i + 1, n - 1):
                if j - i == 1:
                    continue
                new = best[:i] + best[i : j + 1][::-1] + best[j + 1 :]
                nl = route_length(new, distances)
                if nl + 1e-9 < best_len:
                    best = new
                    best_len = nl
                    improved = True
                    break
            if improved:
                break

    return best


def estimate_euclidean_tsp(nodes: List[dict]) -> float:
    """
    Estimate the total distance of a TSP route using Euclidean distance.
    Nodes should be dicts with 'lat' and 'lng' fields.
    Returns distance in kilometers.
    
    Uses a simple heuristic: 1D version of nearest neighbor on 2D points.
    """
    if not nodes:
        return 0.0
    if len(nodes) == 1:
        return 0.0

    # Extract coordinates in degrees
    coords = [(n["lat"], n["lng"]) for n in nodes]

    # Start from first node, greedily visit nearest unvisited
    unvisited = set(range(len(coords)))
    curr_idx = 0
    unvisited.remove(curr_idx)
    total_dist_deg = 0.0

    while unvisited:
        curr_lat, curr_lng = coords[curr_idx]
        nxt_idx = min(
            unvisited,
            key=lambda idx, curr_lat=curr_lat, curr_lng=curr_lng: (coords[idx][0] - curr_lat) ** 2
            + (coords[idx][1] - curr_lng) ** 2,
        )
        nxt_lat, nxt_lng = coords[nxt_idx]
        # Euclidean distance in degrees
        dist_deg = math.sqrt(
            (nxt_lat - curr_lat) ** 2 + (nxt_lng - curr_lng) ** 2
        )
        total_dist_deg += dist_deg
        curr_idx = nxt_idx
        unvisited.remove(curr_idx)

    # Convert degrees to km (rough approximation: 1 degree ≈ 111 km)
    total_dist_km = total_dist_deg * 111.0
    return total_dist_km
