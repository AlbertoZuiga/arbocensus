"""Inter-route local search operators for V3 routing.

This module implements delta-based relocate and swap moves over open routes,
using sparse graph distances only (no external routing APIs in the inner loop).
"""

from collections import Counter
from typing import Dict, List, Tuple

from .utils import sparse_distance

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
