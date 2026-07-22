def _two_opt_open(seq, dist):
    n = len(seq)
    improved = True
    while improved:
        improved = False
        for i in range(n - 1):
            for j in range(i + 2, n):
                cost_before = dist(seq[i], seq[i + 1]) + (
                    dist(seq[j], seq[j + 1]) if j + 1 < n else 0.0
                )
                cost_after = dist(seq[i], seq[j]) + (
                    dist(seq[i + 1], seq[j + 1]) if j + 1 < n else 0.0
                )
                if cost_after < cost_before - 1e-9:
                    seq[i + 1 : j + 1] = seq[i + 1 : j + 1][::-1]
                    improved = True
    return seq


def resequence_route(route, matrix):
    """Open-path 2-opt on a single route. matrix is 0-indexed over all real nodes."""
    if len(route) < 3:
        return list(route)
    seq = list(route)
    _two_opt_open(seq, lambda a, b: matrix[a][b])
    return seq


def resequence_routes(routes, matrix):
    """Apply open-path 2-opt to every route independently."""
    return [resequence_route(route, matrix) for route in routes]


def route_travel(route, matrix):
    """Travel cost of a stop sequence under the same matrix 2-opt optimises."""
    return sum(matrix[a][b] for a, b in zip(route[:-1], route[1:], strict=True))


def two_opt_gap(route, matrix):
    """Fraction of a route's travel that an open-path 2-opt removes."""
    travel = route_travel(route, matrix)
    if travel <= 0:
        return 0.0
    improved = route_travel(resequence_route(route, matrix), matrix)
    return (travel - improved) / travel


def solution_two_opt_gap(routes, matrix):
    """Travel-weighted `two_opt_gap` over every route of a solution."""
    travel = sum(route_travel(route, matrix) for route in routes)
    if travel <= 0:
        return 0.0
    improved = sum(
        route_travel(route, matrix) for route in resequence_routes(routes, matrix)
    )
    return (travel - improved) / travel
