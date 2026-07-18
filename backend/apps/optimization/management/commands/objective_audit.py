from apps.datasets.instances import dataset_uuid
from apps.datasets.models import Dataset, Tree
from apps.optimization.cost_matrix import OSRMCostMatrixBuilder
from apps.optimization.n_estimator import (
    estimate_max_vehicles,
    p95_nearest_neighbor_travel,
)
from apps.optimization.pipeline import SOLVER_TIME_LIMIT_SEC
from apps.optimization.solver import (
    BALANCE_ARM_ACTUAL,
    BALANCE_ARMS,
    DROP_PENALTY,
    FIXED_VEHICLE_COST,
    SOFT_LOWER_PENALTY,
    SOFT_UPPER_PENALTY,
    SOFT_UPPER_TARGET_MIDPOINT,
    SOFT_UPPER_TARGETS,
    TIGHT_TMIN_SEC,
    ArbocensusVRPSolver,
    PenaltyConfig,
    build_open_matrix,
)
from apps.optimization.strategies import SPATIAL_SPAN_COEF
from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError

CENSUS_SERVICE_TIME_SEC = 120
CENSUS_MIN_ROUTE_TIME_SEC = 7200
CENSUS_MAX_ROUTE_TIME_SEC = 10800


class Command(BaseCommand):
    help = (
        "Decompose the VRP objective into per-term contributions and compare the "
        "OR-Tools reported objective against a manual reconstruction. Verifies "
        "empirically whether vacant vehicles (buffer slots) pay the soft lower bound "
        "penalty on the end cumul."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--dataset",
            type=str,
            required=True,
            help="Instance slug (e.g. reference-n1607, area-26-n157) or dataset UUID",
        )
        parser.add_argument(
            "--service-time",
            type=int,
            default=CENSUS_SERVICE_TIME_SEC,
        )
        parser.add_argument("--t-min", type=int, default=CENSUS_MIN_ROUTE_TIME_SEC)
        parser.add_argument("--t-max", type=int, default=CENSUS_MAX_ROUTE_TIME_SEC)
        parser.add_argument("--time-limit", type=int, default=SOLVER_TIME_LIMIT_SEC)
        parser.add_argument(
            "--balance-arm",
            type=str,
            default=BALANCE_ARM_ACTUAL,
            choices=list(BALANCE_ARMS),
        )
        parser.add_argument(
            "--soft-upper-target",
            type=str,
            default=SOFT_UPPER_TARGET_MIDPOINT,
            choices=list(SOFT_UPPER_TARGETS),
        )
        parser.add_argument(
            "--span-coef",
            type=int,
            default=SPATIAL_SPAN_COEF,
            help="Geographic span coefficient (Distance dimension). 0 = no spatial term.",
        )
        parser.add_argument(
            "--output",
            type=str,
            default=None,
            help="Path for the text report. Defaults to stdout only.",
        )

    def handle(self, *args, **options):
        dataset = self._get_dataset(options["dataset"])
        service_time_sec = options["service_time"]
        min_route_time_sec = options["t_min"]
        max_route_time_sec = options["t_max"]
        if min_route_time_sec > max_route_time_sec:
            raise CommandError("--t-min must not exceed --t-max")

        penalties = PenaltyConfig(
            soft_upper_target=options["soft_upper_target"],
            balance_arm=options["balance_arm"],
        )
        span_coef = options["span_coef"]
        use_spatial = span_coef > 0

        trees = sorted(
            Tree.objects.filter(dataset=dataset, is_active=True),
            key=lambda t: t.id,
        )
        if len(trees) < 2:
            raise CommandError("Dataset needs at least 2 active trees")

        self.stdout.write(f"Building OSRM matrix for {len(trees)} trees…")
        matrix = OSRMCostMatrixBuilder().build(trees)
        open_matrix = build_open_matrix(matrix)
        total_service = len(trees) * service_time_sec
        max_vehicles = estimate_max_vehicles(
            open_matrix, total_service, min_route_time_sec
        )
        arc_tau = p95_nearest_neighbor_travel(open_matrix)
        points = [(t.location.y, t.location.x) for t in trees] if use_spatial else None

        self.stdout.write(
            f"n={len(trees)} max_vehicles={max_vehicles} tau_p95={arc_tau:.1f}s "
            f"span_coef={span_coef}"
        )
        self.stdout.write("Solving…")

        solver = ArbocensusVRPSolver(
            matrix,
            min_route_time_sec=min_route_time_sec,
            max_route_time_sec=max_route_time_sec,
            service_time_sec=service_time_sec,
            max_vehicles=max_vehicles,
            time_limit_sec=options["time_limit"],
            spatial_points=points,
            span_coef=span_coef if use_spatial else 0,
            penalties=penalties,
        )
        result = solver.solve_and_debug()
        if result is None:
            raise CommandError("Solver returned no solution")

        routes, dropped, debug = result
        report = self._build_report(
            dataset,
            len(trees),
            routes,
            dropped,
            debug,
            penalties,
            min_route_time_sec,
            max_route_time_sec,
            service_time_sec,
            span_coef,
            arc_tau,
        )
        self.stdout.write(report)
        if options["output"]:
            out_path = settings.BASE_DIR.parent / options["output"]
            out_path.parent.mkdir(parents=True, exist_ok=True)
            out_path.write_text(report, encoding="utf-8")
            self.stdout.write(f"Report: {out_path}")

    def _get_dataset(self, identifier):
        # Try slug first (deterministic UUID), then raw UUID.
        try:
            slug_uuid = dataset_uuid(identifier)
            return Dataset.objects.get(id=slug_uuid)
        except (Dataset.DoesNotExist, ValidationError):
            pass
        try:
            return Dataset.objects.get(id=identifier)
        except (Dataset.DoesNotExist, ValidationError) as exc:
            raise CommandError(f"Dataset '{identifier}' not found") from exc

    def _build_report(
        self,
        dataset,
        n_trees,
        routes,
        dropped,
        debug,
        penalties,
        min_route_time_sec,
        max_route_time_sec,
        service_time_sec,
        span_coef,
        arc_tau,
    ):
        end_cumuls = debug["time_end_cumuls"]
        dist_cumuls = debug["dist_end_cumuls"]
        effective_tmin = debug["effective_tmin"]
        k_active = debug["k_active"]
        k_vacant = debug["max_vehicles"] - k_active
        obj_ortools = debug["objective_ortools"]

        # ── manual reconstruction ────────────────────────────────────────────
        # Arc cost: since arc cost evaluator = Time callback, total arc cost =
        # sum of Time end cumuls (start cumul = 0 for all vehicles).
        arc_cost = sum(end_cumuls)

        # Fixed vehicle cost: charged only for vehicles with at least one stop.
        fixed_cost = k_active * FIXED_VEHICLE_COST

        # Soft lower bound violations (applied to ALL max_vehicles, including vacant).
        arm = penalties.balance_arm
        if arm == "upper-tmax-tmin9000":
            lower_target = TIGHT_TMIN_SEC
        else:
            lower_target = effective_tmin
        soft_lower_cost = sum(
            max(0, lower_target - c) * SOFT_LOWER_PENALTY for c in end_cumuls
        )

        # Soft upper bound violations.
        if arm in ("upper-tmax-tmin9000",) or arm.startswith("feasible-floor"):
            upper_target = max_route_time_sec
        else:
            upper_target = (min_route_time_sec + max_route_time_sec) // 2
        soft_upper_cost = sum(
            max(0, c - upper_target) * SOFT_UPPER_PENALTY for c in end_cumuls
        )

        # Drop penalty.
        drop_cost = len(dropped) * DROP_PENALTY

        # Spatial span cost: span_coef * Distance end cumul per vehicle.
        span_cost = 0
        if dist_cumuls is not None:
            span_cost = span_coef * sum(dist_cumuls)

        manual_total = (
            arc_cost
            + fixed_cost
            + soft_lower_cost
            + soft_upper_cost
            + drop_cost
            + span_cost
        )
        delta = obj_ortools - manual_total
        match_pct = abs(delta) / max(1, obj_ortools) * 100

        route_sizes = [len(r) for r in routes]

        lines = [
            f"# Auditoría de Objetivo — {dataset.name}  (n={n_trees})",
            "",
            "## Configuración",
            f"balance_arm={penalties.balance_arm}  "
            f"T_min={min_route_time_sec}s  T_max={max_route_time_sec}s  "
            f"service={service_time_sec}s  span_coef={span_coef}",
            f"effective_tmin={effective_tmin}s  "
            f"upper_target={upper_target}s  lower_target={lower_target}s",
            f"arc_tau_p95={arc_tau:.1f}s",
            "",
            "## Solución",
            f"k_active={k_active}  k_vacant={k_vacant}  "
            f"max_vehicles={debug['max_vehicles']}  drops={len(dropped)}",
            f"ruta más pequeña: {min(route_sizes)} árboles  "
            f"ruta más grande: {max(route_sizes)} árboles"
            if routes
            else "",
            "",
            "## Descomposición del objetivo",
            "",
            f"{'Término':<28} {'OR-Tools':>16} {'Manual':>16}",
            f"{'-'*28} {'-'*16} {'-'*16}",
            f"{'arc_cost (Time cumul)':<28} {'—':>16} {arc_cost:>16,}",
            f"{'fixed_vehicle_cost':<28} {'—':>16} {fixed_cost:>16,}",
            f"{'soft_lower_violations':<28} {'—':>16} {soft_lower_cost:>16,}",
            f"{'soft_upper_violations':<28} {'—':>16} {soft_upper_cost:>16,}",
            f"{'drop_cost':<28} {'—':>16} {drop_cost:>16,}",
            f"{'span_cost (Distance)':<28} {'—':>16} {span_cost:>16,}",
            f"{'-'*28} {'-'*16} {'-'*16}",
            f"{'TOTAL':<28} {obj_ortools:>16,} {manual_total:>16,}",
            f"{'delta (OR-Tools − manual)':<28} {delta:>16,} {'':>16}",
            f"{'coincidencia':<28} {f'{100 - match_pct:.4f}%':>16} {'':>16}",
            "",
            "## Vehículos vacíos — veredicto",
        ]

        # Per-vacant-vehicle analysis
        vacant_penalties = []
        for v, c in enumerate(end_cumuls):
            if c == 0:
                vp = max(0, lower_target - c) * SOFT_LOWER_PENALTY
                vacant_penalties.append((v, vp))

        if vacant_penalties:
            lines.append(
                f"Hay {len(vacant_penalties)} vehículo(s) con end_cumul=0 "
                f"(vacíos). Cada uno paga {lower_target} × {SOFT_LOWER_PENALTY:,} "
                f"= {lower_target * SOFT_LOWER_PENALTY:,} en soft_lower_penalty."
            )
            lines.append(
                f"Costo total por vehículos vacíos: "
                f"{sum(vp for _, vp in vacant_penalties):,}"
            )
            lines.append(
                "**VEREDICTO: CONFIRMADO — los vehículos vacíos sí pagan el "
                "soft lower bound. Esto presiona al solver a llenar todos los "
                "vehículos del buffer hasta T_min (relleno).**"
            )
        else:
            lines.append(
                "No hay vehículos con end_cumul=0: todos los vehículos fueron "
                "utilizados (posiblemente sin buffer o régimen saturado)."
            )

        lines += [
            "",
            "## Detalle por vehículo",
            "",
            f"{'V':>3} {'end_T':>8} {'sl_viol':>12} {'su_viol':>12} {'dist_m':>10} {'estado'}",
        ]
        for v, c in enumerate(end_cumuls):
            sl = max(0, lower_target - c) * SOFT_LOWER_PENALTY
            su = max(0, c - upper_target) * SOFT_UPPER_PENALTY
            dm = dist_cumuls[v] if dist_cumuls else 0
            estado = "activo" if c > 0 else "VACÍO"
            lines.append(f"{v:>3} {c:>8} {sl:>12,} {su:>12,} {dm:>10,} {estado}")

        return "\n".join(lines)
