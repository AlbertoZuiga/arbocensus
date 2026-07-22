import numpy as np
from ortools.constraint_solver import pywrapcp, routing_enums_pb2

# Arc costs go to OR-Tools as integers; seconds are scaled to milliseconds so that
# rounding cannot make a near-optimal path look cheaper than the forest bound.
TSP_COST_SCALE = 1000


def symmetrized(matrix):
    # Symmetrize downward: a directed path can only cost more than the undirected
    # structure built on min(d_ij, d_ji), so any bound derived from it stays valid.
    real = np.asarray(matrix, dtype=float)
    return np.minimum(real, real.T)


def symmetric_mst_edges(matrix):
    symmetric = symmetrized(matrix)
    np.fill_diagonal(symmetric, np.inf)

    n = symmetric.shape[0]
    in_tree = np.zeros(n, dtype=bool)
    in_tree[0] = True
    best = symmetric[0].copy()
    best[0] = np.inf
    edges = []
    for _ in range(n - 1):
        j = int(np.argmin(np.where(in_tree, np.inf, best)))
        edges.append(float(best[j]))
        in_tree[j] = True
        best = np.minimum(best, symmetric[j])
    return sorted(edges, reverse=True)


def without_heaviest_edges(edges, k):
    # Cutting the k-1 heaviest edges of a connected structure spanning n nodes leaves
    # k components. Both bounds of this module are that same operation applied to a
    # different structure: the MST gives a lower bound, a TSP path an upper one.
    if k < 1:
        return 0.0
    return sum(sorted(edges, reverse=True)[k - 1 :])


def minimum_spanning_forest(mst_edges, k):
    # k open paths spanning n nodes form a spanning forest of k components, so the
    # MST minus its k-1 heaviest edges lower-bounds their total travel.
    return without_heaviest_edges(mst_edges, k)


def tsp_path_order(matrix, time_limit_sec):
    # Open TSP path over the symmetrized matrix: one vehicle, dummy depot at index 0
    # with zero cost to and from every node, so entering and leaving are free and the
    # tour degenerates into an open path.
    symmetric = symmetrized(matrix)
    n = symmetric.shape[0]
    if n <= 1:
        return list(range(n))

    open_matrix = np.zeros((n + 1, n + 1))
    open_matrix[1:, 1:] = symmetric

    manager = pywrapcp.RoutingIndexManager(n + 1, 1, 0)
    routing = pywrapcp.RoutingModel(manager)

    def arc_cost(from_index, to_index):
        from_node = manager.IndexToNode(from_index)
        to_node = manager.IndexToNode(to_index)
        return int(open_matrix[from_node][to_node] * TSP_COST_SCALE)

    routing.SetArcCostEvaluatorOfAllVehicles(routing.RegisterTransitCallback(arc_cost))

    search_params = pywrapcp.DefaultRoutingSearchParameters()
    search_params.first_solution_strategy = (
        routing_enums_pb2.FirstSolutionStrategy.PATH_CHEAPEST_ARC
    )
    search_params.local_search_metaheuristic = (
        routing_enums_pb2.LocalSearchMetaheuristic.GUIDED_LOCAL_SEARCH
    )
    search_params.time_limit.FromSeconds(time_limit_sec)

    solution = routing.SolveWithParameters(search_params)
    if solution is None:
        raise ValueError(f"open TSP path over {n} nodes has no solution")

    order = []
    index = routing.Start(0)
    while not routing.IsEnd(index):
        node = manager.IndexToNode(index) - 1
        if node >= 0:
            order.append(node)
        index = solution.Value(routing.NextVar(index))
    return order


def path_edges(order, matrix):
    return [float(matrix[a][b]) for a, b in zip(order[:-1], order[1:], strict=True)]


def split_path(order, matrix, k):
    # Cutting the k-1 heaviest edges of an open path leaves k open paths that still
    # cover every node, so the split is a feasible set of routes rather than a bound.
    gaps = path_edges(order, symmetrized(matrix))
    cuts = sorted(
        sorted(range(len(gaps)), key=lambda i: gaps[i], reverse=True)[: k - 1]
    )
    segments = []
    start = 0
    for cut in cuts:
        segments.append(order[start : cut + 1])
        start = cut + 1
    segments.append(order[start:])
    return segments


def path_travel(segment, matrix):
    return sum(path_edges(segment, matrix))


def directed_path_travel(segment, matrix):
    # A crew can walk a route either way round, so the achievable directed cost of a
    # segment is the cheaper of its two traversals.
    return min(path_travel(segment, matrix), path_travel(segment[::-1], matrix))
