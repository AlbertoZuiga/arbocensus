import math
from itertools import combinations

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


def summarize_route(sequences, points):
    c = centroid(points)
    radii = [haversine(c, p) for p in points]
    return {
        "points": points,
        "sequences": sequences,
        "centroid": c,
        "max_radius": max(radii),
        "mean_radius": sum(radii) / len(radii),
        "bbox": bbox(points),
    }


def sum_max_radius(routes):
    return sum(r["max_radius"] for r in routes)


def total_interleave(routes):
    total = 0
    for a in routes:
        for b in routes:
            if b is a:
                continue
            for point in b["points"]:
                if point_in_bbox(point, a["bbox"]):
                    total += 1
    return total


def interleave_per_route(routes):
    return total_interleave(routes) / len(routes) if routes else 0.0


def worst_pair_iou(routes):
    ious = [bbox_iou(a["bbox"], b["bbox"]) for a, b in combinations(routes, 2)]
    return max(ious) if ious else 0.0


def routes_from_points(node_routes, trees):
    summaries = []
    for route in node_routes:
        coords = [(trees[node].location.y, trees[node].location.x) for node in route]
        if not coords:
            continue
        summaries.append(summarize_route(list(range(1, len(coords) + 1)), coords))
    return summaries


def routes_from_solution(solution):
    routes = []
    for route in solution.routes.order_by("route_number"):
        stops = list(route.stops.select_related("tree").order_by("sequence"))
        coords = [(s.tree.location.y, s.tree.location.x) for s in stops]
        if not coords:
            continue
        routes.append(summarize_route([s.sequence for s in stops], coords))
    return routes


def aggregate_metrics(routes):
    return {
        "sum_max_radius_m": round(sum_max_radius(routes)),
        "interleave_total": total_interleave(routes),
        "interleave_per_route": round(interleave_per_route(routes), 2),
        "worst_pair_iou": round(worst_pair_iou(routes), 2),
    }
