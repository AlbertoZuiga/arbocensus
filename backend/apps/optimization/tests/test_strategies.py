import numpy as np
from apps.optimization.solver import build_open_matrix
from apps.optimization.strategies import (
    kmeans,
    project_equirectangular,
    solve_cluster_first,
    solve_spatial_term,
)

SANTIAGO_LAT = -33.45
SANTIAGO_LON = -70.65


def uniform_matrix(n, travel=60.0):
    m = np.full((n, n), travel)
    np.fill_diagonal(m, 0.0)
    return m


def line_points(n, step=0.001):
    return [(SANTIAGO_LAT + i * step, SANTIAGO_LON + i * step) for i in range(n)]


def two_cluster_points(per_cluster):
    points = []
    for i in range(per_cluster):
        points.append((SANTIAGO_LAT + i * 0.0005, SANTIAGO_LON + i * 0.0005))
    for i in range(per_cluster):
        points.append(
            (SANTIAGO_LAT + 0.5 + i * 0.0005, SANTIAGO_LON + 0.5 + i * 0.0005)
        )
    return points


def route_time(open_matrix, route, service_time_sec):
    nodes = [0, *[node + 1 for node in route], 0]
    total = 0.0
    for from_node, to_node in zip(nodes[:-1], nodes[1:], strict=True):
        service = service_time_sec if from_node != 0 else 0
        total += open_matrix[from_node][to_node] + service
    return total


def test_spatial_term_visits_every_node_once():
    n = 8
    routes = solve_spatial_term(
        uniform_matrix(n),
        points=line_points(n),
        min_route_time_sec=600,
        max_route_time_sec=100_000,
        service_time_sec=300,
        max_vehicles=5,
        time_limit_sec=5,
    )
    assert routes is not None
    visited = [node for route in routes for node in route]
    assert sorted(visited) == list(range(n))
    assert len(visited) == len(set(visited))


def test_spatial_term_excludes_dummy_depot():
    n = 6
    routes = solve_spatial_term(
        uniform_matrix(n),
        points=line_points(n),
        min_route_time_sec=600,
        max_route_time_sec=100_000,
        service_time_sec=300,
        max_vehicles=5,
        time_limit_sec=5,
    )
    assert routes is not None
    for route in routes:
        for node in route:
            assert 0 <= node < n


def test_spatial_term_respects_max_route_time():
    n = 8
    matrix = uniform_matrix(n, travel=120.0)
    max_route_time = 2_000
    routes = solve_spatial_term(
        matrix,
        points=line_points(n),
        min_route_time_sec=500,
        max_route_time_sec=max_route_time,
        service_time_sec=300,
        max_vehicles=8,
        time_limit_sec=10,
    )
    assert routes is not None
    open_matrix = build_open_matrix(matrix)
    for route in routes:
        assert route_time(open_matrix, route, 300) <= max_route_time


def test_cluster_first_covers_all_nodes_once():
    per_cluster = 5
    n = per_cluster * 2
    routes = solve_cluster_first(
        uniform_matrix(n),
        points=two_cluster_points(per_cluster),
        min_route_time_sec=600,
        max_route_time_sec=100_000,
        service_time_sec=300,
        time_limit_sec=5,
    )
    assert routes is not None
    assert len(routes) >= 1
    visited = [node for route in routes for node in route]
    assert sorted(visited) == list(range(n))
    assert len(visited) == len(set(visited))


def test_cluster_first_respects_max_route_time():
    per_cluster = 5
    n = per_cluster * 2
    matrix = uniform_matrix(n, travel=120.0)
    max_route_time = 3_000
    routes = solve_cluster_first(
        matrix,
        points=two_cluster_points(per_cluster),
        min_route_time_sec=500,
        max_route_time_sec=max_route_time,
        service_time_sec=300,
        time_limit_sec=10,
    )
    assert routes is not None
    open_matrix = build_open_matrix(matrix)
    for route in routes:
        assert route_time(open_matrix, route, 300) <= max_route_time


def test_cluster_first_degenerates_to_single_cluster():
    n = 2
    routes = solve_cluster_first(
        uniform_matrix(n),
        points=line_points(n),
        min_route_time_sec=600,
        max_route_time_sec=100_000,
        service_time_sec=300,
        time_limit_sec=5,
    )
    assert routes is not None
    visited = sorted(node for route in routes for node in route)
    assert visited == [0, 1]


def test_kmeans_is_deterministic_for_seed():
    coords = project_equirectangular(two_cluster_points(6))
    first = kmeans(coords, 2, seed=7)
    second = kmeans(coords, 2, seed=7)
    assert np.array_equal(first, second)


def test_kmeans_assigns_every_point():
    coords = project_equirectangular(two_cluster_points(6))
    labels = kmeans(coords, 3, seed=0)
    assert labels.shape[0] == coords.shape[0]
    assert set(labels.tolist()).issubset(set(range(3)))


def test_kmeans_separates_distant_clusters():
    coords = project_equirectangular(two_cluster_points(5))
    labels = kmeans(coords, 2, seed=0)
    assert len(set(labels[:5].tolist())) == 1
    assert len(set(labels[5:].tolist())) == 1
    assert labels[0] != labels[5]
