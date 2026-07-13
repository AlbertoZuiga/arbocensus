from itertools import combinations
from statistics import mean

from apps.optimization.route_metrics import bbox, bbox_iou
from apps.optimization.strategies import project_equirectangular

AUDIT_COLUMNS = [
    "route",
    "n_trees",
    "duration_sec",
    "service_total_sec",
    "travel_sec",
    "walk_ratio",
    "shortfall_sec",
    "saturation",
    "self_crossings",
]

SUMMARY_LABEL = "summary"


def _orientation(a, b, c):
    return (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])


def _segments_cross(first, second):
    p1, p2 = first
    p3, p4 = second
    d1 = _orientation(p3, p4, p1)
    d2 = _orientation(p3, p4, p2)
    d3 = _orientation(p1, p2, p3)
    d4 = _orientation(p1, p2, p4)
    # A zero orientation means an endpoint lies on the other segment's line: the
    # legacy dataset has trees at identical coordinates, so non-adjacent segments
    # can share an endpoint. Touching is not a backtrack; only strict straddling is.
    if 0.0 in (d1, d2, d3, d4):
        return False
    return (d1 > 0) != (d2 > 0) and (d3 > 0) != (d4 > 0)


def self_crossings(points):
    if len(points) < 4:
        return 0
    projected = [tuple(p) for p in project_equirectangular(points)]
    segments = list(zip(projected[:-1], projected[1:], strict=True))
    return sum(
        1
        for i, j in combinations(range(len(segments)), 2)
        if j > i + 1 and _segments_cross(segments[i], segments[j])
    )


def audit_route(
    route_number,
    points,
    duration_sec,
    travel_sec,
    *,
    min_route_time_sec,
    max_route_time_sec,
):
    return {
        "route": route_number,
        "n_trees": len(points),
        "duration_sec": duration_sec,
        "service_total_sec": duration_sec - travel_sec,
        "travel_sec": travel_sec,
        "walk_ratio": round(travel_sec / duration_sec, 3),
        "shortfall_sec": max(0, min_route_time_sec - duration_sec),
        "saturation": round(duration_sec / max_route_time_sec, 3),
        "self_crossings": self_crossings(points),
    }


def audit_solution(solution, *, min_route_time_sec, max_route_time_sec):
    audited = []
    for route in solution.routes.order_by("route_number"):
        stops = list(route.stops.select_related("tree").order_by("sequence"))
        points = [(stop.tree.location.y, stop.tree.location.x) for stop in stops]
        audited.append(
            {
                "row": audit_route(
                    route.route_number,
                    points,
                    route.total_estimated_time_sec,
                    route.travel_time_sec,
                    min_route_time_sec=min_route_time_sec,
                    max_route_time_sec=max_route_time_sec,
                ),
                "points": points,
                "stops": [
                    {"sequence": stop.sequence, "tree_id": str(stop.tree_id)}
                    for stop in stops
                ],
            }
        )
    return audited


def summarize_audit(audited):
    rows = [entry["row"] for entry in audited]
    duration_total = sum(row["duration_sec"] for row in rows)
    travel_total = sum(row["travel_sec"] for row in rows)
    return {
        "route": SUMMARY_LABEL,
        "n_trees": sum(row["n_trees"] for row in rows),
        "duration_sec": duration_total,
        "service_total_sec": sum(row["service_total_sec"] for row in rows),
        "travel_sec": travel_total,
        "walk_ratio": round(travel_total / duration_total, 3),
        "shortfall_sec": sum(row["shortfall_sec"] for row in rows),
        "saturation": round(mean(row["saturation"] for row in rows), 3),
        "self_crossings": sum(row["self_crossings"] for row in rows),
    }


def worst_overlap_pair(audited):
    if len(audited) < 2:
        return None
    boxes = {entry["row"]["route"]: bbox(entry["points"]) for entry in audited}
    pair = max(
        combinations(audited, 2),
        key=lambda p: bbox_iou(
            boxes[p[0]["row"]["route"]], boxes[p[1]["row"]["route"]]
        ),
    )
    iou = bbox_iou(boxes[pair[0]["row"]["route"]], boxes[pair[1]["row"]["route"]])
    return pair[0], pair[1], round(iou, 3)


def routes_geojson(audited):
    features = []
    for entry in audited:
        row = entry["row"]
        # A LineString needs two positions: a one-stop route would emit invalid
        # GeoJSON and geojson.io/QGIS refuse to render the whole file.
        if len(entry["points"]) < 2:
            continue
        features.append(
            {
                "type": "Feature",
                "geometry": {
                    "type": "LineString",
                    "coordinates": [[lon, lat] for lat, lon in entry["points"]],
                },
                "properties": dict(row),
            }
        )
    for entry in audited:
        route_number = entry["row"]["route"]
        for (lat, lon), stop in zip(entry["points"], entry["stops"], strict=True):
            features.append(
                {
                    "type": "Feature",
                    "geometry": {"type": "Point", "coordinates": [lon, lat]},
                    "properties": {
                        "route": route_number,
                        "sequence": stop["sequence"],
                        "tree_id": stop["tree_id"],
                    },
                }
            )
    return {"type": "FeatureCollection", "features": features}
