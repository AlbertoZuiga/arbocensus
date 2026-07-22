import math
from typing import NamedTuple

import numpy as np
from apps.optimization.strategies import choose_k, kmeans, project_equirectangular


class ClusterPlan(NamedTuple):
    labels: list
    cluster_count: int
    vehicles_per_cluster: int
    vehicle_count: int
    allowed_vehicles: list


def compact_labels(labels, cluster_count):
    used = [c for c in range(cluster_count) if np.any(labels == c)]
    remap = {c: i for i, c in enumerate(used)}
    return [remap[int(label)] for label in labels], len(used)


def cluster_centroids(coords, labels, cluster_count):
    coords = np.asarray(coords, dtype=float)
    labels = np.asarray(labels, dtype=int)
    return np.array(
        [coords[labels == c].mean(axis=0) for c in range(cluster_count)], dtype=float
    )


def cluster_neighbourhoods(centroids, neighbors):
    d2 = ((centroids[:, None, :] - centroids[None, :, :]) ** 2).sum(axis=2)
    return [
        sorted(int(c) for c in np.argsort(d2[cluster])[: neighbors + 1])
        for cluster in range(centroids.shape[0])
    ]


def build_cluster_plan(
    points,
    matrix,
    *,
    service_time_sec,
    min_route_time_sec,
    max_route_time_sec,
    max_vehicles,
    neighbors,
    seed=0,
):
    coords = project_equirectangular(points)
    k = choose_k(
        len(points), matrix, service_time_sec, min_route_time_sec, max_route_time_sec
    )
    labels, cluster_count = compact_labels(kmeans(coords, k, seed=seed), k)
    centroids = cluster_centroids(coords, labels, cluster_count)
    neighbourhoods = cluster_neighbourhoods(centroids, neighbors)

    # Every cluster owns the same number of vehicles so that no cluster is starved by
    # the arbitrary order of a round-robin split of the estimator's fleet buffer.
    vehicles_per_cluster = max(1, math.ceil(max_vehicles / cluster_count))
    allowed_vehicles = [
        [
            vehicle
            for c in neighbourhoods[label]
            for vehicle in range(
                c * vehicles_per_cluster, (c + 1) * vehicles_per_cluster
            )
        ]
        for label in labels
    ]
    return ClusterPlan(
        labels=labels,
        cluster_count=cluster_count,
        vehicles_per_cluster=vehicles_per_cluster,
        vehicle_count=cluster_count * vehicles_per_cluster,
        allowed_vehicles=allowed_vehicles,
    )
