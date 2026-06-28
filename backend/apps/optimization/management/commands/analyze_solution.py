import math
from itertools import combinations

from apps.optimization.models import RoutingSolution
from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError

EARTH_RADIUS_M = 6371000


def haversine(a, b):
    lat1, lon1, lat2, lon2 = map(math.radians, [a[0], a[1], b[0], b[1]])
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    h = (
        math.sin(dlat / 2) ** 2
        + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
    )
    return 2 * EARTH_RADIUS_M * math.asin(math.sqrt(h))


def centroid(points):
    n = len(points)
    return (sum(p[0] for p in points) / n, sum(p[1] for p in points) / n)


def bbox(points):
    lats = [p[0] for p in points]
    lons = [p[1] for p in points]
    return (min(lats), max(lats), min(lons), max(lons))


def bbox_iou(a, b):
    ilat = max(0.0, min(a[1], b[1]) - max(a[0], b[0]))
    ilon = max(0.0, min(a[3], b[3]) - max(a[2], b[2]))
    inter = ilat * ilon
    area_a = (a[1] - a[0]) * (a[3] - a[2])
    area_b = (b[1] - b[0]) * (b[3] - b[2])
    union = area_a + area_b - inter
    return inter / union if union > 0 else 0.0


def point_in_bbox(point, box):
    return box[0] <= point[0] <= box[1] and box[2] <= point[1] <= box[3]


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
            c = centroid(points)
            radii = [haversine(c, p) for p in points]
            analyzed.append(
                {
                    "route": route,
                    "points": points,
                    "sequences": sequences,
                    "centroid": c,
                    "max_radius": max(radii),
                    "mean_radius": sum(radii) / len(radii),
                    "bbox": bbox(points),
                }
            )

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
        total_interleave = 0
        for a in analyzed:
            foreign = []
            for b in analyzed:
                if b is a:
                    continue
                for seq, point in zip(b["sequences"], b["points"], strict=True):
                    if point_in_bbox(point, a["bbox"]):
                        foreign.append(f"R{b['route'].route_number}.{seq}")
            total_interleave += len(foreign)
            label = f"  R{a['route'].route_number}: {len(foreign)} foreign in bbox"
            if foreign:
                label += " [" + ", ".join(foreign) + "]"
            self.stdout.write(label)

        sum_max_radius = sum(a["max_radius"] for a in analyzed)
        self.stdout.write("")
        self.stdout.write(
            f"BASELINE balance_score={solution.balance_score:.3f} "
            f"sum_max_radius={sum_max_radius:.0f} m "
            f"total_interleave={total_interleave}"
        )
