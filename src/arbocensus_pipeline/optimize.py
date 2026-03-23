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
