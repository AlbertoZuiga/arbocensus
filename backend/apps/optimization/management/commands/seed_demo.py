import random

from apps.datasets.models import Dataset, Tree
from apps.optimization.models import OptimizationJob, RoutingConfig
from apps.optimization.pipeline import OptimizationPipeline
from django.contrib.gis.geos import Point
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

SEED = 42
LAT_MIN, LAT_MAX = -33.45, -33.41
LON_MIN, LON_MAX = -70.66, -70.58


class Command(BaseCommand):
    help = "Seed a reproducible Santiago dataset and run the optimization pipeline against real OSRM"

    def add_arguments(self, parser):
        parser.add_argument("--trees", type=int, default=40)
        parser.add_argument("--name", type=str, default="Demo Santiago")
        parser.add_argument("--seed", type=int, default=SEED)

    def handle(self, *args, **options):
        n_trees = options["trees"]
        if n_trees < 2:
            raise CommandError("--trees must be at least 2")

        rng = random.Random(options["seed"])

        with transaction.atomic():
            dataset = Dataset.objects.create(name=options["name"])
            trees = [
                Tree(
                    dataset=dataset,
                    location=Point(
                        rng.uniform(LON_MIN, LON_MAX),
                        rng.uniform(LAT_MIN, LAT_MAX),
                    ),
                )
                for _ in range(n_trees)
            ]
            Tree.objects.bulk_create(trees)
            dataset.total_trees = n_trees
            dataset.save(update_fields=["total_trees"])

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
