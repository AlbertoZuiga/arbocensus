import csv
import time
from statistics import mean, pstdev

from apps.datasets.instances import dataset_uuid
from apps.datasets.models import Dataset, Tree
from apps.optimization.cost_matrix import OSRMCostMatrixBuilder
from apps.optimization.greedy import solve_greedy
from apps.optimization.models import OptimizationJob, RoutingConfig, RoutingSolution
from apps.optimization.n_estimator import mean_nearest_neighbor_travel
from apps.optimization.pipeline import OptimizationPipeline
from apps.optimization.route_audit import (
    audit_route,
    audit_solution,
    worst_overlap_pair,
)
from apps.optimization.route_metrics import aggregate_metrics, routes_from_points
from apps.optimization.solver import (
    BALANCE_ARM_ACTUAL,
    BALANCE_ARM_SERVICE_FLOOR,
    BALANCE_ARM_TMIN_SCALED,
    BALANCE_ARM_TMIN_SCALED_EXEMPT_LAST,
    BALANCE_ARM_UPPER_TMAX_TMIN9000,
    PenaltyConfig,
    build_open_matrix,
)
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

CENSUS_SERVICE_TIME_SEC = 120
CENSUS_MIN_ROUTE_TIME_SEC = 7200
CENSUS_MAX_ROUTE_TIME_SEC = 10800

INSTANCES = [
    "battery-n50",
    "battery-n100",
    "battery-n200",
    "battery-n400",
    "battery-n800",
    "battery-n1000",
    "battery-sparse-n250",
    "battery-sparse-n500",
    "area-26-n157",
    "area-27-n72",
    "area-29-n43",
    "reference-n1607",
]

SPATIAL = RoutingSolution.Strategy.SPATIAL_TERM.value
GLOBAL = RoutingSolution.Strategy.GLOBAL.value
GREEDY = "greedy"

# (label, strategy, balance_arm, span_coef). The config axis fixes the strategy at
# spatial_term and sweeps the duration soft-bound arms plus one Time-span cell; the
# algorithm axis fixes the arm at `actual` and sweeps the strategy.
CONFIG_AXIS = [
    ("actual", SPATIAL, BALANCE_ARM_ACTUAL, 0),
    ("upper-tmax-tmin9000", SPATIAL, BALANCE_ARM_UPPER_TMAX_TMIN9000, 0),
    ("tmin-scaled", SPATIAL, BALANCE_ARM_TMIN_SCALED, 0),
    ("service-floor", SPATIAL, BALANCE_ARM_SERVICE_FLOOR, 0),
    ("tmin-scaled+exempt-last", SPATIAL, BALANCE_ARM_TMIN_SCALED_EXEMPT_LAST, 0),
    ("span-c100", SPATIAL, BALANCE_ARM_ACTUAL, 100),
]
ALGO_AXIS = [
    ("global", GLOBAL, BALANCE_ARM_ACTUAL, 0),
    ("greedy", GREEDY, BALANCE_ARM_ACTUAL, 0),
]

SEEDS = [1, 2, 3]

COLUMNS = [
    "instance",
    "n",
    "axis",
    "cell",
    "strategy",
    "balance_arm",
    "span_coef",
    "seed",
    "k",
    "drops",
    "travel_sec",
    "balance",
    "sigma_t_sec",
    "crossings",
    "worst_iou",
    "interleave_per_route",
    "walk_ratio",
    "saturation_mean",
    "sat_estimated",
    "relleno_sec",
    "deficit_sec",
    "wall_clock_sec",
    "t_osrm_sec",
    "t_model_build_sec",
    "t_first_solution_sec",
    "t_metaheuristic_sec",
    "t_extraction_sec",
]


class _RollbackError(Exception):
    pass


class Command(BaseCommand):
    help = (
        "Config x algorithm x size sweep over the frozen real-instance suite. "
        "Reference census config: service 2 min, T_max 3 h. Appends one row per "
        "cell to a master CSV and is resumable: cells already present are skipped. "
        "OR-Tools cells run inside a rolled-back transaction so the shared database "
        "is not polluted with hundreds of throwaway solutions."
    )

    def add_arguments(self, parser):
        parser.add_argument("--csv", type=str, required=True)
        parser.add_argument(
            "--only-instance",
            type=str,
            default=None,
            help="Restrict the sweep to a single instance slug (smoke test)",
        )
        parser.add_argument(
            "--only-cell",
            type=str,
            default=None,
            help="Restrict the sweep to a single config/algo cell label",
        )
        parser.add_argument(
            "--seeds",
            type=int,
            nargs="+",
            default=SEEDS,
        )

    def handle(self, *args, **options):
        csv_path = settings.BASE_DIR.parent / options["csv"]
        csv_path.parent.mkdir(parents=True, exist_ok=True)
        done = self._existing_keys(csv_path)

        instances = INSTANCES
        if options["only_instance"]:
            if options["only_instance"] not in INSTANCES:
                raise CommandError(f"unknown instance '{options['only_instance']}'")
            instances = [options["only_instance"]]

        cells = [("config", *cell) for cell in CONFIG_AXIS]
        cells += [("algo", *cell) for cell in ALGO_AXIS]
        if options["only_cell"]:
            cells = [c for c in cells if c[1] == options["only_cell"]]
            if not cells:
                raise CommandError(f"unknown cell '{options['only_cell']}'")

        for slug in instances:
            trees, matrix = self._prepare_instance(slug)
            nn_travel = mean_nearest_neighbor_travel(build_open_matrix(matrix))
            for axis, cell, strategy, arm, span in cells:
                for seed in options["seeds"]:
                    key = (slug, cell, strategy, arm, str(span), str(seed))
                    if key in done:
                        self.stdout.write(f"skip {slug} {cell} seed={seed}")
                        continue
                    row = self._run_cell(
                        slug,
                        trees,
                        matrix,
                        nn_travel,
                        axis,
                        cell,
                        strategy,
                        arm,
                        span,
                        seed,
                    )
                    self._append(csv_path, row)
                    done.add(key)
                    self.stdout.write(
                        f"done {slug} {cell} seed={seed} "
                        f"k={row['k']} bal={row['balance']} "
                        f"cross={row['crossings']} wall={row['wall_clock_sec']}s"
                    )
        self.stdout.write(self.style.SUCCESS(f"Sweep CSV: {csv_path}"))

    def _existing_keys(self, csv_path):
        if not csv_path.exists():
            return set()
        with csv_path.open(newline="", encoding="utf-8") as handle:
            return {
                (
                    r["instance"],
                    r["cell"],
                    r["strategy"],
                    r["balance_arm"],
                    r["span_coef"],
                    r["seed"],
                )
                for r in csv.DictReader(handle)
            }

    def _prepare_instance(self, slug):
        try:
            dataset = Dataset.objects.get(id=dataset_uuid(slug))
        except Dataset.DoesNotExist as exc:
            raise CommandError(
                f"instance '{slug}' not loaded (run load_instances first)"
            ) from exc
        trees = sorted(
            Tree.objects.filter(dataset=dataset, is_active=True),
            key=lambda tree: tree.id,
        )
        matrix = OSRMCostMatrixBuilder().build(trees)
        return trees, matrix

    def _run_cell(
        self, slug, trees, matrix, nn_travel, axis, cell, strategy, arm, span, seed
    ):
        wall_start = time.perf_counter()
        if strategy == GREEDY:
            rows, worst_iou, interleave, timing = self._greedy_cell(trees, matrix)
        else:
            rows, worst_iou, interleave, timing = self._ortools_cell(
                trees, strategy, arm, span
            )
        wall = round(time.perf_counter() - wall_start, 2)
        return self._metrics_row(
            slug,
            len(trees),
            axis,
            cell,
            strategy,
            arm,
            span,
            seed,
            rows,
            worst_iou,
            interleave,
            timing,
            nn_travel,
            wall,
        )

    def _ortools_cell(self, trees, strategy, arm, span):
        penalties = PenaltyConfig(balance_arm=arm)
        dataset = trees[0].dataset
        rows = worst = interleave = timing = None
        try:
            with transaction.atomic():
                config = RoutingConfig.objects.create(
                    dataset=dataset,
                    service_time_sec=CENSUS_SERVICE_TIME_SEC,
                    min_route_time_sec=CENSUS_MIN_ROUTE_TIME_SEC,
                    max_route_time_sec=CENSUS_MAX_ROUTE_TIME_SEC,
                )
                job = OptimizationJob.objects.create(config=config, strategy=strategy)
                job.set_status("running")
                metrics = OptimizationPipeline(job).run(
                    strategy=strategy, penalties=penalties, time_span_coef=span
                )
                solution = RoutingSolution.objects.get(job=job, strategy=strategy)
                audited = audit_solution(
                    solution,
                    min_route_time_sec=CENSUS_MIN_ROUTE_TIME_SEC,
                    max_route_time_sec=CENSUS_MAX_ROUTE_TIME_SEC,
                )
                pair = worst_overlap_pair(audited)
                rows = [entry["row"] for entry in audited]
                for row in rows:
                    row["drops"] = len(metrics["dropped_trees"])
                worst = pair[2] if pair else 0.0
                interleave = solution.interleave_per_route
                timing = solution.timing
                raise _RollbackError
        except _RollbackError:
            pass
        return rows, worst, interleave, timing

    def _greedy_cell(self, trees, matrix):
        routes = solve_greedy(
            matrix,
            max_route_time_sec=CENSUS_MAX_ROUTE_TIME_SEC,
            service_time_sec=CENSUS_SERVICE_TIME_SEC,
        )
        rows = []
        for number, route in enumerate(routes, start=1):
            travel = sum(
                matrix[a][b] for a, b in zip(route[:-1], route[1:], strict=True)
            )
            duration = round(travel) + len(route) * CENSUS_SERVICE_TIME_SEC
            points = [
                (trees[node].location.y, trees[node].location.x) for node in route
            ]
            row = audit_route(
                number,
                points,
                duration,
                round(travel),
                min_route_time_sec=CENSUS_MIN_ROUTE_TIME_SEC,
                max_route_time_sec=CENSUS_MAX_ROUTE_TIME_SEC,
            )
            row["drops"] = 0
            rows.append(row)
        spatial = aggregate_metrics(routes_from_points(routes, trees))
        return rows, spatial["worst_pair_iou"], spatial["interleave_per_route"], None

    def _metrics_row(
        self,
        slug,
        n,
        axis,
        cell,
        strategy,
        arm,
        span,
        seed,
        rows,
        worst_iou,
        interleave,
        timing,
        nn_travel,
        wall,
    ):
        durations = [r["duration_sec"] for r in rows]
        travels = [r["travel_sec"] for r in rows]
        k = len(rows)
        travel_total = sum(travels)
        service_total = sum(r["service_total_sec"] for r in rows)
        balance = self._balance(durations, arm)
        deficit = sum(
            max(0, CENSUS_MIN_ROUTE_TIME_SEC - r["service_total_sec"]) for r in rows
        )
        # Minimal travel to visit n trees across k open routes is n-k edges; the
        # excess over that nearest-neighbour lower bound is padding (relleno).
        travel_min_est = max(0, n - k) * nn_travel
        relleno = max(0, round(travel_total - travel_min_est))
        sat_estimated = (
            round(service_total / (k * CENSUS_MAX_ROUTE_TIME_SEC), 3) if k else 0.0
        )
        phases = self._phase_times(timing)
        return {
            "instance": slug,
            "n": n,
            "axis": axis,
            "cell": cell,
            "strategy": strategy,
            "balance_arm": arm,
            "span_coef": span,
            "seed": seed,
            "k": k,
            "drops": rows[0]["drops"] if rows else 0,
            "travel_sec": round(travel_total),
            "balance": balance,
            "sigma_t_sec": round(pstdev(durations)) if k > 1 else 0,
            "crossings": sum(r["self_crossings"] for r in rows),
            "worst_iou": round(worst_iou, 3),
            "interleave_per_route": round(interleave, 3),
            "walk_ratio": (
                round(travel_total / sum(durations), 3) if sum(durations) else 0.0
            ),
            "saturation_mean": round(mean(r["saturation"] for r in rows), 3),
            "sat_estimated": sat_estimated,
            "relleno_sec": relleno,
            "deficit_sec": deficit,
            "wall_clock_sec": wall,
            **phases,
        }

    def _balance(self, durations, arm):
        if len(durations) <= 1:
            return 1.0
        if arm == BALANCE_ARM_TMIN_SCALED_EXEMPT_LAST:
            # The residual under-filled route is exempt from balance in this arm, so
            # it is excluded from both ends of the min/max ratio.
            trimmed = sorted(durations)[1:]
            durations = trimmed or durations
        return round(min(durations) / max(durations), 3)

    def _phase_times(self, timing):
        if not timing:
            return {
                "t_osrm_sec": 0.0,
                "t_model_build_sec": 0.0,
                "t_first_solution_sec": 0.0,
                "t_metaheuristic_sec": 0.0,
                "t_extraction_sec": 0.0,
            }
        return {
            "t_osrm_sec": round(timing.get("cost_matrix", {}).get("total", 0.0), 3),
            "t_model_build_sec": round(
                timing.get("model_build", {}).get("total", 0.0), 3
            ),
            "t_first_solution_sec": round(
                timing.get("solve", {}).get("first_solution", 0.0), 3
            ),
            "t_metaheuristic_sec": round(
                timing.get("solve", {}).get("metaheuristic", 0.0), 3
            ),
            "t_extraction_sec": round(
                timing.get("solution_extraction", {}).get("total", 0.0), 3
            ),
        }

    def _append(self, csv_path, row):
        exists = csv_path.exists()
        with csv_path.open("a", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=COLUMNS)
            if not exists:
                writer.writeheader()
            writer.writerow(row)
