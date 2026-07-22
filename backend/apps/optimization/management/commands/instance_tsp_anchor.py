import csv

from apps.datasets.instances import dataset_uuid
from apps.datasets.models import Dataset, Tree
from apps.optimization.bounds import (
    directed_path_travel,
    minimum_spanning_forest,
    path_travel,
    split_path,
    symmetric_mst_edges,
    symmetrized,
    tsp_path_order,
)
from apps.optimization.cost_matrix import OSRMCostMatrixBuilder
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

CENSUS_SERVICE_TIME_SEC = 120
CENSUS_MAX_ROUTE_TIME_SEC = 10800

COLUMNS = [
    "instance",
    "n",
    "k",
    "msf_k_sec",
    "ub_k_sec",
    "ub_k_directed_sec",
    "gap_sec",
    "gap_pct",
    "ub_max_route_dur_sec",
    "ub_routes_over_tmax",
    "ub_tmax_feasible",
    "tsp_time_limit_sec",
]


class Command(BaseCommand):
    help = (
        "Bracket the optimal travel of an instance from both sides. MSF_k (the "
        "minimum spanning tree minus its k-1 heaviest edges) lower-bounds it but is a "
        "relaxation no route can attain. UB_k applies the same cut to a near-optimal "
        "open TSP path, which leaves k open paths covering every node: a constructed, "
        "feasible set of routes. The gap between the two is the real uncertainty of "
        "any padding metric anchored on MSF_k."
    )

    def add_arguments(self, parser):
        parser.add_argument("--csv", type=str, required=True)
        parser.add_argument("--instance", type=str, nargs="+", required=True)
        parser.add_argument("--k-max", type=int, default=6)
        parser.add_argument(
            "--tsp-time-limit",
            type=int,
            default=120,
            help="Solver time limit for the open TSP path, in seconds",
        )

    def handle(self, *args, **options):
        rows = []
        for slug in options["instance"]:
            rows.extend(self._anchor(slug, options))

        csv_path = settings.BASE_DIR.parent / options["csv"]
        csv_path.parent.mkdir(parents=True, exist_ok=True)
        with csv_path.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=COLUMNS)
            writer.writeheader()
            writer.writerows(rows)
        self.stdout.write(self.style.SUCCESS(f"TSP anchor CSV: {csv_path}"))

    def _anchor(self, slug, options):
        try:
            dataset = Dataset.objects.get(id=dataset_uuid(slug))
        except Dataset.DoesNotExist as exc:
            raise CommandError(
                f"instance '{slug}' not loaded (run load_instances first)"
            ) from exc
        trees = sorted(
            Tree.objects.filter(dataset=dataset, is_active=True),
            key=lambda tree: tree.id,
        )
        matrix = OSRMCostMatrixBuilder().build(trees)
        n = len(trees)

        mst_edges = symmetric_mst_edges(matrix)
        time_limit = options["tsp_time_limit"]
        order = tsp_path_order(matrix, time_limit)
        if sorted(order) != list(range(n)):
            raise CommandError(
                f"{slug}: TSP path covers {len(set(order))} of {n} nodes"
            )
        symmetric = symmetrized(matrix)

        rows = []
        for k in range(1, options["k_max"] + 1):
            msf_k = minimum_spanning_forest(mst_edges, k)
            segments = split_path(order, matrix, k)
            ub_k = sum(path_travel(segment, symmetric) for segment in segments)
            ub_directed = sum(
                directed_path_travel(segment, matrix) for segment in segments
            )
            if ub_k < msf_k - 1e-6:
                raise CommandError(
                    f"{slug} k={k}: constructed path bound {ub_k:.0f} below the "
                    f"spanning-forest bound {msf_k:.0f} — one of them is wrong"
                )

            durations = [
                directed_path_travel(segment, matrix)
                + len(segment) * CENSUS_SERVICE_TIME_SEC
                for segment in segments
            ]
            over_tmax = sum(1 for d in durations if d > CENSUS_MAX_ROUTE_TIME_SEC)
            gap = ub_k - msf_k
            rows.append(
                {
                    "instance": slug,
                    "n": n,
                    "k": k,
                    "msf_k_sec": round(msf_k),
                    "ub_k_sec": round(ub_k),
                    "ub_k_directed_sec": round(ub_directed),
                    "gap_sec": round(gap),
                    "gap_pct": round(100 * gap / msf_k, 2) if msf_k else "",
                    "ub_max_route_dur_sec": round(max(durations)),
                    "ub_routes_over_tmax": over_tmax,
                    "ub_tmax_feasible": over_tmax == 0,
                    "tsp_time_limit_sec": time_limit,
                }
            )
            self.stdout.write(
                f"{slug} k={k} msf={msf_k:.0f} ub={ub_k:.0f} "
                f"gap={gap:.0f} ({100 * gap / msf_k:.1f}%) "
                f"max_dur={max(durations):.0f} over_tmax={over_tmax}"
            )
        return rows
