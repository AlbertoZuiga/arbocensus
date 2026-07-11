import time

import numpy as np
from apps.optimization.profiling import PhaseTimer
from apps.optimization.route_metrics import haversine
from ortools.constraint_solver import pywrapcp, routing_enums_pb2

FIXED_VEHICLE_COST = 100_000
SOFT_LOWER_PENALTY = 10_000
SOFT_UPPER_PENALTY = 500
DROP_PENALTY = 10 * FIXED_VEHICLE_COST


def build_open_matrix(matrix):
    real = np.asarray(matrix, dtype=float)
    n = real.shape[0] + 1
    open_matrix = np.zeros((n, n))
    open_matrix[1:, 1:] = real
    return open_matrix


def build_open_geo_matrix(points):
    n = len(points) + 1
    geo = np.zeros((n, n))
    for i, a in enumerate(points):
        for j, b in enumerate(points):
            if i != j:
                geo[i + 1][j + 1] = haversine(a, b)
    return geo


class ArbocensusVRPSolver:
    def __init__(
        self,
        matrix,
        *,
        min_route_time_sec,
        max_route_time_sec,
        service_time_sec,
        max_vehicles,
        time_limit_sec=180,
        spatial_points=None,
        span_coef=0,
    ):
        self.matrix = build_open_matrix(matrix)
        self.node_count = self.matrix.shape[0] - 1
        self.min_route_time_sec = min_route_time_sec
        self.max_route_time_sec = max_route_time_sec
        self.service_time_sec = service_time_sec
        self.max_vehicles = max_vehicles
        self.time_limit_sec = time_limit_sec
        self.spatial_points = spatial_points
        self.span_coef = span_coef

    def solve(self, timer=None):
        timer = timer or PhaseTimer()
        n = self.node_count + 1

        with timer.phase("model_build"):
            manager = pywrapcp.RoutingIndexManager(n, self.max_vehicles, 0)
            routing = pywrapcp.RoutingModel(manager)

            def time_callback(from_index, to_index):
                from_node = manager.IndexToNode(from_index)
                to_node = manager.IndexToNode(to_index)
                travel = self.matrix[from_node][to_node]
                service = self.service_time_sec if from_node != 0 else 0
                return int(travel + service)

            callback_index = routing.RegisterTransitCallback(time_callback)
            routing.SetArcCostEvaluatorOfAllVehicles(callback_index)

            routing.AddDimension(
                callback_index,
                0,
                self.max_route_time_sec,
                True,
                "Time",
            )
            time_dimension = routing.GetDimensionOrDie("Time")

            if self.spatial_points is not None:
                geo_matrix = build_open_geo_matrix(self.spatial_points)

                def distance_callback(from_index, to_index):
                    from_node = manager.IndexToNode(from_index)
                    to_node = manager.IndexToNode(to_index)
                    return int(geo_matrix[from_node][to_node])

                distance_cb = routing.RegisterTransitCallback(distance_callback)
                routing.AddDimension(distance_cb, 0, 10_000_000, True, "Distance")
                distance_dimension = routing.GetDimensionOrDie("Distance")
                distance_dimension.SetSpanCostCoefficientForAllVehicles(self.span_coef)

            routing.SetFixedCostOfAllVehicles(FIXED_VEHICLE_COST)

            for node in range(1, n):
                routing.AddDisjunction([manager.NodeToIndex(node)], DROP_PENALTY)

            midpoint = (self.min_route_time_sec + self.max_route_time_sec) // 2
            for vehicle_id in range(self.max_vehicles):
                end_index = routing.End(vehicle_id)
                time_dimension.SetCumulVarSoftLowerBound(
                    end_index, self.min_route_time_sec, SOFT_LOWER_PENALTY
                )
                time_dimension.SetCumulVarSoftUpperBound(
                    end_index, midpoint, SOFT_UPPER_PENALTY
                )

            search_params = pywrapcp.DefaultRoutingSearchParameters()
            search_params.first_solution_strategy = (
                routing_enums_pb2.FirstSolutionStrategy.PATH_CHEAPEST_ARC
            )
            search_params.local_search_metaheuristic = (
                routing_enums_pb2.LocalSearchMetaheuristic.GUIDED_LOCAL_SEARCH
            )
            search_params.time_limit.FromSeconds(self.time_limit_sec)

        solution = self._solve_with_timing(routing, search_params, timer)
        if solution is None:
            return None

        with timer.phase("solution_extraction"):
            return self._extract_solution(manager, routing, solution)

    def _solve_with_timing(self, routing, search_params, timer):
        first_solution_elapsed = None
        solve_start = time.perf_counter()

        def on_solution():
            nonlocal first_solution_elapsed
            if first_solution_elapsed is None:
                first_solution_elapsed = time.perf_counter() - solve_start

        routing.AddAtSolutionCallback(on_solution)
        solution = routing.SolveWithParameters(search_params)
        solve_elapsed = time.perf_counter() - solve_start

        if first_solution_elapsed is None:
            first_solution_elapsed = 0.0
        timer.record("solve", solve_elapsed, "total")
        timer.record("solve", first_solution_elapsed, "first_solution")
        timer.record(
            "solve", max(0.0, solve_elapsed - first_solution_elapsed), "metaheuristic"
        )
        return solution

    def _extract_solution(self, manager, routing, solution):
        return extract_or_tools_routes(manager, routing, solution, self.max_vehicles)


def extract_or_tools_routes(manager, routing, solution, max_vehicles):
    routes = []
    for vehicle_id in range(max_vehicles):
        index = routing.Start(vehicle_id)
        route = []
        while not routing.IsEnd(index):
            node = manager.IndexToNode(index) - 1
            if node >= 0:
                route.append(node)
            index = solution.Value(routing.NextVar(index))
        if route:
            routes.append(route)

    dropped = []
    for index in range(routing.Size()):
        if routing.IsStart(index) or routing.IsEnd(index):
            continue
        if solution.Value(routing.NextVar(index)) == index:
            dropped.append(manager.IndexToNode(index) - 1)
    return routes, dropped
