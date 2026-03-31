"""API views for the arbocensus web application."""

import json
import logging

from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt

from .models import PipelineRun
from .services.pipeline import run_pipeline
from .services.route_discovery import list_public_routes

logger = logging.getLogger(__name__)


def api_root(request):
    """API root — lists available endpoints."""
    return JsonResponse(
        {
            "message": "ArboCensus API",
            "endpoints": list_public_routes(),
        }
    )


def health(request):
    """Health check."""
    return JsonResponse({"status": "ok", "timestamp": timezone.now().isoformat()})


@csrf_exempt
def runs_list_create(request):
    """GET /api/runs/ — list all runs.
    POST /api/runs/ — create and start a new pipeline run.
    """
    if request.method == "GET":
        runs = PipelineRun.objects.values(
            "id",
            "status",
            "bbox_north",
            "bbox_south",
            "bbox_east",
            "bbox_west",
            "tree_count",
            "route_count",
            "created_at",
            "completed_at",
            "expected_duration_min",
            "time_per_tree_min",
        )
        return JsonResponse({"runs": list(runs)})

    if request.method == "POST":
        try:
            body = json.loads(request.body)
        except (json.JSONDecodeError, ValueError):
            return JsonResponse({"error": "Invalid JSON body"}, status=400)

        # Validate required fields
        required = ["north", "south", "east", "west"]
        missing = [f for f in required if f not in body]
        if missing:
            return JsonResponse(
                {"error": f"Missing required fields: {', '.join(missing)}"},
                status=400,
            )

        try:
            north = float(body["north"])
            south = float(body["south"])
            east = float(body["east"])
            west = float(body["west"])
        except (TypeError, ValueError) as exc:
            return JsonResponse(
                {"error": f"Invalid coordinate value: {exc}"}, status=400
            )

        if south >= north:
            return JsonResponse({"error": "south must be less than north"}, status=400)
        if west >= east:
            return JsonResponse({"error": "west must be less than east"}, status=400)

        run = PipelineRun.objects.create(
            bbox_north=north,
            bbox_south=south,
            bbox_east=east,
            bbox_west=west,
            expected_duration_min=float(body.get("expected_duration_min", 150.0)),
            time_per_tree_min=float(body.get("time_per_tree_min", 2.0)),
        )

        # Run synchronously (could be a Celery task in production)
        try:
            run_pipeline(run)
        except Exception:  # noqa: BLE001
            logger.exception("Pipeline run %s failed", run.pk)

        run.refresh_from_db()
        return JsonResponse(_serialize_run(run), status=201)

    return JsonResponse({"error": "Method not allowed"}, status=405)


def run_detail(request, run_id):
    """GET /api/runs/{id}/ — get run status and summary."""
    try:
        run = PipelineRun.objects.get(pk=run_id)
    except PipelineRun.DoesNotExist:
        return JsonResponse({"error": "Run not found"}, status=404)
    return JsonResponse(_serialize_run(run))


def run_routes_geojson(request, run_id):
    """GET /api/runs/{id}/routes.geojson — get routes GeoJSON."""
    try:
        run = PipelineRun.objects.get(pk=run_id)
    except PipelineRun.DoesNotExist:
        return JsonResponse({"error": "Run not found"}, status=404)
    if run.status != PipelineRun.Status.COMPLETED:
        return JsonResponse(
            {"error": f"Run not completed (status: {run.status})"}, status=409
        )
    return JsonResponse(
        run.routes_geojson or {"type": "FeatureCollection", "features": []}
    )


def run_clusters_geojson(request, run_id):
    """GET /api/runs/{id}/clusters.geojson — get clusters GeoJSON."""
    try:
        run = PipelineRun.objects.get(pk=run_id)
    except PipelineRun.DoesNotExist:
        return JsonResponse({"error": "Run not found"}, status=404)
    if run.status != PipelineRun.Status.COMPLETED:
        return JsonResponse(
            {"error": f"Run not completed (status: {run.status})"}, status=409
        )
    return JsonResponse(
        run.clusters_geojson or {"type": "FeatureCollection", "features": []}
    )


def _serialize_run(run: PipelineRun) -> dict:
    return {
        "id": run.pk,
        "status": run.status,
        "bbox": {
            "north": run.bbox_north,
            "south": run.bbox_south,
            "east": run.bbox_east,
            "west": run.bbox_west,
        },
        "parameters": {
            "expected_duration_min": run.expected_duration_min,
            "time_per_tree_min": run.time_per_tree_min,
        },
        "results": {
            "tree_count": run.tree_count,
            "route_count": run.route_count,
        },
        "error_message": run.error_message or None,
        "created_at": run.created_at.isoformat() if run.created_at else None,
        "completed_at": run.completed_at.isoformat() if run.completed_at else None,
        "links": {
            "self": f"/api/runs/{run.pk}/",
            "routes_geojson": f"/api/runs/{run.pk}/routes.geojson",
            "clusters_geojson": f"/api/runs/{run.pk}/clusters.geojson",
        },
    }
