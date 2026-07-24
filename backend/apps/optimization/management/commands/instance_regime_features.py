import csv

from apps.datasets.instances import instances_dir, read_instance
from apps.optimization.instance_features import geometry_features, regime_features
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

CENSUS_SERVICE_TIME_SEC = 120
CENSUS_MIN_ROUTE_TIME_SEC = 7200
CENSUS_MAX_ROUTE_TIME_SEC = 10800

COLUMNS = [
    "instance",
    "n",
    "bbox_area_km2",
    "density_per_km2",
    "diameter_m",
    "extent_major_m",
    "extent_minor_m",
    "elongation",
    "service_total_sec",
    "nn_mean_sec",
    "k_hat",
    "msf_k_hat_sec",
    "work_lb_sec",
    "saturation_hat",
    "rho_pad",
]


class Command(BaseCommand):
    help = (
        "Geometric and structural features of the frozen instances, all computable "
        "before any solver run: extent, density, diameter, and the duration-floor "
        "regime ratio rho_pad = k_hat * T_min / work_lb. Reads coordinates from the "
        "frozen instance CSVs and reuses the published MSF_k decomposition, so it "
        "touches neither the solver nor OSRM."
    )

    def add_arguments(self, parser):
        parser.add_argument("--decomposition", type=str, required=True)
        parser.add_argument("--instance", type=str, nargs="+", required=True)
        parser.add_argument("--csv", type=str, required=True)

    def handle(self, *args, **options):
        root = settings.BASE_DIR.parent
        msf, nn_mean = self._decomposition(root / options["decomposition"])

        rows = []
        for slug in options["instance"]:
            path = instances_dir() / f"{slug}.csv"
            if not path.exists():
                raise CommandError(f"frozen instance not found: {path}")
            if slug not in msf:
                raise CommandError(f"decomposition CSV lacks MSF_k for {slug}")
            trees = read_instance(path)
            geometry = geometry_features([(t.lat, t.lon) for t in trees])
            service_total = len(trees) * CENSUS_SERVICE_TIME_SEC
            regime = regime_features(
                msf[slug],
                service_total,
                CENSUS_MIN_ROUTE_TIME_SEC,
                CENSUS_MAX_ROUTE_TIME_SEC,
            )
            rows.append(
                {
                    "instance": slug,
                    "n": geometry["n"],
                    "bbox_area_km2": round(geometry["bbox_area_km2"], 4),
                    "density_per_km2": round(geometry["density_per_km2"], 1),
                    "diameter_m": round(geometry["diameter_m"]),
                    "extent_major_m": round(geometry["extent_major_m"]),
                    "extent_minor_m": round(geometry["extent_minor_m"]),
                    "elongation": round(geometry["elongation"], 2),
                    "service_total_sec": service_total,
                    "nn_mean_sec": round(nn_mean[slug], 2),
                    "k_hat": regime["k_hat"],
                    "msf_k_hat_sec": round(msf[slug][regime["k_hat"]]),
                    "work_lb_sec": round(regime["work_lb_sec"]),
                    "saturation_hat": round(regime["saturation_hat"], 3),
                    "rho_pad": round(regime["rho_pad"], 3),
                }
            )
            self.stdout.write(
                f"{slug}: n={geometry['n']} k_hat={regime['k_hat']} "
                f"work_lb={regime['work_lb_sec']:.0f} "
                f"rho_pad={regime['rho_pad']:.3f} "
                f"density={geometry['density_per_km2']:.0f}/km2"
            )

        csv_path = root / options["csv"]
        csv_path.parent.mkdir(parents=True, exist_ok=True)
        with csv_path.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=COLUMNS)
            writer.writeheader()
            writer.writerows(rows)
        self.stdout.write(self.style.SUCCESS(f"Features CSV: {csv_path}"))

    def _decomposition(self, path):
        msf = {}
        nn_mean = {}
        with path.open(newline="", encoding="utf-8") as handle:
            for row in csv.DictReader(handle):
                msf.setdefault(row["instance"], {})[int(row["k"])] = float(
                    row["msf_k_sec"]
                )
                nn_mean[row["instance"]] = float(row["nn_mean_sec"])
        return msf, nn_mean
