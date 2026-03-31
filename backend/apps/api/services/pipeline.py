"""Pipeline orchestration service."""

import logging

from apps.api.models import PipelineRun
from django.utils import timezone

from arbocensus_pipeline import export
from arbocensus_pipeline import filter as flt
from arbocensus_pipeline import graph, optimize, routing
from arbocensus_pipeline.input import load_input

logger = logging.getLogger(__name__)


def run_pipeline(pipeline_run: PipelineRun) -> None:
    """Execute the full pipeline for a given PipelineRun instance.

    Updates `pipeline_run` in-place (persists to DB at key checkpoints).
    On success, sets status=completed and stores GeoJSON results.
    On failure, sets status=failed and saves the error message.
    """
    try:
        pipeline_run.status = PipelineRun.Status.RUNNING
        pipeline_run.save(update_fields=["status"])

        # Stage 1: Load input
        trees_data = load_input(
            north=pipeline_run.bbox_north,
            south=pipeline_run.bbox_south,
            east=pipeline_run.bbox_east,
            west=pipeline_run.bbox_west,
        )

        # Stage 2: Filter
        filtered = flt.filter_trees(trees_data)
        trees = filtered.get("trees", [])

        # Stage 3: Build graph
        nodes = graph.build_nodes(trees)

        if not nodes:
            pipeline_run.status = PipelineRun.Status.COMPLETED
            pipeline_run.tree_count = 0
            pipeline_run.route_count = 0
            pipeline_run.routes_geojson = {"type": "FeatureCollection", "features": []}
            pipeline_run.clusters_geojson = {
                "type": "FeatureCollection",
                "features": [],
            }
            pipeline_run.completed_at = timezone.now()
            pipeline_run.save()
            return

        kd_tree = graph.build_kd_tree(nodes)
        k_neighbors = min(12, len(nodes) - 1) if len(nodes) > 1 else 1
        graph.build_sparse_graph_from_kdtree(nodes, kd_tree, k_neighbors=k_neighbors)

        # Stage 4: Route optimization
        osm_cache = routing.RoutingCache()
        routes = optimize.find_routes(
            locations=nodes,
            expected_duration_per_route=pipeline_run.expected_duration_min * 60.0,
            t_per_tree=pipeline_run.time_per_tree_min * 60.0,
            f_osm_route_time=routing.osm_route_time,
            f_google_route_time=routing.google_route_time,
            osm_cache=osm_cache,
            google_cache=routing.RoutingCache(),
        )

        # Stage 5: Build GeoJSON results
        routes_geojson = export.build_routes_geojson(nodes, routes)

        # Build clusters GeoJSON from routes
        clusters = [
            {
                "cluster_id": r.get("cluster_id"),
                "member_node_indices": r.get("route", []),
            }
            for r in routes
        ]
        clusters_geojson = export.build_cluster_polygons_geojson(nodes, clusters)

        # Persist results
        pipeline_run.tree_count = len(nodes)
        pipeline_run.route_count = len(routes)
        pipeline_run.routes_geojson = routes_geojson
        pipeline_run.clusters_geojson = clusters_geojson
        pipeline_run.status = PipelineRun.Status.COMPLETED
        pipeline_run.completed_at = timezone.now()
        pipeline_run.save()

    except Exception as exc:  # noqa: BLE001
        logger.exception(
            "Pipeline run %s failed at status=%s", pipeline_run.pk, pipeline_run.status
        )
        pipeline_run.status = PipelineRun.Status.FAILED
        pipeline_run.error_message = str(exc)
        pipeline_run.completed_at = timezone.now()
        pipeline_run.save(update_fields=["status", "error_message", "completed_at"])
        raise
