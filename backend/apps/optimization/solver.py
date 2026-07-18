import math
import time
from dataclasses import dataclass

import numpy as np
from apps.optimization.profiling import PhaseTimer
from apps.optimization.route_metrics import haversine
from ortools.constraint_solver import pywrapcp, routing_enums_pb2

FIXED_VEHICLE_COST = 100_000
SOFT_LOWER_PENALTY = 10_000
SOFT_UPPER_PENALTY = 500
DROP_PENALTY = 10 * FIXED_VEHICLE_COST

SOFT_UPPER_TARGET_MIDPOINT = "midpoint"
SOFT_UPPER_TARGET_TMAX = "tmax"
SOFT_UPPER_TARGETS = (SOFT_UPPER_TARGET_MIDPOINT, SOFT_UPPER_TARGET_TMAX)

BALANCE_ARM_ACTUAL = "actual"
BALANCE_ARM_UPPER_TMAX_TMIN9000 = "upper-tmax-tmin9000"
BALANCE_ARM_TMIN_SCALED = "tmin-scaled"
BALANCE_ARM_SERVICE_FLOOR = "service-floor"
BALANCE_ARM_TMIN_SCALED_EXEMPT_LAST = "tmin-scaled+exempt-last"
BALANCE_ARMS = (
    BALANCE_ARM_ACTUAL,
    BALANCE_ARM_UPPER_TMAX_TMIN9000,
    BALANCE_ARM_TMIN_SCALED,
    BALANCE_ARM_SERVICE_FLOOR,
    BALANCE_ARM_TMIN_SCALED_EXEMPT_LAST,
)

# The `upper-tmax-tmin9000` arm anchors the soft lower bound just under the census
# floor (T_min≈9000s) so routes are still discouraged from staying tiny, while the
# upper target rides at T_max to pull duration up and unwind spatial crossings.
TIGHT_TMIN_SEC = 9000


@dataclass(frozen=True)
class PenaltyConfig:
    soft_lower_penalty: int = SOFT_LOWER_PENALTY
    soft_upper_penalty: int = SOFT_UPPER_PENALTY
    soft_upper_target: str = SOFT_UPPER_TARGET_MIDPOINT
    balance_arm: str = BALANCE_ARM_ACTUAL

    def __post_init__(self):
        if self.soft_upper_target not in SOFT_UPPER_TARGETS:
            raise ValueError(
                f"soft_upper_target must be one of {SOFT_UPPER_TARGETS}, "
                f"got '{self.soft_upper_target}'"
            )
        if self.balance_arm not in BALANCE_ARMS:
            raise ValueError(
                f"balance_arm must be one of {BALANCE_ARMS}, got '{self.balance_arm}'"
            )

    def soft_upper_bound(self, min_route_time_sec, max_route_time_sec):
        if self.soft_upper_target == SOFT_UPPER_TARGET_TMAX:
            return max_route_time_sec
        return (min_route_time_sec + max_route_time_sec) // 2

    def vehicle_bounds(
        self,
        *,
        min_route_time_sec,
        max_route_time_sec,
        total_service_sec,
        max_vehicles,
        is_last,
    ):
        # Returns (lower, upper) where each is either (target_sec, penalty) applied to
        # the route end cumul, or None to leave that side of the balance band open.
        arm = self.balance_arm
        if arm == BALANCE_ARM_ACTUAL:
            lower = (min_route_time_sec, self.soft_lower_penalty)
            upper = (
                self.soft_upper_bound(min_route_time_sec, max_route_time_sec),
                self.soft_upper_penalty,
            )
        elif arm == BALANCE_ARM_UPPER_TMAX_TMIN9000:
            lower = (TIGHT_TMIN_SEC, self.soft_lower_penalty)
            upper = (max_route_time_sec, self.soft_upper_penalty)
        elif arm == BALANCE_ARM_SERVICE_FLOOR:
            lower = None
            upper = (
                self.soft_upper_bound(min_route_time_sec, max_route_time_sec),
                self.soft_upper_penalty,
            )
        else:
            floor = min(min_route_time_sec, total_service_sec // max_vehicles)
            exempt = arm == BALANCE_ARM_TMIN_SCALED_EXEMPT_LAST and is_last
            lower = None if exempt else (floor, self.soft_lower_penalty)
            upper = ((floor + max_route_time_sec) // 2, self.soft_upper_penalty)
        return lower, upper


DEFAULT_PENALTIES = PenaltyConfig()


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
        time_limit_sec,
        spatial_points=None,
        span_coef=0,
        time_span_coef=0,
        penalties=DEFAULT_PENALTIES,
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
        self.time_span_coef = time_span_coef
        self.penalties = penalties

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
                # Ceil, not truncate: the Time dimension must never underestimate the
                # real float route time, or routes within T_max exceed it in metrics.
                return math.ceil(travel + service)

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

            if self.time_span_coef:
                time_dimension.SetSpanCostCoefficientForAllVehicles(self.time_span_coef)

            routing.SetFixedCostOfAllVehicles(FIXED_VEHICLE_COST)

            for node in range(1, n):
                routing.AddDisjunction([manager.NodeToIndex(node)], DROP_PENALTY)

            total_service_sec = self.node_count * self.service_time_sec
            for vehicle_id in range(self.max_vehicles):
                end_index = routing.End(vehicle_id)
                lower, upper = self.penalties.vehicle_bounds(
                    min_route_time_sec=self.min_route_time_sec,
                    max_route_time_sec=self.max_route_time_sec,
                    total_service_sec=total_service_sec,
                    max_vehicles=self.max_vehicles,
                    is_last=vehicle_id == self.max_vehicles - 1,
                )
                if lower is not None:
                    time_dimension.SetCumulVarSoftLowerBound(
                        end_index, lower[0], lower[1]
                    )
                if upper is not None:
                    time_dimension.SetCumulVarSoftUpperBound(
                        end_index, upper[0], upper[1]
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
