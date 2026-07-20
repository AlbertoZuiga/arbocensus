import csv

from apps.datasets.instances import dataset_uuid
from apps.datasets.models import Dataset, Tree
from apps.optimization.bounds import minimum_spanning_forest, symmetric_mst_edges
from apps.optimization.cost_matrix import OSRMCostMatrixBuilder
from apps.optimization.n_estimator import mean_nearest_neighbor_travel
from apps.optimization.solver import build_open_matrix
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

CENSUS_SERVICE_TIME_SEC = 120
CENSUS_MIN_ROUTE_TIME_SEC = 7200
CENSUS_MAX_ROUTE_TIME_SEC = 10800

COLUMNS = [
    "instance",
    "n",
    "k",
    "service_total_sec",
    "nn_mean_sec",
    "nn_lower_bound_sec",
    "msf_k_sec",
    "floor_travel_lb_sec",
    "travel_lb_sec",
    "travel_ub_tmax_sec",
    "feasible",
    "saturation_apriori",
    "relleno_lb_sec",
]


class Command(BaseCommand):
    help = (
        "Structural decomposition of a frozen instance: for each fleet size k, the "
        "minimum travel any set of k open routes can achieve (minimum spanning "
        "forest bound), the travel a duration floor forces, the T_max feasibility "
        "ceiling, and the resulting lower bound on the sweep's relleno metric. "
        "Answers whether a relleno target is reachable at all before any arm is run."
    )

    def add_arguments(self, parser):
        parser.add_argument("--csv", type=str, required=True)
        parser.add_argument("--instance", type=str, nargs="+", required=True)
        parser.add_argument("--k-max", type=int, default=6)
        parser.add_argument(
            "--floor",
            type=int,
            nargs="+",
            default=[0, CENSUS_MIN_ROUTE_TIME_SEC],
            help="Per-route duration floors to evaluate, in seconds",
        )

    def handle(self, *args, **options):
        rows = []
        for slug in options["instance"]:
            rows.extend(self._decompose(slug, options))

        csv_path = settings.BASE_DIR.parent / options["csv"]
        csv_path.parent.mkdir(parents=True, exist_ok=True)
        with csv_path.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=COLUMNS)
            writer.writeheader()
            writer.writerows(rows)
        self.stdout.write(self.style.SUCCESS(f"Decomposition CSV: {csv_path}"))

    def _decompose(self, slug, options):
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
        open_matrix = build_open_matrix(matrix)
        n = len(trees)
        nn_mean = mean_nearest_neighbor_travel(open_matrix)
        service_total = n * CENSUS_SERVICE_TIME_SEC

        mst_edges = symmetric_mst_edges(matrix)

        rows = []
        for k in range(1, options["k_max"] + 1):
            # k open paths spanning n nodes form a spanning forest of k components,
            # so dropping the k-1 heaviest MST edges lower-bounds their total travel.
            msf_k = minimum_spanning_forest(mst_edges, k)
            nn_lb = max(0, n - k) * nn_mean
            ub_tmax = k * CENSUS_MAX_ROUTE_TIME_SEC - service_total
            for floor in options["floor"]:
                floor_lb = max(0, k * floor - service_total)
                travel_lb = max(msf_k, floor_lb)
                rows.append(
                    {
                        "instance": slug,
                        "n": n,
                        "k": k,
                        "service_total_sec": service_total,
                        "nn_mean_sec": round(nn_mean, 2),
                        "nn_lower_bound_sec": round(nn_lb),
                        "msf_k_sec": round(msf_k),
                        "floor_travel_lb_sec": round(floor_lb),
                        "travel_lb_sec": round(travel_lb),
                        "travel_ub_tmax_sec": ub_tmax,
                        "feasible": travel_lb <= ub_tmax,
                        "saturation_apriori": round(
                            service_total / (k * CENSUS_MAX_ROUTE_TIME_SEC), 3
                        ),
                        "relleno_lb_sec": round(max(0, travel_lb - nn_lb)),
                    }
                )
                self.stdout.write(
                    f"k={k} floor={floor} msf={msf_k:.0f} nn_lb={nn_lb:.0f} "
                    f"travel_lb={travel_lb:.0f} ub_tmax={ub_tmax} "
                    f"relleno_lb={max(0, travel_lb - nn_lb):.0f} "
                    f"feasible={travel_lb <= ub_tmax}"
                )
        return rows
