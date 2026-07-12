import numpy as np
from apps.optimization.models import RoutingSolution
from apps.optimization.n_estimator import (
    estimate_max_vehicles,
    mean_nearest_neighbor_travel,
)
from apps.optimization.route_metrics import EARTH_RADIUS_M
from apps.optimization.solver import ArbocensusVRPSolver, build_open_matrix

# Meters of route geographic span cost one unit of objective per coefficient.
# Higher → tighter, less overlapping routes at the price of more total travel time.
SPATIAL_SPAN_COEF = 3


def solve_by_strategy(
    strategy,
    matrix,
    *,
    points,
    min_route_time_sec,
    max_route_time_sec,
    service_time_sec,
    max_vehicles,
    time_limit_sec,
    timer=None,
):
    if strategy == RoutingSolution.Strategy.SPATIAL_TERM.value:
        return solve_spatial_term(
            matrix,
            points=points,
            min_route_time_sec=min_route_time_sec,
            max_route_time_sec=max_route_time_sec,
            service_time_sec=service_time_sec,
            max_vehicles=max_vehicles,
            time_limit_sec=time_limit_sec,
            timer=timer,
        )
    if strategy == RoutingSolution.Strategy.CLUSTER_FIRST.value:
        return solve_cluster_first(
            matrix,
            points=points,
            min_route_time_sec=min_route_time_sec,
            max_route_time_sec=max_route_time_sec,
            service_time_sec=service_time_sec,
            time_limit_sec=time_limit_sec,
            timer=timer,
        )
    solver = ArbocensusVRPSolver(
        matrix,
        min_route_time_sec=min_route_time_sec,
        max_route_time_sec=max_route_time_sec,
        service_time_sec=service_time_sec,
        max_vehicles=max_vehicles,
        time_limit_sec=time_limit_sec,
    )
    return solver.solve(timer=timer)


def solve_spatial_term(
    matrix,
    *,
    points,
    min_route_time_sec,
    max_route_time_sec,
    service_time_sec,
    max_vehicles,
    time_limit_sec=180,
    span_coef=SPATIAL_SPAN_COEF,
    timer=None,
):
    solver = ArbocensusVRPSolver(
        matrix,
        min_route_time_sec=min_route_time_sec,
        max_route_time_sec=max_route_time_sec,
        service_time_sec=service_time_sec,
        max_vehicles=max_vehicles,
        time_limit_sec=time_limit_sec,
        spatial_points=points,
        span_coef=span_coef,
    )
    return solver.solve(timer=timer)


def project_equirectangular(points):
    arr = np.asarray(points, dtype=float)
    lat0 = np.radians(arr[:, 0].mean())
    x = np.radians(arr[:, 1]) * np.cos(lat0) * EARTH_RADIUS_M
    y = np.radians(arr[:, 0]) * EARTH_RADIUS_M
    return np.column_stack([x, y])


def _kmeans_plusplus_init(coords, k, rng):
    n = coords.shape[0]
    centroids = [coords[rng.integers(n)]]
    for _ in range(1, k):
        diffs = coords[:, None, :] - np.asarray(centroids)[None, :, :]
        d2 = np.min((diffs**2).sum(axis=2), axis=1)
        total = d2.sum()
        if total == 0:
            centroids.append(coords[rng.integers(n)])
            continue
        centroids.append(coords[rng.choice(n, p=d2 / total)])
    return np.asarray(centroids)


def kmeans(coords, k, *, seed=0, max_iters=100):
    coords = np.asarray(coords, dtype=float)
    rng = np.random.default_rng(seed)
    centroids = _kmeans_plusplus_init(coords, k, rng)
    labels = np.zeros(coords.shape[0], dtype=int)
    for _ in range(max_iters):
        dists = ((coords[:, None, :] - centroids[None, :, :]) ** 2).sum(axis=2)
        labels = dists.argmin(axis=1)
        new_centroids = np.array(
            [
                coords[labels == c].mean(axis=0)
                if np.any(labels == c)
                else centroids[c]
                for c in range(k)
            ]
        )
        if np.allclose(new_centroids, centroids):
            break
        centroids = new_centroids
    return labels


def choose_k(n, matrix, service_time_sec, min_route_time_sec, max_route_time_sec):
    # Nearest-neighbor travel, not mean pairwise travel: a route visits consecutive
    # stops, so the mean distance between ALL node pairs of a metro-wide matrix
    # overstates per-tree travel by orders of magnitude and explodes k.
    t_target = (min_route_time_sec + max_route_time_sec) // 2
    per_tree_work = service_time_sec + mean_nearest_neighbor_travel(
        build_open_matrix(matrix)
    )
    k = max(1, round(n * per_tree_work / t_target))
    return min(k, n)


def solve_cluster_first(
    matrix,
    *,
    points,
    min_route_time_sec,
    max_route_time_sec,
    service_time_sec,
    time_limit_sec=180,
    seed=0,
    timer=None,
):
    matrix = np.asarray(matrix, dtype=float)
    n = matrix.shape[0]
    k = choose_k(n, matrix, service_time_sec, min_route_time_sec, max_route_time_sec)
    coords = project_equirectangular(points)
    labels = kmeans(coords, k, seed=seed)

    routes = []
    covered = []
    dropped = []
    for cluster_id in range(k):
        members = [i for i in range(n) if labels[i] == cluster_id]
        if not members:
            continue
        sub_matrix = matrix[np.ix_(members, members)]
        total_service = len(members) * service_time_sec
        max_vehicles = estimate_max_vehicles(
            build_open_matrix(sub_matrix), total_service, min_route_time_sec
        )
        result = ArbocensusVRPSolver(
            sub_matrix,
            min_route_time_sec=min_route_time_sec,
            max_route_time_sec=max_route_time_sec,
            service_time_sec=service_time_sec,
            max_vehicles=max_vehicles,
            time_limit_sec=time_limit_sec,
        ).solve(timer=timer)
        if result is None:
            return None
        sub_routes, sub_dropped = result
        for sub_route in sub_routes:
            global_route = [members[node] for node in sub_route]
            routes.append(global_route)
            covered.extend(global_route)
        dropped.extend(members[node] for node in sub_dropped)

    if sorted(covered + dropped) != list(range(n)):
        raise ValueError(
            f"cluster_first node coverage mismatch: "
            f"{len(covered)} covered + {len(dropped)} dropped vs {n} trees"
        )
    return routes, dropped
