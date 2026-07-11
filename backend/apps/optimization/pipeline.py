from apps.datasets.models import Tree
from apps.optimization.cost_matrix import OSRMCostMatrixBuilder
from apps.optimization.models import RoutingConfig, RoutingSolution
from apps.optimization.n_estimator import estimate_max_vehicles
from apps.optimization.profiling import PhaseTimer, merge_timing
from apps.optimization.route_metrics import aggregate_metrics, routes_from_points
from apps.optimization.solver import build_open_matrix
from apps.optimization.strategies import solve_by_strategy
from apps.routes.models import Route, RouteStop
from django.db import transaction

SOLVER_TIME_LIMIT_SEC = 180


def estimate_fleet_from_cache(
    dataset,
    min_route_time_sec=RoutingConfig.DEFAULT_MIN_ROUTE_TIME_SEC,
    service_time_sec=RoutingConfig.DEFAULT_SERVICE_TIME_SEC,
):
    trees = sorted(
        Tree.objects.filter(dataset=dataset, is_active=True),
        key=lambda tree: tree.id,
    )
    if len(trees) < 2:
        return None

    matrix = OSRMCostMatrixBuilder().get_cached(trees)
    if matrix is None:
        return None

    total_service = len(trees) * service_time_sec
    return estimate_max_vehicles(
        build_open_matrix(matrix),
        total_service,
        min_route_time_sec,
        buffer=0,
    )


class OptimizationPipeline:
    def __init__(self, job):
        self.job = job
        self.config = job.config

    def run(self, strategy=None):
        trees = sorted(
            Tree.objects.filter(dataset=self.config.dataset, is_active=True),
            key=lambda tree: tree.id,
        )
        if len(trees) < 2:
            raise ValueError("Dataset needs at least 2 active trees to optimize")

        time_limit_sec = min(int(30 + 1.5 * len(trees)), SOLVER_TIME_LIMIT_SEC)

        cost_matrix_timer = PhaseTimer()
        matrix = OSRMCostMatrixBuilder().build(trees, timer=cost_matrix_timer)
        cost_matrix_timer.record(
            "cost_matrix",
            sum(cost_matrix_timer.as_dict()["cost_matrix"].values()),
            "total",
        )
        cost_matrix_timing = cost_matrix_timer.as_dict()
        total_service = len(trees) * self.config.service_time_sec
        max_vehicles = estimate_max_vehicles(
            build_open_matrix(matrix),
            total_service,
            self.config.min_route_time_sec,
        )
        points = [(tree.location.y, tree.location.x) for tree in trees]

        strategies_to_run = (
            [RoutingSolution.Strategy(strategy)]
            if strategy
            else list(RoutingSolution.Strategy)
        )

        solved = {}
        timers = {}
        dropped_nodes = set()
        for s in strategies_to_run:
            timer = PhaseTimer()
            result = solve_by_strategy(
                s.value,
                matrix,
                points=points,
                min_route_time_sec=self.config.min_route_time_sec,
                max_route_time_sec=self.config.max_route_time_sec,
                service_time_sec=self.config.service_time_sec,
                max_vehicles=max_vehicles,
                time_limit_sec=time_limit_sec,
                timer=timer,
            )
            if result is None:
                raise ValueError(
                    f"No feasible solution for strategy '{s.value}': the solver could "
                    f"not build any route for {len(trees)} trees under the current "
                    f"routing config (service {self.config.service_time_sec}s, "
                    f"max_route_time {self.config.max_route_time_sec}s)."
                )
            routes, dropped = result
            solved[s.value] = routes
            timers[s.value] = timer
            dropped_nodes.update(dropped)

        results = {}
        with transaction.atomic():
            for s_value, routes in solved.items():
                results[s_value] = self._persist_solution(
                    trees,
                    matrix,
                    routes,
                    max_vehicles,
                    s_value,
                    cost_matrix_timing,
                    timers[s_value],
                )

        return {
            "solutions": results,
            "dropped_trees": sorted(str(trees[n].id) for n in dropped_nodes),
        }

    def _persist_solution(
        self,
        trees,
        matrix,
        routes,
        max_vehicles_estimated,
        strategy,
        cost_matrix_timing,
        timer,
    ):
        route_times = [self._travel_time(matrix, route) for route in routes]
        estimated_times = [
            travel + len(route) * self.config.service_time_sec
            for travel, route in zip(route_times, routes, strict=True)
        ]

        with timer.phase("metrics"):
            spatial = aggregate_metrics(routes_from_points(routes, trees))

        timing = merge_timing(cost_matrix_timing, timer.as_dict())

        solution = RoutingSolution.objects.create(
            job=self.job,
            strategy=strategy,
            total_routes=len(routes),
            total_travel_time_sec=sum(route_times),
            balance_score=self._balance_score(estimated_times),
            sum_max_radius_m=spatial["sum_max_radius_m"],
            interleave_total=spatial["interleave_total"],
            interleave_per_route=spatial["interleave_per_route"],
            worst_pair_iou=spatial["worst_pair_iou"],
            timing=timing,
        )

        stops = []
        for route_number, (route, travel, estimated) in enumerate(
            zip(routes, route_times, estimated_times, strict=True), start=1
        ):
            route_obj = Route.objects.create(
                solution=solution,
                route_number=route_number,
                total_trees=len(route),
                travel_time_sec=int(travel),
                total_estimated_time_sec=int(estimated),
            )
            for sequence, node in enumerate(route, start=1):
                stops.append(
                    RouteStop(route=route_obj, tree=trees[node], sequence=sequence)
                )
        RouteStop.objects.bulk_create(stops, batch_size=500)

        return {
            "solution_id": str(solution.id),
            "total_routes": solution.total_routes,
            "total_travel_time_sec": solution.total_travel_time_sec,
            "balance_score": solution.balance_score,
            "max_vehicles_estimated": max_vehicles_estimated,
            **spatial,
        }

    def _travel_time(self, matrix, route):
        return sum(matrix[a][b] for a, b in zip(route[:-1], route[1:], strict=True))

    def _balance_score(self, estimated_times):
        if len(estimated_times) <= 1:
            return 1.0
        longest = max(estimated_times)
        if longest == 0:
            return 1.0
        return min(estimated_times) / longest
