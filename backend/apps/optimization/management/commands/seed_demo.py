import random

from apps.optimization.demo_seed import (
    DISTRIBUTIONS,
    create_dataset,
    generate_points,
    snap_to_streets,
)
from apps.optimization.models import OptimizationJob, RoutingConfig
from apps.optimization.pipeline import OptimizationPipeline
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

SEED = 42


class Command(BaseCommand):
    help = "Seed a reproducible Santiago dataset and run the optimization pipeline against real OSRM"

    def add_arguments(self, parser):
        parser.add_argument("--trees", type=int, default=40)
        parser.add_argument("--name", type=str, default="Demo Santiago")
        parser.add_argument("--seed", type=int, default=SEED)
        parser.add_argument("--distribution", choices=DISTRIBUTIONS, default="uniform")
        parser.add_argument("--clusters", type=int, default=4)
        parser.add_argument("--snap", action="store_true")

    def handle(self, *args, **options):
        n_trees = options["trees"]
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

        with transaction.atomic():
            dataset = create_dataset(options["name"], points)
            config = RoutingConfig.objects.create(dataset=dataset)
            job = OptimizationJob.objects.create(config=config)

        try:
            job.set_status("running")
            metrics = OptimizationPipeline(job).run()
            job.set_completed(metrics)
        except Exception as exc:
            job.set_error(str(exc))
            raise CommandError(f"Optimization failed: {exc}") from exc

        self._print_summary(dataset, job, metrics)

    def _print_summary(self, dataset, job, metrics):
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
