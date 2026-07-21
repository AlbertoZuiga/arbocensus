import numpy as np
from apps.optimization.bounds import minimum_spanning_forest, symmetric_mst_edges
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
