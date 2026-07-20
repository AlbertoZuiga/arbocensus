import numpy as np


def symmetric_mst_edges(matrix):
    # Symmetrize downward: a directed path can only cost more than the undirected
    # forest built on min(d_ij, d_ji), so any bound derived from it stays valid.
    real = np.asarray(matrix, dtype=float)
    symmetric = np.minimum(real, real.T)
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


def minimum_spanning_forest(mst_edges, k):
    # k open paths spanning n nodes form a spanning forest of k components, so the
    # MST minus its k-1 heaviest edges lower-bounds their total travel.
    if k < 1:
        return 0.0
    return sum(mst_edges[k - 1 :])
