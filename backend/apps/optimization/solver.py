import math
import random
import time
from dataclasses import dataclass

import numpy as np
from apps.optimization.n_estimator import (
    mean_nearest_neighbor_travel,
    p95_nearest_neighbor_travel,
)
from apps.optimization.profiling import PhaseTimer
from apps.optimization.route_metrics import haversine
from ortools.constraint_solver import pywrapcp, routing_enums_pb2

try:
    from line_profiler import profile  # type: ignore[import-untyped]
except ImportError:

    def profile(f):  # type: ignore[misc]
        return f


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
FEASIBLE_FLOOR_PREFIX = "feasible-floor-b"
STOPS_FLOOR_SUFFIX = "-stops"
BALANCE_ARM_FEASIBLE_FLOOR_B050 = f"{FEASIBLE_FLOOR_PREFIX}050"
BALANCE_ARM_FEASIBLE_FLOOR_B060 = f"{FEASIBLE_FLOOR_PREFIX}060"
BALANCE_ARM_FEASIBLE_FLOOR_B070 = f"{FEASIBLE_FLOOR_PREFIX}070"
BALANCE_ARM_FEASIBLE_FLOOR_B085 = f"{FEASIBLE_FLOOR_PREFIX}085"
BALANCE_ARM_FEASIBLE_FLOOR_B090 = f"{FEASIBLE_FLOOR_PREFIX}090"
BALANCE_ARM_FEASIBLE_FLOOR_B095 = f"{FEASIBLE_FLOOR_PREFIX}095"
BALANCE_ARM_NO_FLOOR = "no-floor"
NO_FLOOR_STOPS_PREFIX = f"no-floor{STOPS_FLOOR_SUFFIX}"
NO_FLOOR_LOWFLOOR_PREFIX = "no-floor-lowfloor"
BALANCE_ARM_NO_FLOOR_STOPS5 = f"{NO_FLOOR_STOPS_PREFIX}5"
BALANCE_ARM_NO_FLOOR_STOPS10 = f"{NO_FLOOR_STOPS_PREFIX}10"
BALANCE_ARM_NO_FLOOR_STOPS15 = f"{NO_FLOOR_STOPS_PREFIX}15"
BALANCE_ARM_NO_FLOOR_LOWFLOOR3600 = f"{NO_FLOOR_LOWFLOOR_PREFIX}3600"
BALANCE_ARM_NO_FLOOR_LOWFLOOR5400 = f"{NO_FLOOR_LOWFLOOR_PREFIX}5400"
# Combined floor: the scaled duration floor is what buys balance, the stop-count
# floor is what forbids stubs without buying padding. They were mutually exclusive
# until now because each was keyed off the arm name prefix alone.
BALANCE_ARM_COMBINED_B060_STOPS10 = (
    f"{BALANCE_ARM_FEASIBLE_FLOOR_B060}{STOPS_FLOOR_SUFFIX}10"
)
BALANCE_ARM_COMBINED_B070_STOPS10 = (
    f"{BALANCE_ARM_FEASIBLE_FLOOR_B070}{STOPS_FLOOR_SUFFIX}10"
)
BALANCE_ARM_COMBINED_B085_STOPS10 = (
    f"{BALANCE_ARM_FEASIBLE_FLOOR_B085}{STOPS_FLOOR_SUFFIX}10"
)
BALANCE_ARMS = (
    BALANCE_ARM_ACTUAL,
    BALANCE_ARM_UPPER_TMAX_TMIN9000,
    BALANCE_ARM_TMIN_SCALED,
    BALANCE_ARM_SERVICE_FLOOR,
    BALANCE_ARM_TMIN_SCALED_EXEMPT_LAST,
    BALANCE_ARM_FEASIBLE_FLOOR_B050,
    BALANCE_ARM_FEASIBLE_FLOOR_B060,
    BALANCE_ARM_FEASIBLE_FLOOR_B070,
    BALANCE_ARM_FEASIBLE_FLOOR_B085,
    BALANCE_ARM_FEASIBLE_FLOOR_B090,
    BALANCE_ARM_FEASIBLE_FLOOR_B095,
    BALANCE_ARM_NO_FLOOR,
    BALANCE_ARM_NO_FLOOR_STOPS5,
    BALANCE_ARM_NO_FLOOR_STOPS10,
    BALANCE_ARM_NO_FLOOR_STOPS15,
    BALANCE_ARM_NO_FLOOR_LOWFLOOR3600,
    BALANCE_ARM_NO_FLOOR_LOWFLOOR5400,
    BALANCE_ARM_COMBINED_B060_STOPS10,
    BALANCE_ARM_COMBINED_B070_STOPS10,
    BALANCE_ARM_COMBINED_B085_STOPS10,
)

# Charged per MISSING STOP, unlike SOFT_LOWER_PENALTY which is charged per second of
# duration deficit — the same magnitude means a far larger cost here. It is still a
# price, not a hard bound: a costly enough spatial span term can outbid it.
STOPS_FLOOR_PENALTY = 10_000

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

    def min_stops(self):
        # Minimum stops per route, or None when the arm sets no stop floor. Walking
        # in circles cannot inflate a stop count, so this floor forbids stub routes
        # without creating any incentive to pad duration.
        base, _, stops = self.balance_arm.rpartition(STOPS_FLOOR_SUFFIX)
        if not base:
            return None
        return int(stops)

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
        elif arm == BALANCE_ARM_NO_FLOOR or arm.startswith(NO_FLOOR_STOPS_PREFIX):
            # No soft bounds on either side: without a floor the solver has no
            # incentive to walk in circles to reach T_min. The upper is pinned at
            # T_max, which the Time dimension already enforces as a hard capacity, so
            # it can never be violated and costs nothing. Route balance, if wanted,
            # comes from a Time global span cost instead of from the floor.
            # The stops arms share these bounds: their floor is a minimum number of
            # visited nodes on the Stops dimension, not a duration, so the Time
            # dimension stays free of any floor.
            lower = None
            upper = (max_route_time_sec, self.soft_upper_penalty)
        elif arm.startswith(NO_FLOOR_LOWFLOOR_PREFIX):
            # Absolute low time floor instead of T_min: still paddable, but shallow
            # enough that padding to reach it should be cheap.
            floor = int(arm[len(NO_FLOOR_LOWFLOOR_PREFIX) :])
            lower = (floor, self.soft_lower_penalty)
            upper = (max_route_time_sec, self.soft_upper_penalty)
        elif arm.startswith(FEASIBLE_FLOOR_PREFIX):
            # min_route_time_sec is already T_min_eff (pre-computed by the solver).
            lower = (min_route_time_sec, self.soft_lower_penalty)
            upper = (max_route_time_sec, self.soft_upper_penalty)
        else:
            floor = min(min_route_time_sec, total_service_sec // max_vehicles)
            exempt = arm == BALANCE_ARM_TMIN_SCALED_EXEMPT_LAST and is_last
            lower = None if exempt else (floor, self.soft_lower_penalty)
            upper = ((floor + max_route_time_sec) // 2, self.soft_upper_penalty)
        return lower, upper


DEFAULT_PENALTIES = PenaltyConfig()


def node_permutation(node_count, seed):
    order = list(range(node_count))
    if seed:
        random.Random(seed).shuffle(order)
    return order


@profile
def build_open_matrix(matrix):
    real = np.asarray(matrix, dtype=float)
    n = real.shape[0] + 1
    open_matrix = np.zeros((n, n))
    open_matrix[1:, 1:] = real
    return open_matrix


@profile
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
        time_global_span_coef=0,
        penalties=DEFAULT_PENALTIES,
        convex_arc_lambda=0.0,
        node_seed=0,
    ):
        real = np.asarray(matrix, dtype=float)
        # OR-Tools exposes no RNG seed on either parameter proto, so replication is
        # obtained by permuting the node order: it changes PATH_CHEAPEST_ARC tie
        # breaking and the GLS trajectory. seed 0 is the identity permutation, so
        # production behaviour is untouched.
        self.node_permutation = node_permutation(real.shape[0], node_seed)
        if node_seed:
            real = real[np.ix_(self.node_permutation, self.node_permutation)]
            if spatial_points is not None:
                spatial_points = [spatial_points[i] for i in self.node_permutation]
        self.matrix = build_open_matrix(real)
        self.node_count = self.matrix.shape[0] - 1
        self.min_route_time_sec = min_route_time_sec
        self.max_route_time_sec = max_route_time_sec
        self.service_time_sec = service_time_sec
        self.max_vehicles = max_vehicles
        self.time_limit_sec = time_limit_sec
        self.spatial_points = spatial_points
        self.span_coef = span_coef
        self.time_span_coef = time_span_coef
        self.time_global_span_coef = time_global_span_coef
        self.penalties = penalties
        self.convex_arc_lambda = convex_arc_lambda

    @profile
    def solve(self, timer=None):
        result = self._solve_core(timer)
        if result is None:
            return None
        routes, dropped, _ = result
        return routes, dropped

    def solve_and_debug(self, timer=None):
        """Same as solve() but also returns an objective decomposition dict."""
        return self._solve_core(timer)

    def _solve_core(self, timer):
        timer = timer or PhaseTimer()
        n = self.node_count + 1
        effective_tmin = self._compute_effective_tmin()

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

            time_cb_index = routing.RegisterTransitCallback(time_callback)

            # Arc cost evaluator: convex variant when lambda > 0, else same as time.
            if self.convex_arc_lambda > 0:
                lam = self.convex_arc_lambda
                tau = self._p95_arc_travel()

                def convex_cost_callback(from_index, to_index):
                    from_node = manager.IndexToNode(from_index)
                    to_node = manager.IndexToNode(to_index)
                    travel = self.matrix[from_node][to_node]
                    convex = lam * max(0.0, travel - tau) ** 2 / tau if tau > 0 else 0.0
                    return math.ceil(travel + convex)

                arc_cb_index = routing.RegisterTransitCallback(convex_cost_callback)
            else:
                arc_cb_index = time_cb_index

            routing.SetArcCostEvaluatorOfAllVehicles(arc_cb_index)

            routing.AddDimension(
                time_cb_index,
                0,
                self.max_route_time_sec,
                True,
                "Time",
            )
            time_dimension = routing.GetDimensionOrDie("Time")

            if self.spatial_points is not None:
                with timer.phase("model_build", "geo_matrix"):
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

            if self.time_global_span_coef:
                # Penalizes the LARGEST route duration (max end cumul), not the sum of
                # spans, so it nudges routes toward equal duration without a floor.
                time_dimension.SetGlobalSpanCostCoefficient(self.time_global_span_coef)

            min_stops = self.penalties.min_stops()
            stops_dimension = None
            if min_stops is not None:

                def stops_callback(from_index, _to_index):
                    from_node = manager.IndexToNode(from_index)
                    return 1 if from_node != 0 else 0

                stops_cb_index = routing.RegisterTransitCallback(stops_callback)
                routing.AddDimension(
                    stops_cb_index,
                    0,
                    self.node_count,
                    True,
                    "Stops",
                )
                stops_dimension = routing.GetDimensionOrDie("Stops")

            routing.SetFixedCostOfAllVehicles(FIXED_VEHICLE_COST)

            with timer.phase("model_build", "disjunctions"):
                for node in range(1, n):
                    routing.AddDisjunction([manager.NodeToIndex(node)], DROP_PENALTY)

            total_service_sec = self.node_count * self.service_time_sec
            with timer.phase("model_build", "vehicle_bounds"):
                for vehicle_id in range(self.max_vehicles):
                    end_index = routing.End(vehicle_id)
                    lower, upper = self.penalties.vehicle_bounds(
                        min_route_time_sec=effective_tmin,
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
                    if stops_dimension is not None:
                        stops_dimension.SetCumulVarSoftLowerBound(
                            end_index, min_stops, STOPS_FLOOR_PENALTY
                        )

            with timer.phase("model_build", "search_params"):
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
            result = self._extract_solution(manager, routing, solution)

        routes, dropped = result
        time_end_cumuls = [
            solution.Value(time_dimension.CumulVar(routing.End(v)))
            for v in range(self.max_vehicles)
        ]
        dist_end_cumuls = None
        if self.spatial_points is not None:
            dist_dim = routing.GetDimensionOrDie("Distance")
            dist_end_cumuls = [
                solution.Value(dist_dim.CumulVar(routing.End(v)))
                for v in range(self.max_vehicles)
            ]
        stops_end_cumuls = None
        if stops_dimension is not None:
            stops_end_cumuls = [
                solution.Value(stops_dimension.CumulVar(routing.End(v)))
                for v in range(self.max_vehicles)
            ]
        debug = {
            "objective_ortools": solution.ObjectiveValue(),
            "stops_end_cumuls": stops_end_cumuls,
            "time_end_cumuls": time_end_cumuls,
            "dist_end_cumuls": dist_end_cumuls,
            "max_vehicles": self.max_vehicles,
            "k_active": len(routes),
            "dropped_count": len(dropped),
            "effective_tmin": effective_tmin,
            "span_coef": self.span_coef,
            "convex_arc_lambda": self.convex_arc_lambda,
        }
        return routes, dropped, debug

    def _compute_effective_tmin(self):
        arm = self.penalties.balance_arm
        if not arm.startswith(FEASIBLE_FLOOR_PREFIX):
            return self.min_route_time_sec
        beta = int(arm[len(FEASIBLE_FLOOR_PREFIX) :].split("-")[0]) / 100
        total_service = self.node_count * self.service_time_sec
        nn = mean_nearest_neighbor_travel(self.matrix)
        total_work = total_service + self.node_count * nn
        k_est = max(
            1, min(math.ceil(total_work / self.min_route_time_sec), self.node_count)
        )
        return int(min(self.min_route_time_sec, beta * total_work / k_est))

    def _p95_arc_travel(self):
        return p95_nearest_neighbor_travel(self.matrix)

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
        routes, dropped = extract_or_tools_routes(
            manager, routing, solution, self.max_vehicles
        )
        perm = self.node_permutation
        return (
            [[perm[node] for node in route] for route in routes],
            [perm[node] for node in dropped],
        )


@profile
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
