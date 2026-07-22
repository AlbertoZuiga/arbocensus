import numpy as np
from apps.optimization.bounds import (
    directed_path_travel,
    minimum_spanning_forest,
    path_travel,
    split_path,
    symmetric_mst_edges,
    symmetrized,
    tsp_path_order,
)
from apps.optimization.solver import ArbocensusVRPSolver


def line_matrix(n, step=100.0):
    # Nodes on a line, so the MST is the chain of consecutive gaps and its total is
    # known in closed form: (n-1)*step.
    coords = np.arange(n, dtype=float) * step
    return np.abs(coords[:, None] - coords[None, :])


def random_euclidean_matrix(n, seed=7, scale=400.0):
    rng = np.random.default_rng(seed)
    points = rng.random((n, 2)) * scale
    diffs = points[:, None, :] - points[None, :, :]
    return np.sqrt((diffs**2).sum(axis=2))


def test_mst_of_a_line_is_the_chain():
    edges = symmetric_mst_edges(line_matrix(5))
    assert sorted(edges) == [100.0] * 4


def test_forest_drops_the_heaviest_edges():
    edges = symmetric_mst_edges(line_matrix(5))
    assert minimum_spanning_forest(edges, 1) == 400.0
    assert minimum_spanning_forest(edges, 3) == 200.0


def test_forest_bound_uses_the_cheaper_direction():
    asymmetric = np.array([[0.0, 10.0], [3.0, 0.0]])
    assert symmetric_mst_edges(asymmetric) == [3.0]


def test_forest_bound_holds_for_a_solved_instance():
    matrix = random_euclidean_matrix(30)
    solver = ArbocensusVRPSolver(
        matrix,
        min_route_time_sec=600,
        max_route_time_sec=6_000,
        service_time_sec=60,
        max_vehicles=6,
        time_limit_sec=5,
    )
    result = solver.solve()
    assert result is not None
    routes, dropped = result
    assert dropped == []

    travel = sum(
        matrix[a][b]
        for route in routes
        for a, b in zip(route[:-1], route[1:], strict=True)
    )
    bound = minimum_spanning_forest(symmetric_mst_edges(matrix), len(routes))
    assert bound <= travel + 1e-6


def upper_bound(order, matrix, k):
    symmetric = symmetrized(matrix)
    return sum(path_travel(seg, symmetric) for seg in split_path(order, matrix, k))


def test_tsp_path_of_a_line_is_the_line_itself():
    matrix = line_matrix(6)
    order = tsp_path_order(matrix, time_limit_sec=2)
    assert order in (list(range(6)), list(reversed(range(6))))


def test_on_a_line_the_two_bounds_coincide():
    # The chain IS the optimal open path, so there is no relaxation gap to measure:
    # any gap the command reports on a real instance is geometry, not arithmetic.
    matrix = line_matrix(6)
    order = tsp_path_order(matrix, time_limit_sec=2)
    edges = symmetric_mst_edges(matrix)
    for k in (1, 2, 3):
        assert upper_bound(order, matrix, k) == minimum_spanning_forest(edges, k)


def test_split_covers_every_node_exactly_once_in_k_paths():
    matrix = random_euclidean_matrix(25)
    order = tsp_path_order(matrix, time_limit_sec=3)
    for k in (1, 3, 5):
        segments = split_path(order, matrix, k)
        assert len(segments) == k
        assert sorted(node for seg in segments for node in seg) == list(range(25))


def test_constructed_bound_never_dips_below_the_forest_bound():
    matrix = random_euclidean_matrix(25)
    order = tsp_path_order(matrix, time_limit_sec=3)
    edges = symmetric_mst_edges(matrix)
    for k in (1, 2, 3, 4, 5):
        assert upper_bound(order, matrix, k) >= minimum_spanning_forest(edges, k) - 1e-6


def test_directed_travel_walks_the_route_the_cheaper_way():
    asymmetric = np.array(
        [
            [0.0, 1.0, 50.0],
            [50.0, 0.0, 1.0],
            [1.0, 50.0, 0.0],
        ]
    )
    assert path_travel([0, 1, 2], asymmetric) == 2.0
    assert path_travel([2, 1, 0], asymmetric) == 100.0
    assert directed_path_travel([2, 1, 0], asymmetric) == 2.0
