from itertools import combinations

from apps.optimization.models import RoutingSolution
from apps.optimization.route_metrics import (
    bbox_iou,
    haversine,
    interleave_per_route,
    point_in_bbox,
    sum_max_radius,
    summarize_route,
    total_interleave,
    worst_pair_iou,
)
from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = "Analyze route-quality metrics for a RoutingSolution"

    def add_arguments(self, parser):
        parser.add_argument("--solution-id", type=str, default=None)

    def handle(self, *args, **options):
        solution_id = options["solution_id"]
        if solution_id:
            try:
                solution = RoutingSolution.objects.get(id=solution_id)
            except (RoutingSolution.DoesNotExist, ValidationError) as exc:
                raise CommandError(f"No solution found with id {solution_id}") from exc
        else:
            solution = RoutingSolution.objects.order_by("-generated_at").first()
            if solution is None:
                raise CommandError("No solution found")

        routes = list(solution.routes.order_by("route_number"))

        analyzed = []
        for route in routes:
            stops = list(route.stops.select_related("tree").order_by("sequence"))
            points = [(s.tree.location.y, s.tree.location.x) for s in stops]
            if not points:
                continue
            sequences = [s.sequence for s in stops]
            analyzed.append({"route": route, **summarize_route(sequences, points)})

        self.stdout.write(f"Solution {solution.id}")
        self.stdout.write(f"  total_routes: {solution.total_routes}")
        self.stdout.write(f"  balance_score: {solution.balance_score:.3f}")

        for a in analyzed:
            route = a["route"]
            self.stdout.write("")
            self.stdout.write(f"Route {route.route_number}")
            self.stdout.write(f"  stops: {len(a['points'])}")
            self.stdout.write(f"  travel_time_sec: {route.travel_time_sec}")
            self.stdout.write(
                f"  centroid: ({a['centroid'][0]:.5f}, {a['centroid'][1]:.5f})"
            )
            self.stdout.write(f"  max_radius: {a['max_radius']:.0f} m")
            self.stdout.write(f"  mean_radius: {a['mean_radius']:.0f} m")
            self.stdout.write("  stops (lat, lon):")
            for lat, lon in a["points"]:
                self.stdout.write(f"    ({lat:.5f}, {lon:.5f})")

        self.stdout.write("")
        self.stdout.write("Inter-route")
        for a, b in combinations(analyzed, 2):
            sep = haversine(a["centroid"], b["centroid"])
            avg_radius = (a["max_radius"] + b["max_radius"]) / 2
            ratio = sep / avg_radius if avg_radius > 0 else 0.0
            flag = "OVERLAP" if sep < avg_radius else "separated"
            iou = bbox_iou(a["bbox"], b["bbox"])
            self.stdout.write(
                f"  R{a['route'].route_number}-R{b['route'].route_number}: "
                f"sep={sep:.0f} m  sep/avg_radius={ratio:.2f} {flag}  iou={iou:.2f}"
            )

        self.stdout.write("")
        self.stdout.write("Interleave")
        for a in analyzed:
            foreign = []
            for b in analyzed:
                if b is a:
                    continue
                for seq, point in zip(b["sequences"], b["points"], strict=True):
                    if point_in_bbox(point, a["bbox"]):
                        foreign.append(f"R{b['route'].route_number}.{seq}")
            label = f"  R{a['route'].route_number}: {len(foreign)} foreign in bbox"
            if foreign:
                label += " [" + ", ".join(foreign) + "]"
            self.stdout.write(label)

        self.stdout.write("")
        self.stdout.write(
            f"BASELINE balance_score={solution.balance_score:.3f} "
            f"sum_max_radius={sum_max_radius(analyzed):.0f} m "
            f"interleave_total={total_interleave(analyzed)} "
            f"interleave_per_route={interleave_per_route(analyzed):.2f} "
            f"worst_pair_iou={worst_pair_iou(analyzed):.2f}"
        )
