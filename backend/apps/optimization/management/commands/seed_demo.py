import argparse
import random

from apps.optimization.dataset_factory import (
    DISTRIBUTIONS,
    create_dataset,
    generate_points,
    snap_to_streets,
)
from apps.optimization.experiment_log import record_experiment
from apps.optimization.models import OptimizationJob, RoutingConfig, RoutingSolution
from apps.optimization.pipeline import OptimizationPipeline
from apps.optimization.route_metrics import aggregate_metrics, routes_from_solution
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

SEED = 42

PROFILES = {"light": 15, "medium": 50, "heavy": 200}
PROFILE_OPTIMIZES = {"light": False, "medium": True, "heavy": True}


class Command(BaseCommand):
    help = "Seed a reproducible Santiago dataset and optionally run the optimization pipeline against real OSRM"

    def add_arguments(self, parser):
        parser.add_argument("--profile", choices=PROFILES, default=None)
        parser.add_argument("--trees", type=int, default=40)
        parser.add_argument("--name", type=str, default="Demo Santiago")
        parser.add_argument("--seed", type=int, default=SEED)
        parser.add_argument("--distribution", choices=DISTRIBUTIONS, default="uniform")
        parser.add_argument("--clusters", type=int, default=4)
        parser.add_argument("--snap", action="store_true")
        parser.add_argument(
            "--optimize", action=argparse.BooleanOptionalAction, default=None
        )

    def handle(self, *args, **options):
        profile = options["profile"]
        n_trees = PROFILES[profile] if profile else options["trees"]
        optimize = options["optimize"]
        if optimize is None:
            optimize = PROFILE_OPTIMIZES[profile] if profile else True

        if n_trees < 2:
            raise CommandError("--trees must be at least 2")
        if options["clusters"] < 1:
            raise CommandError("--clusters must be at least 1")

        rng = random.Random(options["seed"])
        points = generate_points(
            rng, n_trees, options["distribution"], options["clusters"]
        )
        if options["snap"]:
            points = snap_to_streets(points)

        dataset = create_dataset(options["name"], points)

        if not optimize:
            w = self.stdout.write
            w(self.style.SUCCESS(f"Dataset {dataset.id} ({dataset.total_trees} trees)"))
            w("Optimization skipped (--no-optimize)")
            return

        with transaction.atomic():
            config = RoutingConfig.objects.create(dataset=dataset)
            job = OptimizationJob.objects.create(config=config)

        try:
            job.set_status("running")
            metrics = OptimizationPipeline(job).run()
            job.set_completed(metrics)
        except Exception as exc:
            job.set_error(str(exc))
            raise CommandError(f"Optimization failed: {exc}") from exc

        report_path = self._record(metrics, options, n_trees, profile)
        self._print_summary(dataset, job, metrics, report_path)

    def _record(self, metrics, options, n_trees, profile):
        solution = RoutingSolution.objects.get(id=metrics["solution_id"])
        geo = aggregate_metrics(routes_from_solution(solution))
        return record_experiment(
            slug="seed-demo",
            title=f"seed_demo · {n_trees} árboles · {options['distribution']}",
            command="manage.py seed_demo",
            params={
                "profile": profile or "(custom)",
                "trees": n_trees,
                "seed": options["seed"],
                "distribution": options["distribution"],
                "snap": options["snap"],
            },
            metrics={
                "total_routes": metrics["total_routes"],
                "total_travel_time_sec": round(metrics["total_travel_time_sec"]),
                "balance_score": round(metrics["balance_score"], 3),
                "max_vehicles_estimated": metrics["max_vehicles_estimated"],
                **geo,
            },
            analysis={
                "que_ocurrio": (
                    f"Se sembró un dataset de {n_trees} árboles "
                    f"({options['distribution']}) y se resolvió el Open mTSP global, "
                    f"produciendo {metrics['total_routes']} rutas con balance "
                    f"{metrics['balance_score']:.3f}."
                )
            },
        )

    def _print_summary(self, dataset, job, metrics, report_path):
        w = self.stdout.write
        w(self.style.SUCCESS(f"Dataset {dataset.id} ({dataset.total_trees} trees)"))
        w(f"Job {job.id} -> {job.status}")
        w("")

        for route in job.solution.routes.all().order_by("route_number"):
            w(
                f"Route {route.route_number}: "
                f"{route.total_trees} trees, "
                f"travel {route.travel_time_sec}s, "
                f"total {route.total_estimated_time_sec}s"
            )

        w("")
        w(f"Routes: {metrics['total_routes']}")
        w(f"Total travel time: {metrics['total_travel_time_sec']:.0f}s")
        w(f"Balance score: {metrics['balance_score']:.3f}")
        w(f"Max vehicles estimated: {metrics['max_vehicles_estimated']}")
        w(f"Experiment report: {report_path}")
