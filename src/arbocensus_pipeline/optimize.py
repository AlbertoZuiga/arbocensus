"""Inter-route local search operators for V3 routing.

This module implements delta-based relocate and swap moves over open routes,
using sparse graph distances only (no external routing APIs in the inner loop).
"""

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
