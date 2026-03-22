"""Graph stage: build nodes, dense matrix, and sparse KD-tree graph."""

from typing import Any, Dict, List

import numpy as np
from scipy.spatial import KDTree

from .utils import haversine_m


def _node_distance(nodes: List[Dict[str, Any]], i: int, j: int) -> float:
    return haversine_m(
        float(nodes[i]["lat"]),
        float(nodes[i]["lng"]),
        float(nodes[j]["lat"]),
        float(nodes[j]["lng"]),
    )


def _set_min_edge(
    adjacency: Dict[int, Dict[int, float]],
    src: int,
    dst: int,
    distance_m: float,
) -> None:
    prev = adjacency[src].get(dst)
    if prev is None or distance_m < prev:
        adjacency[src][dst] = distance_m


def _add_symmetric_edge(
    adjacency: Dict[int, Dict[int, float]],
    i: int,
    j: int,
    distance_m: float,
) -> None:
    _set_min_edge(adjacency, i, j, distance_m)
    _set_min_edge(adjacency, j, i, distance_m)


def build_nodes(trees: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    nodes = []
    for i, t in enumerate(trees):
        lat = t.get("lat") if isinstance(t, dict) else None
        lng = t.get("lng") if isinstance(t, dict) else None
        if lat is None:
            lat = t.get("latitude")
        if lng is None:
            lng = t.get("longitude")
        nodes.append(
            {
                "id": i,
                "lat": float(lat),
                "lng": float(lng),
                "meta": t.get("meta") if isinstance(t, dict) else None,
            }
        )
    return nodes


def compute_matrix( # TODO: Remove legacy once --v3 becomes the default
    nodes: List[Dict[str, Any]]
) -> List[List[float]]:
    n = len(nodes)
    mat = [[0.0] * n for _ in range(n)]
    for i in range(n):
        lat1 = nodes[i]["lat"]
        lon1 = nodes[i]["lng"]
        for j in range(i + 1, n):
            lat2 = nodes[j]["lat"]
            lon2 = nodes[j]["lng"]
            d = haversine_m(lat1, lon1, lat2, lon2)
            mat[i][j] = d
            mat[j][i] = d
    return mat


def build_kd_tree(nodes: List[Dict[str, Any]]) -> KDTree:
    coords = np.array([[float(n["lat"]), float(n["lng"])] for n in nodes], dtype=float)
    if coords.size == 0:
        coords = np.empty((0, 2), dtype=float)
    return KDTree(coords)


def build_sparse_graph_from_kdtree(
    nodes: List[Dict[str, Any]],
    kd_tree: KDTree,
    k_neighbors: int = 12,
) -> Dict[int, List[tuple[int, float]]]:
    n = len(nodes)
    adjacency: Dict[int, Dict[int, float]] = {i: {} for i in range(n)}

    if n == 0:
        return {i: [] for i in range(n)}

    k_eff = max(0, min(int(k_neighbors), n - 1))
    if k_eff == 0:
        return {i: [] for i in range(n)}

    for i, node in enumerate(nodes):
        query_point = [float(node["lat"]), float(node["lng"])]
        _, neighbor_idx = kd_tree.query(query_point, k=k_eff + 1)
        neighbor_ids = [int(idx) for idx in np.atleast_1d(neighbor_idx).tolist()[1:]]

        for j in neighbor_ids:
            if j == i:
                continue
            _add_symmetric_edge(adjacency, i, j, _node_distance(nodes, i, j))

    return {
        i: sorted(nbrs.items(), key=lambda item: item[0])
        for i, nbrs in adjacency.items()
    }
