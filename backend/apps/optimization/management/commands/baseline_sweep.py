import random
from statistics import mean

from apps.optimization.demo_seed import DISTRIBUTIONS, create_dataset, generate_points
from apps.optimization.models import OptimizationJob, RoutingConfig, RoutingSolution
from apps.optimization.pipeline import OptimizationPipeline
from apps.optimization.route_metrics import (
    interleave_per_route,
    sum_max_radius,
    summarize_route,
    total_interleave,
    worst_pair_iou,
)
from django.core.management.base import BaseCommand
from django.db import transaction


class Command(BaseCommand):
    help = "Run a reproducible seed x size sweep and report mean geographic-quality metrics"

    def add_arguments(self, parser):
        parser.add_argument("--sizes", type=str, default="20,40,80")
        parser.add_argument("--seeds", type=int, default=5)
        parser.add_argument("--base-seed", type=int, default=42)
        parser.add_argument("--distribution", choices=DISTRIBUTIONS, default="uniform")
        parser.add_argument("--clusters", type=int, default=4)

    def handle(self, *args, **options):
        sizes = [int(s) for s in options["sizes"].split(",")]
        seeds = [options["base_seed"] + i for i in range(options["seeds"])]
        distribution = options["distribution"]
        clusters = options["clusters"]

        self.stdout.write(
            f"Sweep distribution={distribution} sizes={sizes} seeds={seeds}"
        )
        rows = []
        for n in sizes:
            runs = [self._run(n, seed, distribution, clusters) for seed in seeds]
            row = {key: mean(r[key] for r in runs) for key in runs[0]}
            rows.append((n, row))
            self.stdout.write(
                f"n={n}: k={row['k']:.1f} balance={row['balance']:.3f} "
                f"sum_rmax={row['sum_rmax']:.0f} interleave={row['interleave']:.1f} "
                f"interleave_pr={row['interleave_pr']:.2f} worst_iou={row['worst_iou']:.2f}"
            )

        self.stdout.write("")
        self.stdout.write(
            "LaTeX rows (n & k & balance & sum_rmax & interleave & worst_iou):"
        )
        for n, row in rows:
            self.stdout.write(
                f"    {n} & {row['k']:.1f} & {row['balance']:.3f} & "
                f"{row['sum_rmax']:.0f} & {row['interleave']:.1f} & "
                f"{row['worst_iou']:.2f} \\\\"
            )

    def _run(self, n, seed, distribution, clusters):
        rng = random.Random(seed)
        points = generate_points(rng, n, distribution, clusters)
        with transaction.atomic():
            dataset = create_dataset(f"Sweep n{n} s{seed}", points)
            config = RoutingConfig.objects.create(dataset=dataset)
            job = OptimizationJob.objects.create(config=config)

        job.set_status("running")
        metrics = OptimizationPipeline(job).run()
        job.set_completed(metrics)

        solution = RoutingSolution.objects.get(id=metrics["solution_id"])
        analyzed = []
        for route in solution.routes.order_by("route_number"):
            stops = list(route.stops.select_related("tree").order_by("sequence"))
            coords = [(s.tree.location.y, s.tree.location.x) for s in stops]
            if not coords:
                continue
            analyzed.append(summarize_route([s.sequence for s in stops], coords))

        return {
            "k": float(solution.total_routes),
            "balance": solution.balance_score,
            "sum_rmax": sum_max_radius(analyzed),
            "interleave": float(total_interleave(analyzed)),
            "interleave_pr": interleave_per_route(analyzed),
            "worst_iou": worst_pair_iou(analyzed),
        }
