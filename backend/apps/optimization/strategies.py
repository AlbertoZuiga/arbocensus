from apps.optimization.solver import ArbocensusVRPSolver


def solve_by_strategy(
    strategy,
    matrix,
    *,
    points,
    min_route_time_sec,
    max_route_time_sec,
    service_time_sec,
    max_vehicles,
    time_limit_sec,
):
    solver = ArbocensusVRPSolver(
        matrix,
        min_route_time_sec=min_route_time_sec,
        max_route_time_sec=max_route_time_sec,
        service_time_sec=service_time_sec,
        max_vehicles=max_vehicles,
        time_limit_sec=time_limit_sec,
    )
    return solver.solve()
