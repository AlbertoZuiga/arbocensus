import csv
import random
from datetime import UTC, datetime
from itertools import product
from statistics import mean, pstdev

from apps.datasets.models import Dataset, Tree
from apps.optimization.dataset_factory import (
    DISTRIBUTIONS,
    create_dataset,
    generate_points,
)
from apps.optimization.experiment_log import record_experiment
from apps.optimization.models import OptimizationJob, RoutingConfig, RoutingSolution
from apps.optimization.pipeline import SOLVER_TIME_LIMIT_SEC, OptimizationPipeline
from apps.optimization.profiling import PHASE_SCHEMA
from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

TIMING_COLUMNS = [
    f"{group}.{name}" for group, names in PHASE_SCHEMA.items() for name in names
] + ["pipeline_total"]

CSV_COLUMNS = [
    "target",
    "n_trees",
    "strategy",
    "service_time_min",
    "t_max_h",
    "seed",
    "time_limit_sec",
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
    *TIMING_COLUMNS,
]


class Command(BaseCommand):
    help = (
        "Reproducible sweep of strategy x service_time x t_max x seed over a real "
        "dataset (--dataset) or synthetic datasets (--sizes); reports "
        "route-quality metrics and per-phase timing as CSV + markdown. "
        "On a real dataset the seed only labels the repetition: variance comes "
        "from the solver's wall-clock time limit."
    )

    def add_arguments(self, parser):
        parser.add_argument("--dataset", type=str, default=None)
        parser.add_argument("--sizes", type=str, default="20,40,80")
        parser.add_argument("--seeds", type=int, default=5)
        parser.add_argument("--base-seed", type=int, default=42)
        parser.add_argument("--distribution", choices=DISTRIBUTIONS, default="uniform")
        parser.add_argument("--clusters", type=int, default=4)
        parser.add_argument(
            "--strategies",
            type=str,
            default=RoutingSolution.Strategy.GLOBAL.value,
            help="Comma-separated: global,spatial_term,cluster_first",
        )
        parser.add_argument(
            "--service-time",
            type=str,
            default="5",
            help="Comma-separated service time per tree in minutes",
        )
        parser.add_argument(
            "--t-max",
            type=str,
            default="3",
            help="Comma-separated max route duration in hours",
        )
        parser.add_argument(
            "--time-limit",
            type=int,
            default=None,
            help="Fixed solver time limit in seconds (default: pipeline heuristic)",
        )
        parser.add_argument("--csv", type=str, default=None)

    def handle(self, *args, **options):
        strategies = self._parse_strategies(options["strategies"])
        variants = self._parse_variants(options["service_time"], options["t_max"])
        seeds = [options["base_seed"] + i for i in range(options["seeds"])]
        time_limit = options["time_limit"]

        targets = self._build_targets(options, seeds)
        self.stdout.write(
            f"Sweep strategies={[s.value for s in strategies]} variants={variants} "
            f"seeds={seeds} time_limit={time_limit or 'auto'}"
        )

        rows = []
        for label, datasets_by_seed in targets:
            for strategy, (service_min, t_max_h) in product(strategies, variants):
                for seed in seeds:
                    run = self._run(
                        datasets_by_seed[seed],
                        strategy.value,
                        service_min,
                        t_max_h,
                        time_limit,
                    )
                    run.update(
                        target=label,
                        strategy=strategy.value,
                        service_time_min=service_min,
                        t_max_h=t_max_h,
                        seed=seed,
                    )
                    rows.append(run)
                    self.stdout.write(
                        f"{label} {strategy.value} st={service_min}m "
                        f"tmax={t_max_h}h seed={seed}: k={run['k']} "
                        f"balance={run['balance']:.3f} "
                        f"dropped={run['dropped_trees']} "
                        f"solve={run['solve.total']:.1f}s "
                        f"total={run['pipeline_total']:.1f}s"
                    )

        csv_path = self._write_csv(rows, options["csv"])
        table = self._summary_table(rows)
        self.stdout.write("")
        self.stdout.write("\n".join(table))

        report_path = record_experiment(
            slug="baseline-sweep",
            title="Sweep estrategia × service_time × T_max",
            command="manage.py baseline_sweep",
            params={
                "dataset": options["dataset"] or f"synthetic sizes={options['sizes']}",
                "strategies": options["strategies"],
                "service_time_min": options["service_time"],
                "t_max_h": options["t_max"],
                "seeds": len(seeds),
                "base_seed": options["base_seed"],
                "distribution": options["distribution"],
                "time_limit_sec": time_limit or f"auto (cap {SOLVER_TIME_LIMIT_SEC})",
                "csv": str(csv_path),
            },
            metrics={"corridas": len(rows), "csv": f"`{csv_path}`"},
            analysis={"que_ocurrio": "\n".join(["Media por grupo:", "", *table])},
        )
        self.stdout.write("")
        self.stdout.write(f"CSV: {csv_path}")
        self.stdout.write(f"Experiment report: {report_path}")

    def _parse_strategies(self, raw):
        valid = {s.value: s for s in RoutingSolution.Strategy}
        strategies = []
        for name in raw.split(","):
            name = name.strip()
            if name not in valid:
                raise CommandError(
                    f"Unknown strategy '{name}' (valid: {', '.join(valid)})"
                )
            strategies.append(valid[name])
        return strategies

    def _parse_variants(self, service_raw, t_max_raw):
        service_minutes = [float(v) for v in service_raw.split(",")]
        t_max_hours = [float(v) for v in t_max_raw.split(",")]
        return list(product(service_minutes, t_max_hours))

    def _build_targets(self, options, seeds):
        if options["dataset"]:
            try:
                dataset = Dataset.objects.get(id=options["dataset"])
            except (Dataset.DoesNotExist, ValidationError) as exc:
                raise CommandError(f"Dataset '{options['dataset']}' not found") from exc
            return [(dataset.name, dict.fromkeys(seeds, dataset))]
        targets = []
        for n in [int(s) for s in options["sizes"].split(",")]:
            datasets_by_seed = {}
            for seed in seeds:
                rng = random.Random(seed)
                points = generate_points(
                    rng, n, options["distribution"], options["clusters"]
                )
                with transaction.atomic():
                    datasets_by_seed[seed] = create_dataset(
                        f"Sweep n{n} s{seed}", points
                    )
            targets.append((f"n={n}", datasets_by_seed))
        return targets

    def _run(self, dataset, strategy, service_min, t_max_h, time_limit):
        service_time_sec = round(service_min * 60)
        max_route_time_sec = round(t_max_h * 3600)
        with transaction.atomic():
            config = RoutingConfig.objects.create(
                dataset=dataset,
                service_time_sec=service_time_sec,
                max_route_time_sec=max_route_time_sec,
                min_route_time_sec=min(
                    RoutingConfig.DEFAULT_MIN_ROUTE_TIME_SEC, max_route_time_sec
                ),
            )
            job = OptimizationJob.objects.create(config=config, strategy=strategy)

        job.set_status("running")
        metrics = OptimizationPipeline(job).run(
            strategy=strategy, time_limit_sec=time_limit
        )
        job.set_completed(metrics)

        solution = RoutingSolution.objects.get(job=job, strategy=strategy)
        route_times = [
            route.total_estimated_time_sec
            for route in solution.routes.order_by("route_number")
        ]
        row = {
            "n_trees": Tree.objects.filter(dataset=dataset, is_active=True).count(),
            "time_limit_sec": time_limit or "auto",
            "k": solution.total_routes,
            "balance": solution.balance_score,
            "total_travel_time_sec": round(solution.total_travel_time_sec),
            "route_time_mean_sec": round(mean(route_times)) if route_times else 0,
            "route_time_std_sec": round(pstdev(route_times)) if route_times else 0,
            "routes_over_t_max": sum(1 for t in route_times if t > max_route_time_sec),
            "dropped_trees": len(metrics["dropped_trees"]),
            "sum_max_radius_m": solution.sum_max_radius_m,
            "interleave_total": solution.interleave_total,
            "interleave_per_route": solution.interleave_per_route,
            "worst_pair_iou": solution.worst_pair_iou,
        }
        timing = solution.timing or {}
        for column in TIMING_COLUMNS:
            if column == "pipeline_total":
                row[column] = round(timing.get("pipeline_total", 0.0), 3)
            else:
                group, name = column.split(".")
                row[column] = round(timing.get(group, {}).get(name, 0.0), 3)
        return row

    def _write_csv(self, rows, csv_option):
        if csv_option:
            path = settings.BASE_DIR.parent / csv_option
        else:
            directory = settings.EXPERIMENTS_DIR
            directory.mkdir(parents=True, exist_ok=True)
            path = directory / f"{datetime.now(UTC):%Y%m%d-%H%M%S}-baseline-sweep.csv"
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=CSV_COLUMNS)
            writer.writeheader()
            writer.writerows(rows)
        return path

    def _summary_table(self, rows):
        groups = {}
        for row in rows:
            key = (
                row["target"],
                row["strategy"],
                row["service_time_min"],
                row["t_max_h"],
            )
            groups.setdefault(key, []).append(row)

        numeric = [
            "k",
            "balance",
            "route_time_mean_sec",
            "route_time_std_sec",
            "routes_over_t_max",
            "dropped_trees",
            "total_travel_time_sec",
            "sum_max_radius_m",
            "interleave_per_route",
            "worst_pair_iou",
            "solve.total",
            "pipeline_total",
        ]
        table = [
            "| target | strategy | st [min] | T_max [h] | k | balance | T̄ [s] | "
            "σ [s] | >T_max | dropped | travel [s] | sum_rmax [m] | solap./ruta | "
            "IoU peor par | solve [s] | total [s] |",
            "| " + " | ".join(["---"] * 16) + " |",
        ]
        for key, runs in groups.items():
            avg = {col: mean(r[col] for r in runs) for col in numeric}
            table.append(
                f"| {key[0]} | {key[1]} | {key[2]:g} | {key[3]:g} | "
                f"{avg['k']:.1f} | {avg['balance']:.3f} | "
                f"{avg['route_time_mean_sec']:.0f} | {avg['route_time_std_sec']:.0f} | "
                f"{avg['routes_over_t_max']:.1f} | {avg['dropped_trees']:.1f} | "
                f"{avg['total_travel_time_sec']:.0f} | {avg['sum_max_radius_m']:.0f} | "
                f"{avg['interleave_per_route']:.2f} | {avg['worst_pair_iou']:.2f} | "
                f"{avg['solve.total']:.1f} | {avg['pipeline_total']:.1f} |"
            )
        return table
