"""Inter-route local search operators for routing.

This module implements delta-based relocate and swap moves over open routes,
using sparse graph distances only (no external routing APIs in the inner loop).
"""

from collections import Counter
from math import ceil
from statistics import mean
from typing import Callable, Dict, List, Optional, Tuple

from .cluster import k_means_constrained
from .graph import build_kd_tree, build_sparse_graph_from_kdtree
from .routing import RoutingCache
from .utils import (
    estimate_euclidean_tsp,
    nn_path_sparse,
    route_length_sparse,
    sparse_distance,
    two_opt_sparse,
)

SparseGraph = Dict[int, List[Tuple[int, float]]]

EPS = 1e-9
MAX_LOCAL_ITER = 50


def insertion_cost(
    node: int,
    route: List[int],
    position: int,
    sparse_graph: SparseGraph,
    all_nodes: List[dict],
) -> float:
    """Return delta cost of inserting ``node`` at ``position`` in an open route."""
    if not route:
        return 0.0

    if position <= 0:
        return sparse_distance(sparse_graph, node, route[0], all_nodes)

    if position >= len(route):
        return sparse_distance(sparse_graph, route[-1], node, all_nodes)

    left = route[position - 1]
    right = route[position]
    return (
        sparse_distance(sparse_graph, left, node, all_nodes)
        + sparse_distance(sparse_graph, node, right, all_nodes)
        - sparse_distance(sparse_graph, left, right, all_nodes)
    )


def removal_cost(
    node_index_in_route: int,
    route: List[int],
    sparse_graph: SparseGraph,
    all_nodes: List[dict],
) -> float:
    """Return savings obtained by removing a node from an open route.

    A positive value means the route becomes shorter by that amount.
    """
    n = len(route)
    if n <= 1:
        return 0.0

    idx = node_index_in_route
    if idx <= 0:
        return sparse_distance(sparse_graph, route[0], route[1], all_nodes)

    if idx >= n - 1:
        return sparse_distance(sparse_graph, route[-2], route[-1], all_nodes)

    prev_node = route[idx - 1]
    node = route[idx]
    next_node = route[idx + 1]
    return (
        sparse_distance(sparse_graph, prev_node, node, all_nodes)
        + sparse_distance(sparse_graph, node, next_node, all_nodes)
        - sparse_distance(sparse_graph, prev_node, next_node, all_nodes)
    )


def _best_insertion_position(
    node: int,
    route: List[int],
    sparse_graph: SparseGraph,
    all_nodes: List[dict],
) -> Tuple[int, float]:
    best_position = 0
    best_delta = float("inf")

    for position in range(len(route) + 1):
        delta = insertion_cost(node, route, position, sparse_graph, all_nodes)
        if delta + EPS < best_delta:
            best_delta = delta
            best_position = position

    return best_position, best_delta


def _routes_node_multiset(routes: List[List[int]]) -> Counter:
    return Counter(node for route in routes for node in route)


def _all_routes_under_upper_bound(durations: List[float], upper_bound: float) -> bool:
    return all(d <= upper_bound + EPS for d in durations)


def _find_first_relocate_move(
    routes: List[List[int]],
    durations: List[float],
    sparse_graph: SparseGraph,
    all_nodes: List[dict],
    upper_bound: float,
):
    source_idx = max(range(len(durations)), key=lambda i: durations[i])
    source_route = routes[source_idx]
    if len(source_route) <= 2:
        return None

    global_max = max(durations)

    for src_pos, node in enumerate(source_route):
        saved = removal_cost(src_pos, source_route, sparse_graph, all_nodes)
        source_after = source_route[:src_pos] + source_route[src_pos + 1 :]
        if not source_after:
            continue
        source_new_duration = durations[source_idx] - saved

        for dest_idx, dest_route in enumerate(routes):
            if dest_idx == source_idx:
                continue

            insert_pos, insert_delta = _best_insertion_position(
                node,
                dest_route,
                sparse_graph,
                all_nodes,
            )
            dest_new_duration = durations[dest_idx] + insert_delta
            if dest_new_duration > upper_bound + EPS:
                continue

            candidate_durations = durations[:]
            candidate_durations[source_idx] = source_new_duration
            candidate_durations[dest_idx] = dest_new_duration
            if max(candidate_durations) + EPS >= global_max:
                continue

            new_dest_route = dest_route[:insert_pos] + [node] + dest_route[insert_pos:]
            return (
                source_idx,
                dest_idx,
                source_after,
                new_dest_route,
                source_new_duration,
                dest_new_duration,
            )

    return None


def _apply_relocate_move(routes: List[List[int]], durations: List[float], move) -> None:
    source_idx, dest_idx, new_source_route, new_dest_route, src_dur, dst_dur = move
    routes[source_idx] = new_source_route
    routes[dest_idx] = new_dest_route
    durations[source_idx] = src_dur
    durations[dest_idx] = dst_dur


def _evaluate_swap_candidate(
    routes: List[List[int]],
    durations: List[float],
    sparse_graph: SparseGraph,
    all_nodes: List[dict],
    upper_bound: float,
    long_idx: int,
    other_idx: int,
    idx_a: int,
    idx_b: int,
    global_max: float,
):
    long_route = routes[long_idx]
    other_route = routes[other_idx]

    node_a = long_route[idx_a]
    node_b = other_route[idx_b]

    saved_a = removal_cost(idx_a, long_route, sparse_graph, all_nodes)
    saved_b = removal_cost(idx_b, other_route, sparse_graph, all_nodes)

    long_wo_a = long_route[:idx_a] + long_route[idx_a + 1 :]
    other_wo_b = other_route[:idx_b] + other_route[idx_b + 1 :]

    ins_a_pos = min(idx_a, len(long_wo_a))
    ins_b_pos = min(idx_b, len(other_wo_b))

    insert_b_in_long = insertion_cost(
        node_b,
        long_wo_a,
        ins_a_pos,
        sparse_graph,
        all_nodes,
    )
    insert_a_in_other = insertion_cost(
        node_a,
        other_wo_b,
        ins_b_pos,
        sparse_graph,
        all_nodes,
    )

    long_new_duration = durations[long_idx] - saved_a + insert_b_in_long
    other_new_duration = durations[other_idx] - saved_b + insert_a_in_other

    if long_new_duration > upper_bound + EPS or other_new_duration > upper_bound + EPS:
        return None

    candidate_durations = durations[:]
    candidate_durations[long_idx] = long_new_duration
    candidate_durations[other_idx] = other_new_duration
    if max(candidate_durations) + EPS >= global_max:
        return None

    new_long_route = long_wo_a[:ins_a_pos] + [node_b] + long_wo_a[ins_a_pos:]
    new_other_route = other_wo_b[:ins_b_pos] + [node_a] + other_wo_b[ins_b_pos:]
    return (
        long_idx,
        other_idx,
        new_long_route,
        new_other_route,
        long_new_duration,
        other_new_duration,
    )


def _find_first_swap_move(
    routes: List[List[int]],
    durations: List[float],
    sparse_graph: SparseGraph,
    all_nodes: List[dict],
    upper_bound: float,
):
    long_idx = max(range(len(durations)), key=lambda i: durations[i])
    long_route = routes[long_idx]
    if not long_route:
        return None

    global_max = max(durations)

    for other_idx, other_route in enumerate(routes):
        if other_idx == long_idx or not other_route:
            continue

        for idx_a in range(len(long_route)):
            for idx_b in range(len(other_route)):
                move = _evaluate_swap_candidate(
                    routes,
                    durations,
                    sparse_graph,
                    all_nodes,
                    upper_bound,
                    long_idx,
                    other_idx,
                    idx_a,
                    idx_b,
                    global_max,
                )
                if move is not None:
                    return move

    return None


def _apply_swap_move(routes: List[List[int]], durations: List[float], move) -> None:
    long_idx, other_idx, new_long_route, new_other_route, long_dur, other_dur = move
    routes[long_idx] = new_long_route
    routes[other_idx] = new_other_route
    durations[long_idx] = long_dur
    durations[other_idx] = other_dur


def relocate_nodes_between_routes(
    routes: List[List[int]],
    durations: List[float],
    sparse_graph: SparseGraph,
    all_nodes: List[dict],
    upper_bound: float,
) -> Tuple[List[List[int]], List[float]]:
    """Greedy relocate moves from the longest route to other routes.

    Returns updated ``(routes, durations)`` using only sparse-graph delta updates.
    """
    if not routes or len(routes) <= 1:
        return routes, durations

    if _all_routes_under_upper_bound(durations, upper_bound):
        return routes, durations

    baseline_nodes = _routes_node_multiset(routes)

    for _ in range(MAX_LOCAL_ITER):
        move = _find_first_relocate_move(
            routes,
            durations,
            sparse_graph,
            all_nodes,
            upper_bound,
        )
        if move is None:
            break
        _apply_relocate_move(routes, durations, move)

    if _routes_node_multiset(routes) != baseline_nodes:
        raise ValueError("Node conservation violated after relocate operation")

    if any(len(route) == 0 for route in routes):
        raise ValueError("Empty route produced after relocate operation")

    return routes, durations


def swap_nodes_between_routes(
    routes: List[List[int]],
    durations: List[float],
    sparse_graph: SparseGraph,
    all_nodes: List[dict],
    upper_bound: float,
) -> Tuple[List[List[int]], List[float]]:
    """Greedy swap moves between the longest route and all others.

    Each candidate swap uses only local deltas around affected positions.
    """
    if not routes or len(routes) <= 1:
        return routes, durations

    if _all_routes_under_upper_bound(durations, upper_bound):
        return routes, durations

    baseline_nodes = _routes_node_multiset(routes)

    for _ in range(MAX_LOCAL_ITER):
        move = _find_first_swap_move(
            routes,
            durations,
            sparse_graph,
            all_nodes,
            upper_bound,
        )
        if move is None:
            break
        _apply_swap_move(routes, durations, move)

    if _routes_node_multiset(routes) != baseline_nodes:
        raise ValueError("Node conservation violated after swap operation")

    if any(len(route) == 0 for route in routes):
        raise ValueError("Empty route produced after swap operation")

    return routes, durations


def local_search_inter_route(
    routes: List[List[int]],
    durations: List[float],
    sparse_graph: SparseGraph,
    all_nodes: List[dict],
    upper_bound: float,
) -> Tuple[List[List[int]], List[float]]:
    """Run inter-route local search (relocate first, then swap)."""
    routes, durations = relocate_nodes_between_routes(
        routes,
        durations,
        sparse_graph,
        all_nodes,
        upper_bound,
    )
    routes, durations = swap_nodes_between_routes(
        routes,
        durations,
        sparse_graph,
        all_nodes,
        upper_bound,
    )
    return routes, durations


def nearest_neighbor_path(
    members: List[int],
    sparse_graph: SparseGraph,
    all_nodes: List[dict],
) -> List[int]:
    """Build an open path with NN heuristic, trying all starts in the cluster."""
    if not members:
        return []
    if len(members) == 1:
        return members[:]

    best_route: Optional[List[int]] = None
    best_length = float("inf")
    for start in members:
        candidate = nn_path_sparse(start, members, sparse_graph, all_nodes)
        candidate_len = route_length_sparse(candidate, sparse_graph, all_nodes)
        if candidate_len + EPS < best_length:
            best_route = candidate
            best_length = candidate_len

    return best_route if best_route is not None else members[:]


def two_opt_path(
    route: List[int],
    sparse_graph: SparseGraph,
    all_nodes: List[dict],
    max_iter: int = 100,
) -> List[int]:
    """Open-path 2-opt over sparse graph costs."""
    return two_opt_sparse(route, sparse_graph, all_nodes, max_iter=max_iter)


def compute_route_time_with_cache(
    route: List[int],
    locations: List[dict],
    f_route_time: Callable[[dict, dict, RoutingCache], float],
    cache: RoutingCache,
    t_per_tree: float,
) -> float:
    """Compute open-route travel+service time using a cache-backed edge evaluator."""
    if not route:
        return 0.0

    total_travel_time = 0.0
    for i in range(len(route) - 1):
        a = locations[route[i]]
        b = locations[route[i + 1]]
        total_travel_time += float(f_route_time(a, b, cache))

    total_service_time = float(len(route)) * float(t_per_tree)
    return float(total_travel_time + total_service_time)


def _safe_cache_path(
    f_route_time: Callable[[dict, dict, RoutingCache], float],
) -> str | None:
    path = getattr(f_route_time, "cache_path", None)
    if isinstance(path, str) and path.strip():
        return path
    return None


def _load_cache_if_available(
    cache: RoutingCache,
    f_route_time: Callable[[dict, dict, RoutingCache], float],
) -> None:
    cache_path = _safe_cache_path(f_route_time)
    if cache_path:
        cache.load_from_disk(cache_path)


def _save_cache_if_available(
    cache: RoutingCache,
    f_route_time: Callable[[dict, dict, RoutingCache], float],
) -> None:
    cache_path = _safe_cache_path(f_route_time)
    if cache_path:
        cache.save_to_disk(cache_path)


def _clone_routes(routes: List[List[int]]) -> List[List[int]]:
    return [r[:] for r in routes]


def _build_routes_and_durations(
    locations: List[dict],
    clusters: List[List[int]],
    sparse_graph: SparseGraph,
    osm_cache: RoutingCache,
    f_osm_route_time: Callable[[dict, dict, RoutingCache], float],
    t_per_tree: float,
) -> Tuple[List[List[int]], List[float]]:
    routes: List[List[int]] = []
    durations: List[float] = []
    for members in clusters:
        route = nearest_neighbor_path(members, sparse_graph, locations)
        route = two_opt_path(route, sparse_graph, locations, max_iter=60)
        duration = compute_route_time_with_cache(
            route,
            locations,
            f_osm_route_time,
            osm_cache,
            t_per_tree,
        )
        routes.append(route)
        durations.append(duration)
    return routes, durations


def _duration_metrics(
    durations: List[float],
    lower_bound: float,
    upper_bound: float,
) -> Dict[str, float]:
    max_route = max(durations)
    min_route = min(durations)
    avg_route = mean(durations)
    spread = max_route - min_route
    over_gap = max(0.0, max_route - upper_bound)
    under_gap = max(0.0, lower_bound - min_route)
    band_gap = over_gap + under_gap
    feasible_score = avg_route + 0.25 * spread
    return {
        "max_route": max_route,
        "min_route": min_route,
        "avg_route": avg_route,
        "spread": spread,
        "over_gap": over_gap,
        "under_gap": under_gap,
        "band_gap": band_gap,
        "feasible_score": feasible_score,
    }


def _initial_n_routes(
    locations: List[dict],
    expected_duration_per_route: float,
    t_per_tree: float,
) -> int:
    total_euclidean_km = estimate_euclidean_tsp(locations)
    walking_speed_kmh = 4.0
    travel_time_estimate = (total_euclidean_km / walking_speed_kmh) * 3600.0
    service_time_estimate = float(len(locations)) * float(t_per_tree)
    total_time_estimate = travel_time_estimate + service_time_estimate
    n_routes = max(
        1, int(ceil(total_time_estimate / float(expected_duration_per_route)))
    )
    return min(n_routes, len(locations))


def _evaluate_iteration(
    locations: List[dict],
    n_routes: int,
    sparse_graph: SparseGraph,
    osm_cache: RoutingCache,
    f_osm_route_time: Callable[[dict, dict, RoutingCache], float],
    t_per_tree: float,
    lower_bound: float,
    upper_bound: float,
    hard_upper_limit: float,
) -> Dict[str, object]:
    clusters = k_means_constrained(locations, n_clusters=n_routes)
    routes, durations = _build_routes_and_durations(
        locations,
        clusters,
        sparse_graph,
        osm_cache,
        f_osm_route_time,
        t_per_tree,
    )

    routes, durations = local_search_inter_route(
        routes,
        durations,
        sparse_graph,
        locations,
        upper_bound,
    )

    durations = [
        compute_route_time_with_cache(
            route,
            locations,
            f_osm_route_time,
            osm_cache,
            t_per_tree,
        )
        for route in routes
    ]

    metrics = _duration_metrics(durations, lower_bound, upper_bound)
    feasible = (
        metrics["max_route"] <= upper_bound + EPS
        and metrics["min_route"] >= lower_bound - EPS
        and metrics["max_route"] <= hard_upper_limit + EPS
    )

    return {
        "routes": routes,
        "durations": durations,
        "metrics": metrics,
        "feasible": feasible,
    }


def _update_hysteresis_and_n_routes(
    n_routes: int,
    n_locations: int,
    over_counter: int,
    under_counter: int,
    last_direction: int,
    hysteresis_rounds: int,
    expected_duration_per_route: float,
    lower_bound: float,
    upper_bound: float,
    max_route: float,
    min_route: float,
    avg_route: float,
) -> Tuple[int, int, int, int]:
    if max_route > upper_bound + EPS:
        over_counter += 1
        under_counter = 0
    elif min_route < lower_bound - EPS:
        under_counter += 1
        over_counter = 0
    else:
        over_counter = 0
        under_counter = 0

    change_direction = 0
    if over_counter >= hysteresis_rounds:
        if avg_route > upper_bound + EPS:
            factor = avg_route / float(expected_duration_per_route)
            delta_n = max(1, int(ceil(n_routes * (factor - 1.0))))
        else:
            delta_n = 1
        n_routes = min(n_locations, n_routes + delta_n)
        change_direction = +1
        over_counter = 0
    elif under_counter >= hysteresis_rounds:
        n_routes = max(1, n_routes - 1)
        change_direction = -1
        under_counter = 0

    if change_direction != 0 and (last_direction * change_direction < 0):
        if change_direction > 0:
            over_counter = 1
        else:
            under_counter = 1

    if change_direction != 0:
        last_direction = change_direction

    return n_routes, over_counter, under_counter, last_direction


def _validate_final_routes(
    final_routes_idx: List[List[int]],
    locations: List[dict],
    t_per_tree: float,
    f_google_route_time: Callable[[dict, dict, RoutingCache], float],
    google_cache: RoutingCache,
) -> List[Tuple[List[int], float]]:
    validated: List[Tuple[List[int], float]] = []
    for route_idx in final_routes_idx:
        duration_google = compute_route_time_with_cache(
            route_idx,
            locations,
            f_google_route_time,
            google_cache,
            float(t_per_tree),
        )
        validated.append((route_idx[:], duration_google))
    return validated


def find_routes(
    locations,
    t_per_tree,
    f_google_route_time,
    f_osm_route_time,
    expected_duration_per_route=150.0,
    lower_factor=0.90,
    upper_factor=1.10,
    k_neighbors: int = 12,
    max_iterations: int = 14,
    hysteresis_rounds: int = 2,
    hard_max_duration: Optional[float] = None,
) -> List[Tuple[List[int], float]]:
    """route orchestrator with dynamic cluster count and multi-fidelity routing."""
    if not locations:
        return []

    osm_cache = RoutingCache()
    google_cache = RoutingCache()
    _load_cache_if_available(osm_cache, f_osm_route_time)
    _load_cache_if_available(google_cache, f_google_route_time)

    lower_bound = float(expected_duration_per_route) * float(lower_factor)
    upper_bound = float(expected_duration_per_route) * float(upper_factor)
    hard_upper_limit = (
        float(hard_max_duration)
        if hard_max_duration is not None
        else float(upper_bound)
    )

    best_feasible_solution: Optional[List[List[int]]] = None
    best_feasible_score = float("inf")
    best_overall_solution: Optional[List[List[int]]] = None
    best_overall_gap = float("inf")

    over_counter = 0
    under_counter = 0
    last_direction = 0
    converged = False
    n_locations = len(locations)
    n_routes = _initial_n_routes(
        locations, float(expected_duration_per_route), float(t_per_tree)
    )

    kd_tree = build_kd_tree(locations)
    sparse_graph = build_sparse_graph_from_kdtree(locations, kd_tree, k_neighbors)

    last_routes: List[List[int]] = [list(range(n_locations))]

    for iteration in range(max_iterations):
        print(f"Iteration {iteration + 1}/{max_iterations}: n_routes={n_routes}")

        evaluated = _evaluate_iteration(
            locations,
            n_routes,
            sparse_graph,
            osm_cache,
            f_osm_route_time,
            float(t_per_tree),
            lower_bound,
            upper_bound,
            hard_upper_limit,
        )
        routes = evaluated["routes"]
        metrics = evaluated["metrics"]
        feasible = bool(evaluated["feasible"])
        last_routes = _clone_routes(routes)

        max_route = float(metrics["max_route"])
        min_route = float(metrics["min_route"])
        avg_route = float(metrics["avg_route"])
        band_gap = float(metrics["band_gap"])

        print(
            f"  max={max_route:.0f}s min={min_route:.0f}s "
            f"avg={avg_route:.0f}s band_gap={band_gap:.0f}s"
        )

        if band_gap + EPS < best_overall_gap:
            best_overall_gap = band_gap
            best_overall_solution = _clone_routes(routes)

        if feasible and metrics["feasible_score"] + EPS < best_feasible_score:
            best_feasible_score = metrics["feasible_score"]
            best_feasible_solution = _clone_routes(routes)

        if feasible:
            converged = True
            print(f"Converged at iteration {iteration + 1} (feasible solution found)")
            break

        n_routes, over_counter, under_counter, last_direction = (
            _update_hysteresis_and_n_routes(
                n_routes,
                n_locations,
                over_counter,
                under_counter,
                last_direction,
                hysteresis_rounds,
                float(expected_duration_per_route),
                lower_bound,
                upper_bound,
                max_route,
                min_route,
                avg_route,
            )
        )

    if not converged:
        print(
            "Warning: did not converge after "
            f"{max_iterations} iterations, returning best available solution"
        )

    final_routes_idx = (
        best_feasible_solution
        if best_feasible_solution is not None
        else best_overall_solution
    )
    if final_routes_idx is None:
        final_routes_idx = _clone_routes(last_routes)

    validated = _validate_final_routes(
        final_routes_idx,
        locations,
        float(t_per_tree),
        f_google_route_time,
        google_cache,
    )

    _save_cache_if_available(osm_cache, f_osm_route_time)
    _save_cache_if_available(google_cache, f_google_route_time)

    return validated
