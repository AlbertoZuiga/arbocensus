from apps.datasets.models import Tree
from apps.optimization.cost_matrix import OSRMCostMatrixBuilder
from apps.optimization.models import RoutingSolution
from apps.optimization.n_estimator import estimate_max_vehicles
from apps.optimization.solver import ArbocensusVRPSolver, build_open_matrix
from apps.routes.models import Route, RouteStop

SOLVER_TIME_LIMIT_SEC = 180


class OptimizationPipeline:
    def __init__(self, job):
        self.job = job
        self.config = job.config

    def run(self):
        trees = sorted(
            Tree.objects.filter(dataset=self.config.dataset, is_active=True),
            key=lambda tree: tree.id,
        )
        if len(trees) < 2:
            raise ValueError("Dataset needs at least 2 active trees to optimize")

        matrix = OSRMCostMatrixBuilder().build(trees)
        total_service = len(trees) * self.config.service_time_sec
        max_vehicles = estimate_max_vehicles(
            build_open_matrix(matrix),
            total_service,
            self.config.min_route_time_sec,
        )

        solver = ArbocensusVRPSolver(
            matrix,
            min_route_time_sec=self.config.min_route_time_sec,
            max_route_time_sec=self.config.max_route_time_sec,
            service_time_sec=self.config.service_time_sec,
            max_vehicles=max_vehicles,
            time_limit_sec=SOLVER_TIME_LIMIT_SEC,
        )
        routes = solver.solve()
        if routes is None:
            raise ValueError(
                f"No feasible solution: {len(trees)} trees × "
                f"{self.config.service_time_sec}s service exceeds "
                f"max_route_time {self.config.max_route_time_sec}s per route"
            )

        return self._persist_solution(trees, matrix, routes, max_vehicles)

    def _persist_solution(self, trees, matrix, routes, max_vehicles_estimated):
        route_times = [self._travel_time(matrix, route) for route in routes]
        estimated_times = [
            travel + len(route) * self.config.service_time_sec
            for travel, route in zip(route_times, routes, strict=True)
        ]

        solution = RoutingSolution.objects.create(
            job=self.job,
            total_routes=len(routes),
            total_travel_time_sec=sum(route_times),
            balance_score=self._balance_score(estimated_times),
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
