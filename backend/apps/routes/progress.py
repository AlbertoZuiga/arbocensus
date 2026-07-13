from apps.optimization.models import RoutingSolution
from django.db.models import Count, Q

from .models import Route, RouteStop

UNASSIGNED_LABEL = "Sin asignar"


def published_solution(dataset_id):
    return RoutingSolution.objects.filter(
        dataset_id=dataset_id, published_at__isnull=False
    ).first()


def _empty_totals():
    return {"total": 0, "visited": 0, "skipped": 0, "pending": 0}


def _sum_totals(items):
    totals = _empty_totals()
    for item in items:
        for key in totals:
            totals[key] += item[key]
    return totals


def _routes_with_counts(solution):
    return (
        Route.objects.filter(solution=solution)
        .select_related("surveyor")
        .annotate(
            visited=Count("stops", filter=Q(stops__status=RouteStop.Status.VISITED)),
            skipped=Count("stops", filter=Q(stops__status=RouteStop.Status.SKIPPED)),
            pending=Count("stops", filter=Q(stops__status=RouteStop.Status.PENDING)),
        )
        .order_by("route_number")
    )


def _surveyor_name(surveyor):
    return surveyor.username if surveyor else None


def _route_progress(route):
    return {
        "id": str(route.id),
        "route_number": route.route_number,
        "surveyor_id": str(route.surveyor_id) if route.surveyor_id else None,
        "surveyor_name": _surveyor_name(route.surveyor),
        "total": route.visited + route.skipped + route.pending,
        "visited": route.visited,
        "skipped": route.skipped,
        "pending": route.pending,
    }


def _surveyor_progress(routes):
    grouped = {}
    for route in routes:
        group = grouped.setdefault(
            route["surveyor_id"],
            {
                "surveyor_id": route["surveyor_id"],
                "surveyor_name": route["surveyor_name"] or UNASSIGNED_LABEL,
                "route_count": 0,
                **_empty_totals(),
            },
        )
        group["route_count"] += 1
        for key in _empty_totals():
            group[key] += route[key]
    return sorted(
        grouped.values(),
        key=lambda group: (group["surveyor_id"] is None, group["surveyor_name"]),
    )


def census_progress(dataset_id):
    solution = published_solution(dataset_id)
    if solution is None:
        return {
            "solution": None,
            "totals": _empty_totals(),
            "routes": [],
            "surveyors": [],
        }
    routes = [_route_progress(route) for route in _routes_with_counts(solution)]
    return {
        "solution": {
            "id": str(solution.id),
            "strategy": solution.strategy,
            "published_at": solution.published_at,
            "total_routes": solution.total_routes,
        },
        "totals": _sum_totals(routes),
        "routes": routes,
        "surveyors": _surveyor_progress(routes),
    }


def census_progress_geojson(dataset_id):
    solution = published_solution(dataset_id)
    if solution is None:
        return {"type": "FeatureCollection", "features": []}
    stops = (
        RouteStop.objects.filter(route__solution=solution)
        .select_related("tree", "route", "route__surveyor")
        .only(
            "id",
            "sequence",
            "status",
            "skip_reason",
            "tree__location",
            "route__route_number",
            "route__surveyor__username",
        )
        .order_by("route__route_number", "sequence")
    )
    features = [
        {
            "type": "Feature",
            "id": str(stop.id),
            "geometry": {
                "type": "Point",
                "coordinates": [stop.tree.location.x, stop.tree.location.y],
            },
            "properties": {
                "route_number": stop.route.route_number,
                "sequence": stop.sequence,
                "status": stop.status,
                "surveyor_name": _surveyor_name(stop.route.surveyor),
                "skip_reason": stop.skip_reason,
            },
        }
        for stop in stops
    ]
    return {"type": "FeatureCollection", "features": features}
