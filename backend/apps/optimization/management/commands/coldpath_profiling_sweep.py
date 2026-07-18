import csv
from datetime import UTC, datetime
from statistics import mean

from apps.datasets.instances import instances_dir, load_instance
from apps.datasets.models import DistanceMatrix, Tree
from apps.optimization.experiment_log import record_experiment
from apps.optimization.models import OptimizationJob, RoutingConfig, RoutingSolution
from apps.optimization.pipeline import OptimizationPipeline
from apps.optimization.profiling import PHASE_SCHEMA
from django.conf import settings
from django.core.management.base import BaseCommand
from django.db import transaction

CENSUS_SERVICE_TIME_SEC = 120
CENSUS_MIN_ROUTE_TIME_SEC = 7200
CENSUS_MAX_ROUTE_TIME_SEC = 10800
COLD_TIME_LIMIT_SEC = 5

BATTERY_SLUGS = [
    "battery-n50",
    "battery-n100",
    "battery-n200",
    "battery-n400",
    "battery-n800",
    "battery-n1000",
    "battery-sparse-n250",
    "battery-sparse-n500",
]

DEFAULT_STRATEGIES = "global,spatial_term"

TIMING_COLUMNS = [
    f"{group}.{name}" for group, names in PHASE_SCHEMA.items() for name in names
] + ["pipeline_total"]

CSV_COLUMNS = ["slug", "n_trees", "strategy", *TIMING_COLUMNS]


class Command(BaseCommand):
    help = (
        "Cold-path branch profiling sweep: measures time per PhaseTimer sub-phase "
        "on real frozen battery instances with OSRM cache forced cold each run. "
        "Use --time-limit 5 (default) to minimise solve time; the focus is the "
        "cold path (cost_matrix + model_build), not solution quality."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--slugs",
            type=str,
            default=",".join(BATTERY_SLUGS),
            help="Comma-separated instance slugs (default: all battery instances)",
        )
        parser.add_argument(
            "--strategies",
            type=str,
            default=DEFAULT_STRATEGIES,
            help="Comma-separated strategies: global,spatial_term,cluster_first",
        )
        parser.add_argument(
            "--time-limit",
            type=int,
            default=COLD_TIME_LIMIT_SEC,
            help="Solver time limit in seconds (default 5 — minimise solve wait)",
        )
        parser.add_argument("--csv", type=str, default=None)

    def handle(self, *_args, **options):
        slugs = [s.strip() for s in options["slugs"].split(",") if s.strip()]
        strategies = [s.strip() for s in options["strategies"].split(",") if s.strip()]
        time_limit = options["time_limit"]

        inst_dir = instances_dir()
        rows = []

        for slug in slugs:
            path = inst_dir / f"{slug}.csv"
            if not path.exists():
                self.stdout.write(f"skip {slug}: {path} not found")
                continue
            dataset = load_instance(path)
            n_trees = Tree.objects.filter(dataset=dataset, is_active=True).count()
            self.stdout.write(f"loaded {slug} n={n_trees} ({dataset.id})")

            for strategy in strategies:
                DistanceMatrix.objects.filter(dataset=dataset).delete()
                row = self._run(dataset, strategy, time_limit)
                row["slug"] = slug
                row["n_trees"] = n_trees
                row["strategy"] = strategy
                rows.append(row)
                self.stdout.write(
                    f"  {strategy}: "
                    f"osrm={row['cost_matrix.osrm_fetch']:.2f}s "
                    f"hash={row['cost_matrix.hash']:.3f}s "
                    f"persist={row['cost_matrix.persist']:.2f}s "
                    f"geo={row['model_build.geo_matrix']:.3f}s "
                    f"disj={row['model_build.disjunctions']:.3f}s "
                    f"vbounds={row['model_build.vehicle_bounds']:.3f}s "
                    f"total={row['pipeline_total']:.2f}s"
                )

        csv_path = self._write_csv(rows, options["csv"])
        analysis = self._build_analysis(rows)
        report_path = record_experiment(
            slug="coldpath-profiling-sweep",
            title="Perfil camino frío: sub-fases PhaseTimer por rama vs n",
            command="manage.py coldpath_profiling_sweep",
            params={
                "slugs": options["slugs"],
                "strategies": options["strategies"],
                "time_limit_sec": time_limit,
                "csv": str(csv_path),
            },
            metrics={"corridas": len(rows), "csv": f"`{csv_path}`"},
            analysis=analysis,
        )
        self.stdout.write(f"\nCSV: {csv_path}")
        self.stdout.write(f"Experiment report: {report_path}")

    def _run(self, dataset, strategy, time_limit):
        with transaction.atomic():
            config = RoutingConfig.objects.create(
                dataset=dataset,
                service_time_sec=CENSUS_SERVICE_TIME_SEC,
                max_route_time_sec=CENSUS_MAX_ROUTE_TIME_SEC,
                min_route_time_sec=CENSUS_MIN_ROUTE_TIME_SEC,
            )
            job = OptimizationJob.objects.create(config=config, strategy=strategy)

        job.set_status("running")
        metrics = OptimizationPipeline(job).run(
            strategy=strategy, time_limit_sec=time_limit
        )
        job.set_completed(metrics)

        solution = RoutingSolution.objects.filter(job=job, strategy=strategy).first()
        if solution is None or solution.timing is None:
            return dict.fromkeys(TIMING_COLUMNS, 0.0)

        timing = solution.timing
        row = {}
        for column in TIMING_COLUMNS:
            if column == "pipeline_total":
                row[column] = round(timing.get("pipeline_total", 0.0), 3)
            else:
                group, name = column.split(".", 1)
                row[column] = round(timing.get(group, {}).get(name, 0.0), 3)
        return row

    def _write_csv(self, rows, csv_option):
        if csv_option:
            path = settings.BASE_DIR.parent / csv_option
        else:
            directory = settings.EXPERIMENTS_DIR
            directory.mkdir(parents=True, exist_ok=True)
            path = (
                directory
                / f"{datetime.now(UTC):%Y%m%d%H%M%S}-coldpath-profiling-sweep.csv"
            )
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=CSV_COLUMNS)
            writer.writeheader()
            writer.writerows(rows)
        return path

    def _build_analysis(self, rows):
        if not rows:
            return {"que_ocurrio": "_Sin datos._"}

        timing_cols = [
            ("cost_matrix.osrm_fetch", "osrm_fetch"),
            ("cost_matrix.single_request", "single_req"),
            ("cost_matrix.chunked_diagonal", "chk_diag"),
            ("cost_matrix.chunked_offdiagonal", "chk_offdiag"),
            ("cost_matrix.hash", "hash"),
            ("cost_matrix.persist", "persist"),
            ("model_build.geo_matrix", "geo_matrix"),
            ("model_build.disjunctions", "disjunctions"),
            ("model_build.vehicle_bounds", "veh_bounds"),
            ("model_build.search_params", "search_params"),
            ("model_build.total", "model_build"),
            ("solve.total", "solve"),
            ("pipeline_total", "total"),
        ]

        lines = ["### Sub-fases PhaseTimer por rama vs n", ""]
        header = (
            "| n | strategy | " + " | ".join(label for _, label in timing_cols) + " |"
        )
        sep = "| " + " | ".join(["---"] * (len(timing_cols) + 2)) + " |"
        lines.append(header)
        lines.append(sep)

        for r in sorted(rows, key=lambda x: (x["strategy"], x["n_trees"])):
            vals = " | ".join(f"{r[col]:.3f}" for col, _ in timing_cols)
            lines.append(f"| {r['n_trees']} | {r['strategy']} | {vals} |")

        lines.append("")
        lines.append("### Resumen por sub-fase (media sobre instancias)")
        lines.append("")

        for strategy in sorted({r["strategy"] for r in rows}):
            srows = [r for r in rows if r["strategy"] == strategy]
            lines.append(
                f"**{strategy}**: "
                + ", ".join(
                    f"{label}={mean(r[col] for r in srows):.3f}s"
                    for col, label in timing_cols
                )
            )

        return {"que_ocurrio": "\n".join(lines)}
