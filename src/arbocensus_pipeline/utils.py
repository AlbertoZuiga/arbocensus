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


def nn_tour(start: int, nodes: List[int], distances: List[List[float]]) -> List[int]:
    if not nodes:
        return []
    unvisited = set(nodes)
    tour = [start]
    unvisited.remove(start)
    curr = start
    while unvisited:
        nxt = min(unvisited, key=lambda x: distances[curr][x])
        tour.append(nxt)
        unvisited.remove(nxt)
        curr = nxt
    return tour


def tour_length(tour: List[int], distances: List[List[float]]) -> float:
    if not tour:
        return 0.0
    s = 0.0
    for i in range(len(tour) - 1):
        s += distances[tour[i]][tour[i + 1]]
    s += distances[tour[-1]][tour[0]]
    return s


def two_opt(
    route: List[int], distances: List[List[float]], max_iter: int = 100
) -> List[int]:
    best = route[:]
    best_len = tour_length(best, distances)
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
                nl = tour_length(new, distances)
                if nl + 1e-9 < best_len:
                    best = new
                    best_len = nl
                    improved = True
                    break
            if improved:
                break
    return best
