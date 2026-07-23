from itertools import combinations
from statistics import mean

import numpy as np
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
    return (b[..., 0] - a[..., 0]) * (c[..., 1] - a[..., 1]) - (
        b[..., 1] - a[..., 1]
    ) * (c[..., 0] - a[..., 0])


def self_crossings(points):
    if len(points) < 4:
        return 0
    projected = project_equirectangular(points)
    starts = projected[:-1]
    ends = projected[1:]
    lo = np.minimum(starts, ends)
    hi = np.maximum(starts, ends)
    total = 0
    for i in range(len(starts) - 2):
        rest = i + 2
        # Disjoint bounding boxes cannot straddle, so the orientation test only
        # runs on the survivors. Without this a street polyline (~3000 segments
        # per route) costs millions of pair evaluations.
        candidates = np.flatnonzero(
            (lo[rest:, 0] <= hi[i, 0])
            & (hi[rest:, 0] >= lo[i, 0])
            & (lo[rest:, 1] <= hi[i, 1])
            & (hi[rest:, 1] >= lo[i, 1])
        )
        if candidates.size == 0:
            continue
        p3 = starts[rest:][candidates]
        p4 = ends[rest:][candidates]
        d1 = _orientation(p3, p4, starts[i])
        d2 = _orientation(p3, p4, ends[i])
        d3 = _orientation(starts[i], ends[i], p3)
        d4 = _orientation(starts[i], ends[i], p4)
        # A zero orientation means an endpoint lies on the other segment's line:
        # the legacy dataset has trees at identical coordinates, so non-adjacent
        # segments can share an endpoint. Touching is not a backtrack; only
        # strict straddling is.
        touching = (d1 == 0) | (d2 == 0) | (d3 == 0) | (d4 == 0)
        straddles = ((d1 > 0) != (d2 > 0)) & ((d3 > 0) != (d4 > 0))
        total += int(np.count_nonzero(straddles & ~touching))
    return total


def road_self_crossings(path):
    # `path` is the OSRM road polyline as [lon, lat] vertices — the geometry the
    # surveyor map draws — whereas self_crossings projects (lat, lon). The chord
    # metric joins stops directly; this counts crossings of the walked streets.
    return self_crossings([(lat, lon) for lon, lat in path])


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


def tmin_gap_coverage(rows, *, min_route_time_sec):
    coverage = []
    for row in rows:
        gap = min_route_time_sec - row["service_total_sec"]
        if gap > 0:
            coverage.append(round(row["travel_sec"] / gap, 3))
    return coverage


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
