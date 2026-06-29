import random
from statistics import mean

from apps.optimization.dataset_factory import (
    DISTRIBUTIONS,
    create_dataset,
    generate_points,
)
from apps.optimization.experiment_log import record_experiment
from apps.optimization.models import OptimizationJob, RoutingConfig, RoutingSolution
from apps.optimization.pipeline import SOLVER_TIME_LIMIT_SEC, OptimizationPipeline
from apps.optimization.route_metrics import (
    interleave_per_route,
    routes_from_solution,
    sum_max_radius,
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
        parser.add_argument(
            "--strategy",
            choices=[s.value for s in RoutingSolution.Strategy],
            default=RoutingSolution.Strategy.GLOBAL.value,
        )

    def handle(self, *args, **options):
        sizes = [int(s) for s in options["sizes"].split(",")]
        seeds = [options["base_seed"] + i for i in range(options["seeds"])]
        distribution = options["distribution"]
        clusters = options["clusters"]
        strategy = options["strategy"]

        self.stdout.write(
            f"Sweep strategy={strategy} distribution={distribution} "
            f"sizes={sizes} seeds={seeds}"
        )
        rows = []
        for n in sizes:
            runs = [
                self._run(n, seed, distribution, clusters, strategy) for seed in seeds
            ]
            row = {key: mean(r[key] for r in runs) for key in runs[0]}
            rows.append((n, row))
            self.stdout.write(
                f"n={n}: k={row['k']:.1f} balance={row['balance']:.3f} "
                f"sum_rmax={row['sum_rmax']:.0f} interleave={row['interleave']:.1f} "
                f"interleave_pr={row['interleave_pr']:.2f} worst_iou={row['worst_iou']:.2f}"
            )

        self.stdout.write("")
        self.stdout.write(
            "LaTeX rows (n & k & balance & sum_rmax & interleave & solap_pr & worst_iou):"
        )
        for n, row in rows:
            self.stdout.write(
                f"    {n} & {row['k']:.1f} & {row['balance']:.3f} & "
                f"{row['sum_rmax']:.0f} & {row['interleave']:.1f} & "
                f"{row['interleave_pr']:.2f} & {row['worst_iou']:.2f} \\\\"
            )

        report_path = self._record(rows, options, seeds, distribution, strategy)
        self.stdout.write("")
        self.stdout.write(f"Experiment report: {report_path}")

    def _record(self, rows, options, seeds, distribution, strategy):
        table = [
            "| n | k | balance | sum_rmax [m] | solap. total | solap./ruta | IoU peor par |",
            "| --- | --- | --- | --- | --- | --- | --- |",
        ]
        for n, row in rows:
            table.append(
                f"| {n} | {row['k']:.1f} | {row['balance']:.3f} | "
                f"{row['sum_rmax']:.0f} | {row['interleave']:.1f} | "
                f"{row['interleave_pr']:.2f} | {row['worst_iou']:.2f} |"
            )
        return record_experiment(
            slug="baseline-sweep",
            title=f"Baseline geográfico VRP {strategy} · {distribution}",
            command="manage.py baseline_sweep",
            params={
                "strategy": strategy,
                "sizes": options["sizes"],
                "seeds": len(seeds),
                "distribution": distribution,
                "solver_time_limit_sec": SOLVER_TIME_LIMIT_SEC,
            },
            metrics={"semillas": len(seeds), "tamaños": options["sizes"]},
            analysis={
                "que_ocurrio": "\n".join(
                    [
                        "Media por tamaño de dataset sobre el barrido:",
                        "",
                        *table,
                    ]
                ),
                "por_que": (
                    "El modelo resuelve un único Open mTSP global que minimiza el "
                    "tiempo total con una penalización blanda de balance temporal, sin "
                    "ningún criterio espacial explícito en la partición de nodos. Las "
                    "rutas se forman por proximidad temporal, no geográfica."
                ),
                "posibles_causas": [
                    "Ausencia de término espacial en la función objetivo.",
                    "El balance blando premia rutas de duración similar aunque se "
                    "entrelacen geográficamente.",
                    "Mayor densidad de nodos aumenta la probabilidad de que una ruta "
                    "compacta quede contenida en la caja de otra más extensa.",
                ],
                "hipotesis": [
                    "H1: un preprocesamiento de clustering geográfico (resolver un VRP "
                    "por cluster) reduce el solapamiento por ruta sin degradar el "
                    "balance temporal.",
                    "H2: el solapamiento crece de forma monótona con la densidad de "
                    "nodos independientemente de la semilla.",
                    "H3: añadir un término de compacidad espacial al objetivo reduce "
                    "el IoU del peor par a costa de mayor tiempo total.",
                ],
                "como_validar": [
                    "H1: correr `baseline_sweep --distribution clustered` y comparar "
                    "interleave_per_route contra uniform a igual n.",
                    "H2: inspeccionar la dispersión por semilla (no solo la media) en "
                    "cada tamaño.",
                    "H3: implementar el término espacial y re-medir sum_max_radius, "
                    "interleave y balance.",
                ],
                "soluciones": [
                    "Clustering geográfico como preprocesamiento (k-means / DBSCAN) y "
                    "un VRP por cluster.",
                    "Penalización de compacidad espacial en el objetivo del solver.",
                    "Restricciones de zona (capacidad por sector) en OR-Tools.",
                ],
                "experimentos": [
                    "Comparar uniform vs clustered vs multizone con baseline_sweep.",
                    "Medir el trade-off tiempo-total vs solapamiento al variar el peso "
                    "del término espacial.",
                ],
            },
        )

    def _run(self, n, seed, distribution, clusters, strategy):
        rng = random.Random(seed)
        points = generate_points(rng, n, distribution, clusters)
        with transaction.atomic():
            dataset = create_dataset(f"Sweep n{n} s{seed}", points)
            config = RoutingConfig.objects.create(dataset=dataset)
            job = OptimizationJob.objects.create(config=config)

        job.set_status("running")
        metrics = OptimizationPipeline(job).run(strategy=strategy)
        job.set_completed(metrics)

        solution = RoutingSolution.objects.get(job=job, strategy=strategy)
        analyzed = routes_from_solution(solution)
        return {
            "k": float(solution.total_routes),
            "balance": solution.balance_score,
            "sum_rmax": sum_max_radius(analyzed),
            "interleave": float(total_interleave(analyzed)),
            "interleave_pr": interleave_per_route(analyzed),
            "worst_iou": worst_pair_iou(analyzed),
        }
