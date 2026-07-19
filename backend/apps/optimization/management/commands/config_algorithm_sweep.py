import csv
import math
import time
from statistics import mean, median, pstdev

from apps.datasets.instances import dataset_uuid
from apps.datasets.models import Dataset, Tree
from apps.optimization.cost_matrix import OSRMCostMatrixBuilder
from apps.optimization.greedy import solve_greedy
from apps.optimization.models import OptimizationJob, RoutingConfig, RoutingSolution
from apps.optimization.n_estimator import (
    mean_nearest_neighbor_travel,
    p95_nearest_neighbor_travel,
)
from apps.optimization.pipeline import OptimizationPipeline
from apps.optimization.route_audit import (
    audit_route,
    audit_solution,
    worst_overlap_pair,
)
from apps.optimization.route_metrics import aggregate_metrics, routes_from_points
from apps.optimization.route_resequencer import resequence_routes
from apps.optimization.solver import (
    BALANCE_ARM_ACTUAL,
    BALANCE_ARM_FEASIBLE_FLOOR_B085,
    BALANCE_ARM_FEASIBLE_FLOOR_B090,
    BALANCE_ARM_FEASIBLE_FLOOR_B095,
    BALANCE_ARM_NO_FLOOR,
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

# (label, strategy, balance_arm, span_coef, post_resequence, arc_lambda,
#  time_global_span_coef).
# Config axis fixes strategy at spatial_term and sweeps duration soft-bound arms,
# post-pass resequencing (Phase 2), feasible-floor arms (Phase 3a), convex arc
# cost (Phase 3b) and the no-floor family (Phase 4). Algorithm axis fixes arm at
# `actual` and sweeps the strategy.
CONFIG_AXIS = [
    ("actual", SPATIAL, BALANCE_ARM_ACTUAL, 0, False, 0.0, 0),
    ("upper-tmax-tmin9000", SPATIAL, BALANCE_ARM_UPPER_TMAX_TMIN9000, 0, False, 0.0, 0),
    ("tmin-scaled", SPATIAL, BALANCE_ARM_TMIN_SCALED, 0, False, 0.0, 0),
    ("service-floor", SPATIAL, BALANCE_ARM_SERVICE_FLOOR, 0, False, 0.0, 0),
    (
        "tmin-scaled+exempt-last",
        SPATIAL,
        BALANCE_ARM_TMIN_SCALED_EXEMPT_LAST,
        0,
        False,
        0.0,
        0,
    ),
    ("span-c100", SPATIAL, BALANCE_ARM_ACTUAL, 100, False, 0.0, 0),
    # Phase 2 — post-pass intra-route resequencing
    ("actual+reseq", SPATIAL, BALANCE_ARM_ACTUAL, 0, True, 0.0, 0),
    (
        "upper-tmax-tmin9000+reseq",
        SPATIAL,
        BALANCE_ARM_UPPER_TMAX_TMIN9000,
        0,
        True,
        0.0,
        0,
    ),
    # Phase 3a — feasible floor (T_min_eff = min(T_min, β·total_work/k_est))
    ("feasible-floor-b085", SPATIAL, BALANCE_ARM_FEASIBLE_FLOOR_B085, 0, False, 0.0, 0),
    ("feasible-floor-b090", SPATIAL, BALANCE_ARM_FEASIBLE_FLOOR_B090, 0, False, 0.0, 0),
    ("feasible-floor-b095", SPATIAL, BALANCE_ARM_FEASIBLE_FLOOR_B095, 0, False, 0.0, 0),
    # Phase 3b — convex arc cost (arc_cost = travel + λ·max(0,travel−τ)²/τ)
    ("arc-convex-l1", SPATIAL, BALANCE_ARM_ACTUAL, 0, False, 1.0, 0),
    ("arc-convex-l5", SPATIAL, BALANCE_ARM_ACTUAL, 0, False, 5.0, 0),
    ("arc-convex-l20", SPATIAL, BALANCE_ARM_ACTUAL, 0, False, 20.0, 0),
    # Phase 4 — no-floor family: soft lower OFF, soft upper at T_max, optional Time
    # global span cost as a soft balance term instead of a floor.
    ("no-floor", SPATIAL, BALANCE_ARM_NO_FLOOR, 0, False, 0.0, 0),
    ("no-floor-span-c10", SPATIAL, BALANCE_ARM_NO_FLOOR, 0, False, 0.0, 10),
    ("no-floor-span-c100", SPATIAL, BALANCE_ARM_NO_FLOOR, 0, False, 0.0, 100),
    ("no-floor-span-c1000", SPATIAL, BALANCE_ARM_NO_FLOOR, 0, False, 0.0, 1000),
]
ALGO_AXIS = [
    ("global", GLOBAL, BALANCE_ARM_ACTUAL, 0, False, 0.0, 0),
    ("greedy", GREEDY, BALANCE_ARM_ACTUAL, 0, False, 0.0, 0),
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
    "time_global_span_coef",
    "post_resequence",
    "arc_lambda",
    "arc_tau",
    "seed",
    "k",
    "drops",
    "degenerate_routes",
    "travel_sec",
    "balance",
    "sigma_t_sec",
    "dur_min_sec",
    "dur_median_sec",
    "dur_max_sec",
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
            open_m = build_open_matrix(matrix)
            nn_travel = mean_nearest_neighbor_travel(open_m)
            arc_tau = p95_nearest_neighbor_travel(open_m)
            for axis, cell, strategy, arm, span, post_reseq, arc_lam, tgs in cells:
                for seed in options["seeds"]:
                    key = (
                        slug,
                        cell,
                        strategy,
                        arm,
                        str(span),
                        str(tgs),
                        str(post_reseq),
                        str(arc_lam),
                        str(seed),
                    )
                    if key in done:
                        self.stdout.write(f"skip {slug} {cell} seed={seed}")
                        continue
                    row = self._run_cell(
                        slug,
                        trees,
                        matrix,
                        nn_travel,
                        arc_tau,
                        axis,
                        cell,
                        strategy,
                        arm,
                        span,
                        post_reseq,
                        arc_lam,
                        tgs,
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
                    r.get("time_global_span_coef", "0"),
                    r.get("post_resequence", "False"),
                    r.get("arc_lambda", "0.0"),
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
        self,
        slug,
        trees,
        matrix,
        nn_travel,
        arc_tau,
        axis,
        cell,
        strategy,
        arm,
        span,
        post_reseq,
        arc_lam,
        tgs,
        seed,
    ):
        wall_start = time.perf_counter()
        if strategy == GREEDY:
            rows, worst_iou, interleave, timing = self._greedy_cell(trees, matrix)
        else:
            rows, worst_iou, interleave, timing = self._ortools_cell(
                trees, matrix, strategy, arm, span, post_reseq, arc_lam, tgs
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
            post_reseq,
            arc_lam,
            arc_tau,
            tgs,
            seed,
            rows,
            worst_iou,
            interleave,
            timing,
            nn_travel,
            wall,
        )

    def _ortools_cell(
        self, trees, matrix, strategy, arm, span, post_reseq, arc_lam, tgs
    ):
        penalties = PenaltyConfig(balance_arm=arm)
        dataset = trees[0].dataset
        raw_routes = None
        rows = worst = interleave = timing = drops_count = None
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
                    strategy=strategy,
                    penalties=penalties,
                    time_span_coef=span,
                    time_global_span_coef=tgs,
                    convex_arc_lambda=arc_lam,
                )
                solution = RoutingSolution.objects.get(job=job, strategy=strategy)
                drops_count = len(metrics["dropped_trees"])
                timing = solution.timing

                if post_reseq:
                    tree_id_to_idx = {tree.id: i for i, tree in enumerate(trees)}
                    raw_routes = []
                    for route in solution.routes.order_by("route_number"):
                        stops = list(route.stops.order_by("sequence"))
                        raw_routes.append(
                            [tree_id_to_idx[stop.tree_id] for stop in stops]
                        )
                else:
                    audited = audit_solution(
                        solution,
                        min_route_time_sec=CENSUS_MIN_ROUTE_TIME_SEC,
                        max_route_time_sec=CENSUS_MAX_ROUTE_TIME_SEC,
                    )
                    pair = worst_overlap_pair(audited)
                    rows = [entry["row"] for entry in audited]
                    for row in rows:
                        row["drops"] = drops_count
                    worst = pair[2] if pair else 0.0
                    interleave = solution.interleave_per_route

                raise _RollbackError
        except _RollbackError:
            pass

        if post_reseq and raw_routes is not None:
            reseq = resequence_routes(raw_routes, matrix)
            rows, worst, interleave = self._compute_route_metrics(
                reseq, trees, matrix, drops_count
            )

        return rows, worst, interleave, timing

    def _compute_route_metrics(self, routes, trees, matrix, drops_count):
        rows = []
        for i, route in enumerate(routes, start=1):
            points = [(trees[n].location.y, trees[n].location.x) for n in route]
            travel = (
                math.ceil(
                    sum(
                        matrix[a][b] for a, b in zip(route[:-1], route[1:], strict=True)
                    )
                )
                if len(route) > 1
                else 0
            )
            duration = travel + len(route) * CENSUS_SERVICE_TIME_SEC
            row = audit_route(
                i,
                points,
                duration,
                travel,
                min_route_time_sec=CENSUS_MIN_ROUTE_TIME_SEC,
                max_route_time_sec=CENSUS_MAX_ROUTE_TIME_SEC,
            )
            row["drops"] = drops_count
            rows.append(row)
        spatial = aggregate_metrics(routes_from_points(routes, trees))
        return rows, spatial["worst_pair_iou"], spatial["interleave_per_route"]

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
        post_reseq,
        arc_lam,
        arc_tau,
        tgs,
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
            "time_global_span_coef": tgs,
            "post_resequence": post_reseq,
            "arc_lambda": arc_lam,
            "arc_tau": round(arc_tau, 1),
            "seed": seed,
            "k": k,
            "drops": rows[0]["drops"] if rows else 0,
            "degenerate_routes": self._degenerate_count(rows),
            "travel_sec": round(travel_total),
            "balance": balance,
            "sigma_t_sec": round(pstdev(durations)) if k > 1 else 0,
            "dur_min_sec": min(durations) if durations else 0,
            "dur_median_sec": round(median(durations)) if durations else 0,
            "dur_max_sec": max(durations) if durations else 0,
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

    def _degenerate_count(self, rows):
        # A route is degenerate if it carries fewer than 5 stops or runs under 25% of
        # the solution's median route duration. Written before the sweep ran: the no-
        # floor family's known risk is that dropping the floor breeds tiny stub routes.
        if not rows:
            return 0
        med = median(r["duration_sec"] for r in rows)
        return sum(
            1 for r in rows if r["n_trees"] < 5 or r["duration_sec"] < 0.25 * med
        )

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
