import csv
import statistics
import time
from datetime import UTC, datetime

from apps.datasets.models import Dataset, DistanceMatrix, Tree
from apps.optimization.models import OptimizationJob, RoutingConfig, RoutingSolution
from apps.optimization.pipeline import SOLVER_TIME_LIMIT_SEC, OptimizationPipeline
from apps.optimization.route_audit import (
    audit_solution,
    road_self_crossings,
    summarize_audit,
)
from apps.routes.osrm import fetch_route_paths
from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction


class Command(BaseCommand):
    help = (
        "Re-run baseline on frozen instance (reference-n1607) with postpass default "
        "enabled. Consolidates multiple seeds into a single CSV."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--dataset",
            type=str,
            default="reference-n1607",
            help="Instance name (default: reference-n1607)",
        )
        parser.add_argument(
            "--strategy",
            type=str,
            default=RoutingSolution.Strategy.SPATIAL_TERM.value,
        )
        parser.add_argument("--seeds", type=str, default="42,43,44")
        parser.add_argument(
            "--csv",
            type=str,
            default=None,
            help="Output CSV path (default: docs/experiments/postpass-default-YYYYMMDD-HHMMSS.csv)",
        )
        parser.add_argument(
            "--cold-first",
            action="store_true",
            help=(
                "Drop the cached cost matrix before the first seed so that "
                "repetition measures the cold end-to-end wall clock"
            ),
        )

    def handle(self, **options):
        dataset = self._get_dataset(options["dataset"])
        seeds = [int(s) for s in options["seeds"].split(",")]
        strategy = options["strategy"]

        tree_count = Tree.objects.filter(dataset=dataset, is_active=True).count()
        if options["cold_first"]:
            DistanceMatrix.objects.filter(dataset=dataset).delete()
        rows = []
        for index, seed in enumerate(seeds):
            print(f"Running seed {seed}...")
            wall_start = time.perf_counter()
            solution, dropped = self._run_pipeline(dataset, strategy, seed)
            wall_clock_sec = round(time.perf_counter() - wall_start, 1)
            min_route_time_sec = 7200
            max_route_time_sec = 10800
            audited = audit_solution(
                solution,
                min_route_time_sec=min_route_time_sec,
                max_route_time_sec=max_route_time_sec,
            )
            summary = summarize_audit(audited)

            route_durations = [entry["row"]["duration_sec"] for entry in audited]
            route_time_mean = statistics.mean(route_durations)
            route_time_std = (
                statistics.stdev(route_durations) if len(route_durations) > 1 else 0
            )
            routes_over_t_max = sum(
                1 for d in route_durations if d > max_route_time_sec
            )
            routes_under_t_min = sum(
                1 for d in route_durations if d < min_route_time_sec
            )
            t_matrix_sec = solution.timing.get("cost_matrix", {}).get("total", 0)

            row = {
                "instance": dataset.name,
                "n": tree_count,
                "strategy": strategy,
                "seed": seed,
                "k": solution.total_routes,
                "drops": len(dropped),
                "travel_sec": solution.total_travel_time_sec,
                "balance": solution.balance_score,
                "crossings": summary["self_crossings"],
                "worst_iou": solution.worst_pair_iou,
                "interleave_per_route": solution.interleave_per_route,
                "walk_ratio": summary["walk_ratio"],
                "saturation_mean": summary["saturation"],
                "route_time_mean_sec": int(route_time_mean),
                "route_time_std_sec": int(route_time_std),
                "routes_over_t_max": routes_over_t_max,
                "routes_under_t_min": routes_under_t_min,
                "crossings_road": self._crossings_road(solution),
                "wall_clock_sec": wall_clock_sec,
                "t_matrix_sec": round(t_matrix_sec, 1),
                "cache_state": (
                    "cold" if options["cold_first"] and index == 0 else "warm"
                ),
            }
            rows.append(row)
            print(
                f"  k={row['k']}, travel={row['travel_sec']:.0f}s, balance={row['balance']:.3f}"
            )

        csv_path = self._write_csv(rows, options["csv"])
        self.stdout.write(self.style.SUCCESS(f"CSV: {csv_path}"))

    def _crossings_road(self, solution):
        coordinate_lists = []
        for route in solution.routes.order_by("route_number"):
            stops = route.stops.select_related("tree").order_by("sequence")
            coordinate_lists.append(
                [(stop.tree.location.x, stop.tree.location.y) for stop in stops]
            )
        paths = fetch_route_paths(coordinate_lists)
        return sum(road_self_crossings(path) for path in paths)

    def _get_dataset(self, dataset_name):
        try:
            return Dataset.objects.get(name=dataset_name)
        except (Dataset.DoesNotExist, ValidationError) as exc:
            raise CommandError(f"Dataset '{dataset_name}' not found") from exc

    def _run_pipeline(self, dataset, strategy, seed):
        with transaction.atomic():
            config = RoutingConfig.objects.create(
                dataset=dataset,
                service_time_sec=120,
                min_route_time_sec=7200,
                max_route_time_sec=10800,
            )
            job = OptimizationJob.objects.create(config=config, strategy=strategy)

        job.set_status("running")
        metrics = OptimizationPipeline(job).run(
            strategy=strategy,
            time_limit_sec=SOLVER_TIME_LIMIT_SEC,
            node_seed=seed,
        )
        job.set_completed(metrics)

        solution = RoutingSolution.objects.get(job=job, strategy=strategy)
        return solution, metrics["dropped_trees"]

    def _write_csv(self, rows, csv_option):
        if csv_option:
            path = settings.BASE_DIR.parent / csv_option
        else:
            directory = settings.EXPERIMENTS_DIR
            path = (
                directory / f"{datetime.now(UTC):%Y%m%d-%H%M%S}-postpass-baseline.csv"
            )

        path.parent.mkdir(parents=True, exist_ok=True)

        fieldnames = list(rows[0].keys())
        with path.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)

        return path
