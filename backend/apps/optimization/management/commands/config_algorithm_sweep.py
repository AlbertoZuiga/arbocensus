import csv
import math
import time
from statistics import mean, median, pstdev
from typing import NamedTuple

from apps.datasets.instances import dataset_uuid
from apps.datasets.models import Dataset, Tree
from apps.optimization.bounds import minimum_spanning_forest, symmetric_mst_edges
from apps.optimization.cost_matrix import OSRMCostMatrixBuilder
from apps.optimization.greedy import solve_greedy
from apps.optimization.models import OptimizationJob, RoutingConfig, RoutingSolution
from apps.optimization.multistart import (
    BUDGET_MODES,
    BUDGET_PER_START,
    start_seeds,
    start_time_limit_sec,
)
from apps.optimization.n_estimator import (
    mean_nearest_neighbor_travel,
    p95_nearest_neighbor_travel,
)
from apps.optimization.pipeline import OptimizationPipeline, default_time_limit_sec
from apps.optimization.route_audit import (
    audit_route,
    audit_solution,
    road_self_crossings,
    worst_overlap_pair,
)
from apps.optimization.route_metrics import aggregate_metrics, routes_from_points
from apps.optimization.route_resequencer import (
    resequence_routes,
    solution_two_opt_gap,
)
from apps.optimization.solver import (
    BALANCE_ARM_ACTUAL,
    BALANCE_ARM_COMBINED_B060_STOPS10,
    BALANCE_ARM_COMBINED_B070_STOPS10,
    BALANCE_ARM_COMBINED_B085_STOPS10,
    BALANCE_ARM_COMBINED_B095_STOPS5,
    BALANCE_ARM_COMBINED_B095_STOPS10,
    BALANCE_ARM_COMBINED_B095_STOPS15,
    BALANCE_ARM_FEASIBLE_FLOOR_B050,
    BALANCE_ARM_FEASIBLE_FLOOR_B060,
    BALANCE_ARM_FEASIBLE_FLOOR_B070,
    BALANCE_ARM_FEASIBLE_FLOOR_B085,
    BALANCE_ARM_FEASIBLE_FLOOR_B090,
    BALANCE_ARM_FEASIBLE_FLOOR_B095,
    BALANCE_ARM_NO_FLOOR,
    BALANCE_ARM_NO_FLOOR_LOWFLOOR3600,
    BALANCE_ARM_NO_FLOOR_LOWFLOOR5400,
    BALANCE_ARM_NO_FLOOR_STOPS5,
    BALANCE_ARM_NO_FLOOR_STOPS10,
    BALANCE_ARM_NO_FLOOR_STOPS15,
    BALANCE_ARM_SERVICE_FLOOR,
    BALANCE_ARM_TMIN_SCALED,
    BALANCE_ARM_TMIN_SCALED_EXEMPT_LAST,
    BALANCE_ARM_UPPER_TMAX_TMIN9000,
    SOFT_LOWER_PENALTY,
    SOFT_UPPER_TARGET_MIDPOINT,
    SOFT_UPPER_TARGET_TMAX,
    STOPS_FLOOR_PENALTY,
    PenaltyConfig,
    build_open_matrix,
)
from apps.optimization.strategies import SPATIAL_SPAN_COEF
from apps.optimization.sweep_sequences import append_sequences
from apps.optimization.warm_start import WARM_START_CLUSTER_FIRST, WARM_START_GREEDY
from apps.routes.osrm import fetch_route_paths
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


class Cell(NamedTuple):
    label: str
    strategy: str
    balance_arm: str
    span_coef: int = 0
    post_resequence: bool = False
    arc_lambda: float = 0.0
    time_global_span_coef: int = 0
    cluster_neighbors: int | None = None
    warm_start: str | None = None
    soft_lower_penalty: int = SOFT_LOWER_PENALTY
    soft_upper_target: str = SOFT_UPPER_TARGET_MIDPOINT


# Config axis fixes strategy at spatial_term and sweeps duration soft-bound arms,
# post-pass resequencing, feasible-floor arms, convex arc cost, the no-floor family
# and the anti-stub floors. Algorithm axis fixes arm at `actual` and sweeps the
# strategy.
CONFIG_AXIS = [
    Cell("actual", SPATIAL, BALANCE_ARM_ACTUAL),
    Cell("upper-tmax-tmin9000", SPATIAL, BALANCE_ARM_UPPER_TMAX_TMIN9000),
    Cell("tmin-scaled", SPATIAL, BALANCE_ARM_TMIN_SCALED),
    Cell("service-floor", SPATIAL, BALANCE_ARM_SERVICE_FLOOR),
    Cell("tmin-scaled+exempt-last", SPATIAL, BALANCE_ARM_TMIN_SCALED_EXEMPT_LAST),
    Cell("span-c100", SPATIAL, BALANCE_ARM_ACTUAL, span_coef=100),
    # Post-pass intra-route resequencing
    Cell("actual+reseq", SPATIAL, BALANCE_ARM_ACTUAL, post_resequence=True),
    Cell(
        "upper-tmax-tmin9000+reseq",
        SPATIAL,
        BALANCE_ARM_UPPER_TMAX_TMIN9000,
        post_resequence=True,
    ),
    # Feasible floor (T_min_eff = min(T_min, β·total_work/k_est))
    Cell("feasible-floor-b085", SPATIAL, BALANCE_ARM_FEASIBLE_FLOOR_B085),
    Cell("feasible-floor-b090", SPATIAL, BALANCE_ARM_FEASIBLE_FLOOR_B090),
    Cell("feasible-floor-b095", SPATIAL, BALANCE_ARM_FEASIBLE_FLOOR_B095),
    # Convex arc cost (arc_cost = travel + λ·max(0,travel−τ)²/τ)
    Cell("arc-convex-l1", SPATIAL, BALANCE_ARM_ACTUAL, arc_lambda=1.0),
    Cell("arc-convex-l5", SPATIAL, BALANCE_ARM_ACTUAL, arc_lambda=5.0),
    Cell("arc-convex-l20", SPATIAL, BALANCE_ARM_ACTUAL, arc_lambda=20.0),
    # No-floor family: no soft bounds at all, optional Time global span
    # cost as a soft balance term instead of a floor.
    Cell("no-floor", SPATIAL, BALANCE_ARM_NO_FLOOR),
    Cell("no-floor-span-c10", SPATIAL, BALANCE_ARM_NO_FLOOR, time_global_span_coef=10),
    Cell(
        "no-floor-span-c100", SPATIAL, BALANCE_ARM_NO_FLOOR, time_global_span_coef=100
    ),
    Cell(
        "no-floor-span-c1000", SPATIAL, BALANCE_ARM_NO_FLOOR, time_global_span_coef=1000
    ),
    Cell("no-floor+reseq", SPATIAL, BALANCE_ARM_NO_FLOOR, post_resequence=True),
    # Anti-stub floors: a floor on stop count cannot be padded by
    # walking, unlike the low absolute time floors it is compared against.
    Cell("no-floor-stops5", SPATIAL, BALANCE_ARM_NO_FLOOR_STOPS5),
    Cell("no-floor-stops10", SPATIAL, BALANCE_ARM_NO_FLOOR_STOPS10),
    Cell("no-floor-stops15", SPATIAL, BALANCE_ARM_NO_FLOOR_STOPS15),
    Cell("no-floor-lowfloor3600", SPATIAL, BALANCE_ARM_NO_FLOOR_LOWFLOOR3600),
    Cell("no-floor-lowfloor5400", SPATIAL, BALANCE_ARM_NO_FLOOR_LOWFLOOR5400),
    # Low-beta feasible floors, for the relleno-vs-balance frontier of a single
    # instance: the pre-existing grid only reaches down to 0.85.
    Cell("feasible-floor-b050", SPATIAL, BALANCE_ARM_FEASIBLE_FLOOR_B050),
    Cell("feasible-floor-b060", SPATIAL, BALANCE_ARM_FEASIBLE_FLOOR_B060),
    Cell("feasible-floor-b070", SPATIAL, BALANCE_ARM_FEASIBLE_FLOOR_B070),
    # Combined floor: scaled duration floor (balance) + stop-count floor (anti-stub).
    Cell("feasible-floor-b060-stops10", SPATIAL, BALANCE_ARM_COMBINED_B060_STOPS10),
    Cell("feasible-floor-b070-stops10", SPATIAL, BALANCE_ARM_COMBINED_B070_STOPS10),
    Cell("feasible-floor-b085-stops10", SPATIAL, BALANCE_ARM_COMBINED_B085_STOPS10),
    # Stop-count floor on top of the closest candidate of the series, whose only
    # remaining failure is a degenerate route marked by stop count, not duration.
    Cell("feasible-floor-b095-stops5", SPATIAL, BALANCE_ARM_COMBINED_B095_STOPS5),
    Cell("feasible-floor-b095-stops10", SPATIAL, BALANCE_ARM_COMBINED_B095_STOPS10),
    Cell("feasible-floor-b095-stops15", SPATIAL, BALANCE_ARM_COMBINED_B095_STOPS15),
    # Soft clusters: kmeans over the coordinates restricts each node to the vehicles
    # of its own cluster plus its r nearest ones. This shrinks the feasible SET
    # instead of repricing the objective, while keeping a single global pass that can
    # still rebalance the cluster borders.
    Cell("cluster-r0", SPATIAL, BALANCE_ARM_ACTUAL, cluster_neighbors=0),
    Cell("cluster-r1", SPATIAL, BALANCE_ARM_ACTUAL, cluster_neighbors=1),
    Cell("cluster-r2", SPATIAL, BALANCE_ARM_ACTUAL, cluster_neighbors=2),
    # Same restriction without the duration floor, since padding to reach T_min is the
    # measured source of intra-route crossings that spatial coherence alone cannot fix.
    Cell("cluster-r1-no-floor", SPATIAL, BALANCE_ARM_NO_FLOOR, cluster_neighbors=1),
    # Warm start: seed the metaheuristic with a spatially coherent construction
    # instead of letting PATH_CHEAPEST_ARC build one from scratch.
    Cell("warm-greedy", SPATIAL, BALANCE_ARM_ACTUAL, warm_start=WARM_START_GREEDY),
    Cell(
        "warm-cluster",
        SPATIAL,
        BALANCE_ARM_ACTUAL,
        warm_start=WARM_START_CLUSTER_FIRST,
    ),
]
ALGO_AXIS = [
    Cell("global", GLOBAL, BALANCE_ARM_ACTUAL),
    Cell("greedy", GREEDY, BALANCE_ARM_ACTUAL),
]

# Factorial over the two duration-channel prices of the `actual` arm: the soft
# lower floor price (A) and the soft upper target (B). `floor10000-mid` is the
# production baseline (`actual`), re-run inside the cycle rather than compared to
# published means. Selected with --factorial; run one label at a time with
# --only-cell to parallelize one CSV per cell.
FACTORIAL_AXIS = [
    Cell(
        f"floor{penalty}-{'tmax' if target == SOFT_UPPER_TARGET_TMAX else 'mid'}",
        SPATIAL,
        BALANCE_ARM_ACTUAL,
        soft_lower_penalty=penalty,
        soft_upper_target=target,
    )
    for penalty in (10000, 2000, 500, 100)
    for target in (SOFT_UPPER_TARGET_MIDPOINT, SOFT_UPPER_TARGET_TMAX)
]

SEEDS = [1, 2, 3]

DEGENERATE_MIN_STOPS = 5
DEGENERATE_MIN_DURATION_SEC = 1800

COLUMNS = [
    "instance",
    "n",
    "axis",
    "cell",
    "strategy",
    "balance_arm",
    "soft_lower_penalty",
    "soft_upper_target",
    "span_coef",
    "spatial_span_coef",
    "stops_floor_penalty",
    "max_vehicles_forced",
    "time_global_span_coef",
    "post_resequence",
    "arc_lambda",
    "arc_tau",
    "cluster_neighbors",
    "cluster_count",
    "vehicles_per_cluster",
    "warm_start",
    "seed",
    "starts",
    "budget_mode",
    "start_time_limit_sec",
    "k",
    "drops",
    "degenerate_routes",
    "travel_sec",
    "balance",
    "sigma_t_sec",
    "dur_min_sec",
    "dur_median_sec",
    "dur_max_sec",
    "crossings_chord",
    "crossings_road",
    "worst_iou",
    "interleave_per_route",
    "walk_ratio",
    "saturation_mean",
    "sat_estimated",
    "relleno_sec",
    "msf_k_sec",
    "relleno_msf_sec",
    "deficit_sec",
    "wall_clock_sec",
    "t_osrm_sec",
    "t_model_build_sec",
    "t_first_solution_sec",
    "t_metaheuristic_sec",
    "t_extraction_sec",
    "two_opt_gap",
]


class _RollbackError(Exception):
    pass


def _blank_if_none(value):
    return "" if value is None else str(value)


class Command(BaseCommand):
    help = (
        "Config x algorithm x size sweep over the frozen real-instance suite. "
        "Reference census config: service 2 min, T_max 3 h. Appends one row per "
        "cell to a master CSV and is resumable: cells already present are skipped. "
        "OR-Tools cells run inside a rolled-back transaction so the shared database "
        "is not polluted with hundreds of throwaway solutions. The stop sequence of "
        "every route is written to a .sequences.jsonl file next to the CSV."
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
            "--factorial",
            action="store_true",
            help=(
                "Run the floor-price x upper-target factorial axis instead of the "
                "config/algo axes"
            ),
        )
        parser.add_argument(
            "--spatial-span-coef",
            type=int,
            default=SPATIAL_SPAN_COEF,
            help="Override the spatial_term geographic span coefficient",
        )
        parser.add_argument(
            "--stops-penalty",
            type=int,
            default=STOPS_FLOOR_PENALTY,
            help="Override the per-missing-stop penalty of the stop-floor arms",
        )
        parser.add_argument(
            "--max-vehicles",
            type=int,
            default=None,
            help=(
                "Force an exact fleet size instead of the estimator (which adds a "
                "buffer), to test whether padding is an excess-vehicle artefact"
            ),
        )
        parser.add_argument(
            "--seeds",
            type=int,
            nargs="+",
            default=SEEDS,
        )
        parser.add_argument(
            "--starts",
            type=int,
            default=1,
            help=(
                "Number of node-order restarts per run; the best one by solver "
                "objective is kept"
            ),
        )
        parser.add_argument(
            "--budget",
            type=str,
            choices=BUDGET_MODES,
            default=BUDGET_PER_START,
            help=(
                "'per-start' gives every restart the full time limit; 'total' "
                "splits one time limit across the restarts"
            ),
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

        if options["factorial"]:
            cells = [("factorial", cell) for cell in FACTORIAL_AXIS]
        else:
            cells = [("config", cell) for cell in CONFIG_AXIS]
            cells += [("algo", cell) for cell in ALGO_AXIS]
        if options["only_cell"]:
            cells = [c for c in cells if c[1].label == options["only_cell"]]
            if not cells:
                raise CommandError(f"unknown cell '{options['only_cell']}'")

        spatial_span_coef = options["spatial_span_coef"]
        stops_penalty = options["stops_penalty"]
        max_vehicles = options["max_vehicles"]
        starts = options["starts"]
        budget = options["budget"]
        for slug in instances:
            trees, matrix = self._prepare_instance(slug)
            open_m = build_open_matrix(matrix)
            nn_travel = mean_nearest_neighbor_travel(open_m)
            arc_tau = p95_nearest_neighbor_travel(open_m)
            mst_edges = symmetric_mst_edges(matrix)
            for axis, cell in cells:
                seeds = options["seeds"]
                if cell.strategy == GREEDY:
                    # Greedy has no seeded decision, so extra seeds would be copies of
                    # one run dressed up as replicates — the defect this sweep fixes.
                    seeds = seeds[:1]
                for seed in seeds:
                    key = (
                        slug,
                        cell.label,
                        cell.strategy,
                        cell.balance_arm,
                        str(cell.soft_lower_penalty),
                        cell.soft_upper_target,
                        str(cell.span_coef),
                        str(cell.time_global_span_coef),
                        str(cell.post_resequence),
                        str(cell.arc_lambda),
                        _blank_if_none(cell.cluster_neighbors),
                        _blank_if_none(cell.warm_start),
                        str(spatial_span_coef),
                        str(stops_penalty),
                        str(max_vehicles or ""),
                        str(seed),
                        str(starts),
                        budget,
                    )
                    if key in done:
                        self.stdout.write(f"skip {slug} {cell.label} seed={seed}")
                        continue
                    row, sequences = self._run_cell(
                        slug,
                        trees,
                        matrix,
                        nn_travel,
                        mst_edges,
                        arc_tau,
                        axis,
                        cell,
                        seed,
                        spatial_span_coef,
                        stops_penalty,
                        max_vehicles,
                        starts,
                        budget,
                    )
                    self._append(csv_path, row)
                    append_sequences(csv_path, row, sequences)
                    done.add(key)
                    self.stdout.write(
                        f"done {slug} {cell.label} seed={seed} "
                        f"k={row['k']} bal={row['balance']} "
                        f"chord={row['crossings_chord']} road={row['crossings_road']} "
                        f"wall={row['wall_clock_sec']}s"
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
                    r.get("soft_lower_penalty", str(SOFT_LOWER_PENALTY)),
                    r.get("soft_upper_target", SOFT_UPPER_TARGET_MIDPOINT),
                    r["span_coef"],
                    r.get("time_global_span_coef", "0"),
                    r.get("post_resequence", "False"),
                    r.get("arc_lambda", "0.0"),
                    r.get("cluster_neighbors", ""),
                    r.get("warm_start", ""),
                    r.get("spatial_span_coef", str(SPATIAL_SPAN_COEF)),
                    r.get("stops_floor_penalty", str(STOPS_FLOOR_PENALTY)),
                    r.get("max_vehicles_forced", ""),
                    r["seed"],
                    r.get("starts", "1"),
                    r.get("budget_mode", BUDGET_PER_START),
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
        mst_edges,
        arc_tau,
        axis,
        cell,
        seed,
        span_coef,
        stops_penalty,
        max_vehicles,
        starts,
        budget,
    ):
        per_start_limit = start_time_limit_sec(
            default_time_limit_sec(len(trees)), starts, budget
        )
        wall_start = time.perf_counter()
        if cell.strategy == GREEDY:
            rows, worst_iou, interleave, timing, routes = self._greedy_cell(
                trees, matrix
            )
            plan = {}
        else:
            rows, worst_iou, interleave, timing, plan, routes = self._ortools_cell(
                trees,
                matrix,
                cell,
                span_coef,
                stops_penalty,
                max_vehicles,
                seed,
                starts,
                per_start_limit,
            )
        wall = round(time.perf_counter() - wall_start, 2)
        gap = solution_two_opt_gap(routes, matrix)
        crossings_road = self._crossings_road(routes, trees)
        sequences = [[trees[node].id for node in route] for route in routes]
        row = self._metrics_row(
            slug,
            len(trees),
            axis,
            cell,
            arc_tau,
            seed,
            span_coef,
            stops_penalty,
            max_vehicles,
            starts,
            budget,
            per_start_limit,
            rows,
            worst_iou,
            interleave,
            timing,
            plan,
            nn_travel,
            mst_edges,
            wall,
            gap,
            crossings_road,
        )
        return row, sequences

    def _crossings_road(self, routes, trees):
        # Same [lon, lat] stop coordinates the surveyor endpoint feeds OSRM, so the
        # polyline this counts crossings on is the one drawn on the surveyor map.
        coordinate_lists = [
            [(trees[node].location.x, trees[node].location.y) for node in route]
            for route in routes
        ]
        paths = fetch_route_paths(coordinate_lists)
        return sum(road_self_crossings(path) for path in paths)

    def _ortools_cell(
        self,
        trees,
        matrix,
        cell,
        span_coef,
        stops_penalty,
        max_vehicles,
        seed,
        starts,
        per_start_limit,
    ):
        strategy = cell.strategy
        penalties = PenaltyConfig(
            balance_arm=cell.balance_arm,
            stops_floor_penalty=stops_penalty,
            soft_lower_penalty=cell.soft_lower_penalty,
            soft_upper_target=cell.soft_upper_target,
        )
        dataset = trees[0].dataset
        raw_routes = []
        plan = {}
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
                    spatial_span_coef=span_coef,
                    time_span_coef=cell.span_coef,
                    time_global_span_coef=cell.time_global_span_coef,
                    convex_arc_lambda=cell.arc_lambda,
                    max_vehicles=max_vehicles,
                    time_limit_sec=per_start_limit,
                    node_seeds=start_seeds(seed, starts),
                    cluster_neighbors=cell.cluster_neighbors,
                    warm_start=cell.warm_start,
                )
                solution = RoutingSolution.objects.get(job=job, strategy=strategy)
                drops_count = len(metrics["dropped_trees"])
                timing = solution.timing
                plan = {
                    "cluster_count": metrics["cluster_count"],
                    "vehicles_per_cluster": metrics["vehicles_per_cluster"],
                }

                tree_id_to_idx = {tree.id: i for i, tree in enumerate(trees)}
                raw_routes = []
                for route in solution.routes.order_by("route_number"):
                    stops = list(route.stops.order_by("sequence"))
                    raw_routes.append([tree_id_to_idx[stop.tree_id] for stop in stops])

                if not cell.post_resequence:
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

        routes = raw_routes
        if cell.post_resequence:
            routes = resequence_routes(raw_routes, matrix)
            rows, worst, interleave = self._compute_route_metrics(
                routes, trees, matrix, drops_count
            )

        return rows, worst, interleave, timing, plan, routes

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
        return (
            rows,
            spatial["worst_pair_iou"],
            spatial["interleave_per_route"],
            None,
            routes,
        )

    def _metrics_row(
        self,
        slug,
        n,
        axis,
        cell,
        arc_tau,
        seed,
        spatial_span_coef,
        stops_penalty,
        max_vehicles,
        starts,
        budget,
        per_start_limit,
        rows,
        worst_iou,
        interleave,
        timing,
        plan,
        nn_travel,
        mst_edges,
        wall,
        two_opt_gap,
        crossings_road,
    ):
        durations = [r["duration_sec"] for r in rows]
        travels = [r["travel_sec"] for r in rows]
        k = len(rows)
        travel_total = sum(travels)
        service_total = sum(r["service_total_sec"] for r in rows)
        balance = self._balance(durations, cell.balance_arm)
        deficit = sum(
            max(0, CENSUS_MIN_ROUTE_TIME_SEC - r["service_total_sec"]) for r in rows
        )
        # Minimal travel to visit n trees across k open routes is n-k edges; the
        # excess over that nearest-neighbour lower bound is padding (relleno).
        travel_min_est = max(0, n - k) * nn_travel
        relleno = max(0, round(travel_total - travel_min_est))
        # Reachable zero point: k open paths spanning n nodes are a spanning forest
        # of k components, so MSF_k is travel a real solution can actually attain —
        # unlike the nearest-neighbour sum above, which violates the degree-2
        # constraint of a path and can never be reached.
        msf_k = minimum_spanning_forest(mst_edges, k)
        drops = rows[0]["drops"] if rows else 0
        if drops:
            # The forest bound spans every node, so it stops bounding a solution that
            # abandons some of them.
            relleno_msf = ""
        else:
            if travel_total < msf_k - 1:
                raise CommandError(
                    f"{slug} {cell.label}: travel {travel_total:.0f} below the "
                    f"spanning-forest bound MSF_{k}={msf_k:.0f} — the bound or the "
                    f"travel accounting is wrong"
                )
            relleno_msf = max(0, round(travel_total - msf_k))
        sat_estimated = (
            round(service_total / (k * CENSUS_MAX_ROUTE_TIME_SEC), 3) if k else 0.0
        )
        phases = self._phase_times(timing)
        return {
            "instance": slug,
            "n": n,
            "axis": axis,
            "cell": cell.label,
            "strategy": cell.strategy,
            "balance_arm": cell.balance_arm,
            "soft_lower_penalty": cell.soft_lower_penalty,
            "soft_upper_target": cell.soft_upper_target,
            "span_coef": cell.span_coef,
            "spatial_span_coef": spatial_span_coef,
            "stops_floor_penalty": stops_penalty,
            "max_vehicles_forced": max_vehicles or "",
            "time_global_span_coef": cell.time_global_span_coef,
            "post_resequence": cell.post_resequence,
            "arc_lambda": cell.arc_lambda,
            "arc_tau": round(arc_tau, 1),
            "cluster_neighbors": _blank_if_none(cell.cluster_neighbors),
            "cluster_count": plan.get("cluster_count", ""),
            "vehicles_per_cluster": plan.get("vehicles_per_cluster", ""),
            "warm_start": _blank_if_none(cell.warm_start),
            "seed": seed,
            "starts": starts,
            "budget_mode": budget,
            "start_time_limit_sec": per_start_limit,
            "k": k,
            "drops": drops,
            "degenerate_routes": self._degenerate_count(rows),
            "travel_sec": round(travel_total),
            "balance": balance,
            "sigma_t_sec": round(pstdev(durations)) if k > 1 else 0,
            "dur_min_sec": round(min(durations)) if durations else 0,
            "dur_median_sec": round(median(durations)) if durations else 0,
            "dur_max_sec": round(max(durations)) if durations else 0,
            "crossings_chord": sum(r["self_crossings"] for r in rows),
            "crossings_road": crossings_road,
            "worst_iou": round(worst_iou, 3),
            "interleave_per_route": round(interleave, 3),
            "walk_ratio": (
                round(travel_total / sum(durations), 3) if sum(durations) else 0.0
            ),
            "saturation_mean": round(mean(r["saturation"] for r in rows), 3),
            "sat_estimated": sat_estimated,
            "relleno_sec": relleno,
            "msf_k_sec": round(msf_k),
            "relleno_msf_sec": relleno_msf,
            "deficit_sec": deficit,
            "wall_clock_sec": wall,
            **phases,
            "two_opt_gap": round(two_opt_gap, 4),
        }

    def _degenerate_count(self, rows):
        # Stub routes no surveyor can be handed: too few stops, or shorter than half
        # a working morning. Both thresholds are absolute — a threshold relative to
        # the solution's own median cannot see a uniformly fragmented solution, where
        # every route is equally tiny.
        return sum(
            1
            for r in rows
            if r["n_trees"] < DEGENERATE_MIN_STOPS
            or r["duration_sec"] < DEGENERATE_MIN_DURATION_SEC
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
