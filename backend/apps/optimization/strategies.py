import numpy as np
from apps.optimization.models import RoutingConfig
from apps.optimization.n_estimator import average_pair_travel, estimate_max_vehicles
from apps.optimization.route_metrics import EARTH_RADIUS_M, haversine
from apps.optimization.solver import (
    FIXED_VEHICLE_COST,
    SOFT_LOWER_PENALTY,
    SOFT_UPPER_PENALTY,
    ArbocensusVRPSolver,
    build_open_matrix,
)
from ortools.constraint_solver import pywrapcp, routing_enums_pb2

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
):
    if strategy == RoutingConfig.Strategy.SPATIAL_TERM:
        return solve_spatial_term(
            matrix,
            points=points,
            min_route_time_sec=min_route_time_sec,
            max_route_time_sec=max_route_time_sec,
            service_time_sec=service_time_sec,
            max_vehicles=max_vehicles,
            time_limit_sec=time_limit_sec,
        )
    if strategy == RoutingConfig.Strategy.CLUSTER_FIRST:
        return solve_cluster_first(
            matrix,
            points=points,
            min_route_time_sec=min_route_time_sec,
            max_route_time_sec=max_route_time_sec,
            service_time_sec=service_time_sec,
            time_limit_sec=time_limit_sec,
        )
    solver = ArbocensusVRPSolver(
        matrix,
        min_route_time_sec=min_route_time_sec,
        max_route_time_sec=max_route_time_sec,
        service_time_sec=service_time_sec,
        max_vehicles=max_vehicles,
        time_limit_sec=time_limit_sec,
    )
    return solver.solve()


def _open_geo_matrix(points):
    n = len(points) + 1
    geo = np.zeros((n, n))
    for i, a in enumerate(points):
        for j, b in enumerate(points):
            if i != j:
                geo[i + 1][j + 1] = haversine(a, b)
    return geo


def _extract_routes(manager, routing, solution, max_vehicles):
    routes = []
    for vehicle_id in range(max_vehicles):
        index = routing.Start(vehicle_id)
        route = []
        while not routing.IsEnd(index):
            node = manager.IndexToNode(index) - 1
            if node >= 0:
                route.append(node)
            index = solution.Value(routing.NextVar(index))
        if route:
            routes.append(route)
    return routes


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
):
    open_matrix = build_open_matrix(matrix)
    geo_matrix = _open_geo_matrix(points)
    n = open_matrix.shape[0]

    manager = pywrapcp.RoutingIndexManager(n, max_vehicles, 0)
    routing = pywrapcp.RoutingModel(manager)

    def time_callback(from_index, to_index):
        from_node = manager.IndexToNode(from_index)
        to_node = manager.IndexToNode(to_index)
        travel = open_matrix[from_node][to_node]
        service = service_time_sec if from_node != 0 else 0
        return int(travel + service)

    time_cb = routing.RegisterTransitCallback(time_callback)
    routing.SetArcCostEvaluatorOfAllVehicles(time_cb)

    routing.AddDimension(time_cb, 0, max_route_time_sec, True, "Time")
    time_dimension = routing.GetDimensionOrDie("Time")

    def distance_callback(from_index, to_index):
        from_node = manager.IndexToNode(from_index)
        to_node = manager.IndexToNode(to_index)
        return int(geo_matrix[from_node][to_node])

    distance_cb = routing.RegisterTransitCallback(distance_callback)
    routing.AddDimension(distance_cb, 0, 10_000_000, True, "Distance")
    distance_dimension = routing.GetDimensionOrDie("Distance")
    distance_dimension.SetSpanCostCoefficientForAllVehicles(span_coef)

    routing.SetFixedCostOfAllVehicles(FIXED_VEHICLE_COST)

    midpoint = (min_route_time_sec + max_route_time_sec) // 2
    for vehicle_id in range(max_vehicles):
        end_index = routing.End(vehicle_id)
        time_dimension.SetCumulVarSoftLowerBound(
            end_index, min_route_time_sec, SOFT_LOWER_PENALTY
        )
        time_dimension.SetCumulVarSoftUpperBound(
            end_index, midpoint, SOFT_UPPER_PENALTY
        )

    search_params = pywrapcp.DefaultRoutingSearchParameters()
    search_params.first_solution_strategy = (
        routing_enums_pb2.FirstSolutionStrategy.PATH_CHEAPEST_ARC
    )
    search_params.local_search_metaheuristic = (
        routing_enums_pb2.LocalSearchMetaheuristic.GUIDED_LOCAL_SEARCH
    )
    search_params.time_limit.FromSeconds(time_limit_sec)

    solution = routing.SolveWithParameters(search_params)
    if solution is None:
        return None
    return _extract_routes(manager, routing, solution, max_vehicles)


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
    t_target = (min_route_time_sec + max_route_time_sec) // 2
    per_tree_work = service_time_sec + average_pair_travel(build_open_matrix(matrix))
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
):
    matrix = np.asarray(matrix, dtype=float)
    n = matrix.shape[0]
    k = choose_k(n, matrix, service_time_sec, min_route_time_sec, max_route_time_sec)
    coords = project_equirectangular(points)
    labels = kmeans(coords, k, seed=seed)

    routes = []
    covered = []
    for cluster_id in range(k):
        members = [i for i in range(n) if labels[i] == cluster_id]
        if not members:
            continue
        sub_matrix = matrix[np.ix_(members, members)]
        total_service = len(members) * service_time_sec
        max_vehicles = estimate_max_vehicles(
            build_open_matrix(sub_matrix), total_service, min_route_time_sec
        )
        sub_routes = ArbocensusVRPSolver(
            sub_matrix,
            min_route_time_sec=min_route_time_sec,
            max_route_time_sec=max_route_time_sec,
            service_time_sec=service_time_sec,
            max_vehicles=max_vehicles,
            time_limit_sec=time_limit_sec,
        ).solve()
        if sub_routes is None:
            raise ValueError(
                f"cluster_first: cluster {cluster_id} infeasible "
                f"(size={len(members)}, max_route_time={max_route_time_sec}s, "
                f"service_time={service_time_sec}s, max_vehicles={max_vehicles})"
            )
        for sub_route in sub_routes:
            global_route = [members[node] for node in sub_route]
            routes.append(global_route)
            covered.extend(global_route)

    assert sorted(covered) == list(range(n)), (
        f"cluster_first node coverage mismatch: "
        f"{len(covered)} covered ({len(set(covered))} unique) vs {n} trees"
    )
    return routes
