import csv
import math
import time
from datetime import UTC, datetime
from statistics import mean, pstdev

from apps.datasets.models import Dataset, Tree
from apps.optimization.cost_matrix import OSRMCostMatrixBuilder
from apps.optimization.experiment_log import record_experiment
from apps.optimization.greedy import solve_greedy
from apps.optimization.route_metrics import aggregate_metrics, routes_from_points
from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError

CSV_COLUMNS = [
    "target",
    "n_trees",
    "service_time_min",
    "t_max_h",
    "k",
    "balance",
    "total_travel_time_sec",
    "route_time_mean_sec",
    "route_time_std_sec",
    "routes_over_t_max",
    "dropped_trees",
    "sum_max_radius_m",
    "interleave_total",
    "interleave_per_route",
    "worst_pair_iou",
]


class Command(BaseCommand):
    help = (
        "Nearest-neighbor greedy baseline over a real dataset: chains the closest "
        "unvisited tree until the route time budget (T_max) is exhausted, with no "
        "global optimization and no load balancing. Reports the same route-quality "
        "metrics as baseline_sweep so both are directly comparable. Deterministic: "
        "no seeds."
    )

    def add_arguments(self, parser):
        parser.add_argument("--dataset", type=str, required=True)
        parser.add_argument("--service-time", type=float, default=2)
        parser.add_argument("--t-max", type=float, default=3)
        parser.add_argument("--csv", type=str, default=None)

    def handle(self, *args, **options):
        try:
            dataset = Dataset.objects.get(id=options["dataset"])
        except (Dataset.DoesNotExist, ValidationError) as exc:
            raise CommandError(f"Dataset '{options['dataset']}' not found") from exc

        service_time_sec = round(options["service_time"] * 60)
        max_route_time_sec = round(options["t_max"] * 3600)

        trees = sorted(
            Tree.objects.filter(dataset=dataset, is_active=True),
            key=lambda tree: tree.id,
        )
        if len(trees) < 2:
            raise CommandError("Dataset needs at least 2 active trees")

        matrix = OSRMCostMatrixBuilder().build(trees)
        solve_start = time.perf_counter()
        routes = solve_greedy(
            matrix,
            max_route_time_sec=max_route_time_sec,
            service_time_sec=service_time_sec,
        )
        solve_time_sec = round(time.perf_counter() - solve_start, 3)

        travel_times = [self._travel_time(matrix, route) for route in routes]
        estimated_times = [
            math.ceil(travel + len(route) * service_time_sec)
            for travel, route in zip(travel_times, routes, strict=True)
        ]
        spatial = aggregate_metrics(routes_from_points(routes, trees))

        row = {
            "target": dataset.name,
            "n_trees": len(trees),
            "service_time_min": options["service_time"],
            "t_max_h": options["t_max"],
            "k": len(routes),
            "balance": round(min(estimated_times) / max(estimated_times), 3),
            "total_travel_time_sec": round(sum(travel_times)),
            "route_time_mean_sec": round(mean(estimated_times)),
            "route_time_std_sec": round(pstdev(estimated_times)),
            "routes_over_t_max": sum(
                1 for t in estimated_times if t > max_route_time_sec
            ),
            "dropped_trees": len(trees) - sum(len(route) for route in routes),
            **spatial,
        }

        csv_path = self._write_csv(row, options["csv"])
        for column in CSV_COLUMNS:
            self.stdout.write(f"{column}: {row[column]}")
        self.stdout.write(f"solve_time_sec: {solve_time_sec}")

        self.stdout.write("")
        self.stdout.write("route,trees,travel_time_sec,estimated_time_sec")
        for number, (route, travel, estimated) in enumerate(
            zip(routes, travel_times, estimated_times, strict=True), start=1
        ):
            self.stdout.write(f"{number},{len(route)},{round(travel)},{estimated}")

        self.stdout.write("")
        self.stdout.write(f"CSV: {csv_path}")

        report_path = record_experiment(
            slug="greedy-baseline",
            title="Baseline greedy (vecino más cercano)",
            command="manage.py greedy_baseline",
            params={
                "dataset": str(dataset.id),
                "service_time_min": options["service_time"],
                "t_max_h": options["t_max"],
                "csv": str(csv_path),
            },
            metrics={
                **{column: row[column] for column in CSV_COLUMNS},
                "solve_time_sec": solve_time_sec,
            },
        )
        self.stdout.write(f"Experiment report: {report_path}")

    def _travel_time(self, matrix, route):
        return sum(matrix[a][b] for a, b in zip(route[:-1], route[1:], strict=True))

    def _write_csv(self, row, csv_option):
        if csv_option:
            path = settings.BASE_DIR.parent / csv_option
        else:
            directory = settings.EXPERIMENTS_DIR
            path = directory / f"{datetime.now(UTC):%Y%m%d-%H%M%S}-greedy-baseline.csv"
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=CSV_COLUMNS)
            writer.writeheader()
            writer.writerow(row)
        return path
