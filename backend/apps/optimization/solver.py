import numpy as np
from ortools.constraint_solver import pywrapcp, routing_enums_pb2

FIXED_VEHICLE_COST = 100_000
SOFT_LOWER_PENALTY = 10_000
SOFT_UPPER_PENALTY = 500


def build_open_matrix(matrix):
    real = np.asarray(matrix, dtype=float)
    n = real.shape[0] + 1
    open_matrix = np.zeros((n, n))
    open_matrix[1:, 1:] = real
    return open_matrix


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
    ):
        self.matrix = build_open_matrix(matrix)
        self.node_count = self.matrix.shape[0] - 1
        self.min_route_time_sec = min_route_time_sec
        self.max_route_time_sec = max_route_time_sec
        self.service_time_sec = service_time_sec
        self.max_vehicles = max_vehicles
        self.time_limit_sec = time_limit_sec

    def solve(self):
        n = self.node_count + 1
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

        routing.SetFixedCostOfAllVehicles(FIXED_VEHICLE_COST)

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

        solution = routing.SolveWithParameters(search_params)
        if solution is None:
            return None

        return self._extract_solution(manager, routing, solution)

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
    return routes
