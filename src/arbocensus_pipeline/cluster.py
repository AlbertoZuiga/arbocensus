"""Clustering helpers: recursive split and balanced K-Means clustering."""

import math
from typing import Any, Dict, List, Tuple

import numpy as np
from k_means_constrained import KMeansConstrained

from .utils import haversine_m


def bounding_box(  # TODO: Remove legacy once --v3 becomes the default
    nodes: List[Dict[str, Any]],
) -> Tuple[float, float, float, float]:
    lats = [n["lat"] for n in nodes]
    lngs = [n["lng"] for n in nodes]
    return min(lats), max(lats), min(lngs), max(lngs)


def longest_axis(  # TODO: Remove legacy once --v3 becomes the default
    nodes: List[Dict[str, Any]],
) -> str:
    min_lat, max_lat, min_lng, max_lng = bounding_box(nodes)
    lat_span = max_lat - min_lat
    lng_span = max_lng - min_lng
    return "lat" if lat_span >= lng_span else "lng"


def recursive_split(  # TODO: Remove legacy once --v3 becomes the default
    node_list: List[int],
    nodes: List[Dict[str, Any]],
    max_size: int,
    out_clusters: List[List[int]],
):
    if len(node_list) <= max_size:
        out_clusters.append(node_list)
        return

    subset = [nodes[i] for i in node_list]
    axis = longest_axis(subset)
    if axis == "lat":
        node_list.sort(key=lambda i: nodes[i]["lat"])
    else:
        node_list.sort(key=lambda i: nodes[i]["lng"])

    mid = len(node_list) // 2
    left = node_list[:mid]
    right = node_list[mid:]
    recursive_split(left, nodes, max_size, out_clusters)
    recursive_split(right, nodes, max_size, out_clusters)


def make_clusters_recursive(  # TODO: Remove legacy once --v3 becomes the default
    nodes: List[Dict[str, Any]], max_size: int = 100
) -> List[List[int]]:
    n = len(nodes)
    if n == 0:
        return []
    all_ids = list(range(n))
    clusters: List[List[int]] = []
    recursive_split(all_ids, nodes, max_size, clusters)
    return clusters


def _coords_from_nodes(nodes: List[Dict[str, Any]]) -> np.ndarray:
    return np.array([[float(n["lat"]), float(n["lng"])] for n in nodes], dtype=float)


def _ensure_exact_cluster_count(
    clusters: List[List[int]],
    n_clusters: int,
) -> List[List[int]]:
    if len(clusters) >= n_clusters:
        return clusters

    missing = n_clusters - len(clusters)
    clusters = [c[:] for c in clusters]
    for _ in range(missing):
        largest_idx = max(range(len(clusters)), key=lambda i: len(clusters[i]))
        if len(clusters[largest_idx]) <= 1:
            break
        moved = clusters[largest_idx].pop()
        clusters.append([moved])
    return clusters


def _labels_to_clusters(labels: np.ndarray, n_clusters: int) -> List[List[int]]:
    buckets: List[List[int]] = [[] for _ in range(n_clusters)]
    for idx, label in enumerate(labels.tolist()):
        buckets[int(label)].append(idx)
    clusters = [c for c in buckets if c]
    return _ensure_exact_cluster_count(clusters, n_clusters)


def k_means_constrained(
    nodes: List[Dict[str, Any]], n_clusters: int
) -> List[List[int]]:
    n = len(nodes)
    if n == 0:
        return []
    if n_clusters <= 0:
        raise ValueError("n_clusters must be > 0")
    if n_clusters >= n:
        return [[i] for i in range(n)]
    if n_clusters == 1:
        return [list(range(n))]

    coords = _coords_from_nodes(nodes)
    min_size = int(math.floor(n / n_clusters))
    max_size = int(math.ceil(n / n_clusters) + 1)

    model = KMeansConstrained(
        n_clusters=n_clusters,
        size_min=min_size,
        size_max=max_size,
        random_state=42,
    )
    labels = model.fit_predict(coords)
    return _labels_to_clusters(labels, n_clusters)


def cluster_diameter(cluster_indices: List[int], nodes: List[Dict[str, Any]]) -> float:
    if len(cluster_indices) <= 1:
        return 0.0

    max_distance = 0.0
    for i in range(len(cluster_indices) - 1):
        a = nodes[cluster_indices[i]]
        for j in range(i + 1, len(cluster_indices)):
            b = nodes[cluster_indices[j]]
            d = haversine_m(
                float(a["lat"]),
                float(a["lng"]),
                float(b["lat"]),
                float(b["lng"]),
            )
            if d > max_distance:
                max_distance = d
    return max_distance


def cluster_balance_score(clusters: List[List[int]]) -> float:
    if not clusters:
        return 0.0
    sizes = [len(c) for c in clusters]
    return float(max(sizes) - min(sizes))
