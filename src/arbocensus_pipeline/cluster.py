"""Clustering helpers for balanced K-Means clustering."""

import math
from typing import Any, Dict, List

import numpy as np
from k_means_constrained import KMeansConstrained

from .utils import haversine_m


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
