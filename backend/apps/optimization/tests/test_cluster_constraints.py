import numpy as np
from apps.optimization import cluster_constraints
from apps.optimization.cluster_constraints import (
    build_cluster_plan,
    cluster_neighbourhoods,
    compact_labels,
)

SANTIAGO_LAT = -33.45
SANTIAGO_LON = -70.65

SERVICE_TIME_SEC = 120
MIN_ROUTE_TIME_SEC = 7_200
MAX_ROUTE_TIME_SEC = 10_800


def three_cluster_points(per_cluster):
    points = []
    for offset in (0.0, 0.5, 1.0):
        for i in range(per_cluster):
            points.append(
                (SANTIAGO_LAT + offset + i * 0.0005, SANTIAGO_LON + offset + i * 0.0005)
            )
    return points


def uniform_matrix(n, travel=600.0):
    m = np.full((n, n), travel)
    np.fill_diagonal(m, 0.0)
    return m


def plan_for(points, *, neighbors, max_vehicles, monkeypatch, k):
    monkeypatch.setattr(cluster_constraints, "choose_k", lambda *a, **kw: k)
    return build_cluster_plan(
        points,
        uniform_matrix(len(points)),
        service_time_sec=SERVICE_TIME_SEC,
        min_route_time_sec=MIN_ROUTE_TIME_SEC,
        max_route_time_sec=MAX_ROUTE_TIME_SEC,
        max_vehicles=max_vehicles,
        neighbors=neighbors,
        seed=0,
    )


def test_compact_labels_drops_empty_clusters():
    labels, count = compact_labels(np.array([0, 0, 2, 2]), 3)

    assert labels == [0, 0, 1, 1]
    assert count == 2


def test_neighbourhood_of_zero_neighbors_is_the_cluster_itself():
    centroids = np.array([[0.0, 0.0], [10.0, 0.0], [100.0, 0.0]])

    assert cluster_neighbourhoods(centroids, 0) == [[0], [1], [2]]


def test_neighbourhood_grows_with_the_nearest_centroids():
    centroids = np.array([[0.0, 0.0], [10.0, 0.0], [100.0, 0.0]])

    assert cluster_neighbourhoods(centroids, 1) == [[0, 1], [0, 1], [1, 2]]
    assert cluster_neighbourhoods(centroids, 2) == [[0, 1, 2]] * 3


def test_every_cluster_owns_the_same_number_of_vehicles(monkeypatch):
    plan = plan_for(
        three_cluster_points(4),
        neighbors=0,
        max_vehicles=7,
        monkeypatch=monkeypatch,
        k=3,
    )

    assert plan.cluster_count == 3
    assert plan.vehicles_per_cluster == 3
    assert plan.vehicle_count == 9


def test_zero_neighbors_confines_each_node_to_its_own_cluster(monkeypatch):
    plan = plan_for(
        three_cluster_points(4),
        neighbors=0,
        max_vehicles=3,
        monkeypatch=monkeypatch,
        k=3,
    )

    allowed_by_label = {
        label: tuple(allowed)
        for label, allowed in zip(plan.labels, plan.allowed_vehicles, strict=True)
    }
    assert len(allowed_by_label) == 3
    assert sorted(v for allowed in allowed_by_label.values() for v in allowed) == [
        0,
        1,
        2,
    ]


def test_neighbors_widen_the_allowed_vehicle_set(monkeypatch):
    points = three_cluster_points(4)
    narrow = plan_for(points, neighbors=0, max_vehicles=3, monkeypatch=monkeypatch, k=3)
    wide = plan_for(points, neighbors=1, max_vehicles=3, monkeypatch=monkeypatch, k=3)

    for node in range(len(points)):
        assert set(narrow.allowed_vehicles[node]) < set(wide.allowed_vehicles[node])


def test_every_node_keeps_at_least_one_vehicle(monkeypatch):
    plan = plan_for(
        three_cluster_points(4),
        neighbors=2,
        max_vehicles=3,
        monkeypatch=monkeypatch,
        k=3,
    )

    assert all(allowed for allowed in plan.allowed_vehicles)
    assert len(plan.allowed_vehicles) == 12
