import csv
import json
from datetime import UTC, datetime
from statistics import mean

from apps.datasets.models import Dataset
from apps.optimization.experiment_log import record_experiment
from apps.optimization.models import OptimizationJob, RoutingConfig, RoutingSolution
from apps.optimization.pipeline import SOLVER_TIME_LIMIT_SEC, OptimizationPipeline
from apps.optimization.route_audit import (
    AUDIT_COLUMNS,
    audit_solution,
    routes_geojson,
    summarize_audit,
    tmin_gap_coverage,
    worst_overlap_pair,
)
from apps.optimization.solver import (
    SOFT_LOWER_PENALTY,
    SOFT_UPPER_PENALTY,
    SOFT_UPPER_TARGET_MIDPOINT,
    SOFT_UPPER_TARGETS,
    PenaltyConfig,
)
from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction


class Command(BaseCommand):
    help = (
        "Per-route radiography of one pipeline run on a real dataset: walk_ratio "
        "(travel/duration), service total, shortfall against T_min, saturation "
        "against T_max and self-crossings of the stop sequence. Emits a per-route "
        "CSV (last row 'summary': sums for counts and times, mean saturation, "
        "aggregate walk_ratio) and a GeoJSON FeatureCollection with one LineString "
        "per route plus one Point per stop. On a real dataset the seed only labels "
        "the repetition: variance comes from the solver's wall-clock time limit."
    )

    def add_arguments(self, parser):
        parser.add_argument("--dataset", type=str, required=True)
        parser.add_argument(
            "--strategy",
            type=str,
            default=RoutingSolution.Strategy.SPATIAL_TERM.value,
            choices=[s.value for s in RoutingSolution.Strategy],
        )
        parser.add_argument(
            "--service-time",
            type=int,
            default=RoutingConfig.DEFAULT_SERVICE_TIME_SEC,
            help="Service time per tree in seconds",
        )
        parser.add_argument(
            "--t-min",
            type=int,
            default=RoutingConfig.DEFAULT_MIN_ROUTE_TIME_SEC,
            help="Target minimum route duration in seconds",
        )
        parser.add_argument(
            "--t-max",
            type=int,
            default=RoutingConfig.DEFAULT_MAX_ROUTE_TIME_SEC,
            help="Maximum route duration in seconds",
        )
        parser.add_argument(
            "--time-limit",
            type=int,
            default=SOLVER_TIME_LIMIT_SEC,
            help="Solver time limit in seconds",
        )
        parser.add_argument(
            "--soft-lower-penalty",
            type=int,
            default=SOFT_LOWER_PENALTY,
            help="Cost per second below T_min at the end of a route",
        )
        parser.add_argument(
            "--soft-upper-target",
            type=str,
            default=SOFT_UPPER_TARGET_MIDPOINT,
            choices=list(SOFT_UPPER_TARGETS),
            help="Where the soft upper bound of the Time dimension sits",
        )
        parser.add_argument(
            "--soft-upper-penalty",
            type=int,
            default=SOFT_UPPER_PENALTY,
            help="Cost per second above the soft upper target",
        )
        parser.add_argument("--seed", type=int, default=42)
        parser.add_argument("--csv", type=str, default=None)
        parser.add_argument("--geojson", type=str, default=None)
        parser.add_argument(
            "--worst-pair-geojson",
            type=str,
            default=None,
            help="Also write a GeoJSON with only the worst bbox-IoU route pair",
        )

    def handle(self, *args, **options):
        dataset = self._get_dataset(options["dataset"])
        service_time_sec = options["service_time"]
        min_route_time_sec = options["t_min"]
        max_route_time_sec = options["t_max"]
        if min_route_time_sec > max_route_time_sec:
            raise CommandError("--t-min must not exceed --t-max")

        strategy = options["strategy"]
        penalties = PenaltyConfig(
            soft_lower_penalty=options["soft_lower_penalty"],
            soft_upper_penalty=options["soft_upper_penalty"],
            soft_upper_target=options["soft_upper_target"],
        )
        solution, dropped = self._run_pipeline(
            dataset,
            strategy,
            service_time_sec,
            min_route_time_sec,
            max_route_time_sec,
            options["time_limit"],
            penalties,
        )

        audited = audit_solution(
            solution,
            min_route_time_sec=min_route_time_sec,
            max_route_time_sec=max_route_time_sec,
        )
        summary = summarize_audit(audited)
        rows = [entry["row"] for entry in audited] + [summary]

        csv_path = self._write_csv(rows, options["csv"])
        geojson_path = self._write_geojson(routes_geojson(audited), options["geojson"])
        worst_pair = worst_overlap_pair(audited)
        worst_pair_path = None
        if options["worst_pair_geojson"]:
            if worst_pair:
                first, second, _ = worst_pair
                worst_pair_path = self._write_geojson(
                    routes_geojson([first, second]), options["worst_pair_geojson"]
                )
            else:
                self.stderr.write(
                    "--worst-pair-geojson skipped: the solution has a single route"
                )

        coverage = tmin_gap_coverage(rows[:-1], min_route_time_sec=min_route_time_sec)
        self._print_report(
            dataset,
            solution,
            strategy,
            penalties,
            rows,
            summary,
            coverage,
            worst_pair,
            dropped,
            csv_path,
            geojson_path,
            worst_pair_path,
        )

        report_path = record_experiment(
            slug="route-audit",
            title="Radiografía por ruta (walk_ratio, shortfall, saturación)",
            command="manage.py route_audit",
            params={
                "dataset": str(dataset.id),
                "strategy": strategy,
                "service_time_sec": service_time_sec,
                "t_min_sec": min_route_time_sec,
                "t_max_sec": max_route_time_sec,
                "time_limit_sec": options["time_limit"],
                "soft_lower_penalty": penalties.soft_lower_penalty,
                "soft_upper_target": penalties.soft_upper_target,
                "soft_upper_penalty": penalties.soft_upper_penalty,
                "seed": options["seed"],
                "csv": str(csv_path),
                "geojson": str(geojson_path),
            },
            metrics={
                "k": solution.total_routes,
                "dropped_trees": len(dropped),
                "total_travel_time_sec": round(solution.total_travel_time_sec),
                "balance_score": solution.balance_score,
                "walk_ratio_aggregate": summary["walk_ratio"],
                "walk_ratio_worst": max(row["walk_ratio"] for row in rows[:-1]),
                "tmin_gap_routes": len(coverage),
                "tmin_gap_coverage_mean": (
                    round(mean(coverage), 3) if coverage else None
                ),
                "shortfall_total_sec": summary["shortfall_sec"],
                "saturation_mean": summary["saturation"],
                "self_crossings_total": summary["self_crossings"],
                "worst_pair_iou": solution.worst_pair_iou,
            },
        )
        self.stdout.write(f"Experiment report: {report_path}")

    def _get_dataset(self, dataset_id):
        try:
            return Dataset.objects.get(id=dataset_id)
        except (Dataset.DoesNotExist, ValidationError) as exc:
            raise CommandError(f"Dataset '{dataset_id}' not found") from exc

    def _run_pipeline(
        self,
        dataset,
        strategy,
        service_time_sec,
        min_route_time_sec,
        max_route_time_sec,
        time_limit_sec,
        penalties,
    ):
        with transaction.atomic():
            config = RoutingConfig.objects.create(
                dataset=dataset,
                service_time_sec=service_time_sec,
                min_route_time_sec=min_route_time_sec,
                max_route_time_sec=max_route_time_sec,
            )
            job = OptimizationJob.objects.create(config=config, strategy=strategy)

        job.set_status("running")
        metrics = OptimizationPipeline(job).run(
            strategy=strategy, time_limit_sec=time_limit_sec, penalties=penalties
        )
        job.set_completed(metrics)

        solution = RoutingSolution.objects.get(job=job, strategy=strategy)
        return solution, metrics["dropped_trees"]

    def _write_csv(self, rows, csv_option):
        path = self._resolve_path(csv_option, "route-audit.csv")
        with path.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=AUDIT_COLUMNS)
            writer.writeheader()
            writer.writerows(rows)
        return path

    def _write_geojson(self, collection, geojson_option):
        path = self._resolve_path(geojson_option, "route-audit.geojson")
        path.write_text(json.dumps(collection), encoding="utf-8")
        return path

    def _resolve_path(self, option, default_suffix):
        if option:
            path = settings.BASE_DIR.parent / option
        else:
            directory = settings.EXPERIMENTS_DIR
            path = directory / f"{datetime.now(UTC):%Y%m%d-%H%M%S}-{default_suffix}"
        path.parent.mkdir(parents=True, exist_ok=True)
        return path

    def _print_report(
        self,
        dataset,
        solution,
        strategy,
        penalties,
        rows,
        summary,
        coverage,
        worst_pair,
        dropped,
        csv_path,
        geojson_path,
        worst_pair_path,
    ):
        w = self.stdout.write
        w(f"Dataset {dataset.id} ({dataset.name})")
        w(f"strategy={strategy} k={solution.total_routes} dropped={len(dropped)}")
        w(
            f"soft_lower_penalty={penalties.soft_lower_penalty} "
            f"soft_upper_target={penalties.soft_upper_target} "
            f"soft_upper_penalty={penalties.soft_upper_penalty}"
        )
        w("")
        w(",".join(AUDIT_COLUMNS))
        for row in rows:
            w(",".join(str(row[column]) for column in AUDIT_COLUMNS))

        route_rows = rows[:-1]
        worst_walk = max(route_rows, key=lambda row: row["walk_ratio"])
        worst_shortfall = max(route_rows, key=lambda row: row["shortfall_sec"])
        w("")
        w(f"walk_ratio aggregate: {summary['walk_ratio']}")
        w(
            f"walk_ratio worst: {worst_walk['walk_ratio']} "
            f"(route {worst_walk['route']})"
        )
        w(
            f"shortfall total: {summary['shortfall_sec']}s "
            f"(worst route {worst_shortfall['route']}: "
            f"{worst_shortfall['shortfall_sec']}s)"
        )
        if coverage:
            w(
                f"T_min gap coverage: mean {round(mean(coverage), 3)} over "
                f"{len(coverage)} routes with service below T_min "
                f"(min {min(coverage)}, max {max(coverage)})"
            )
        w(f"saturation mean: {summary['saturation']}")
        w(f"self_crossings total: {summary['self_crossings']}")
        if worst_pair:
            first, second, iou = worst_pair
            w(
                f"worst overlap pair: routes {first['row']['route']} and "
                f"{second['row']['route']} (bbox IoU {iou})"
            )
        w("")
        w(f"CSV: {csv_path}")
        w(f"GeoJSON: {geojson_path}")
        if worst_pair_path:
            w(f"Worst-pair GeoJSON: {worst_pair_path}")
