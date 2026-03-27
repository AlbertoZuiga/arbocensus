"""Export utilities for GeoJSON visualization"""

import json
import os
from typing import Any, Dict, List


def write_geojson(obj: Dict[str, Any], path: str):
    d = os.path.dirname(path)
    if d:
        os.makedirs(d, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False)


def build_bbox_geojson(
    north: float, south: float, east: float, west: float
) -> Dict[str, Any]:
    """Build a GeoJSON polygon for the bounding box."""
    coords = [[west, north], [east, north], [east, south], [west, south], [west, north]]
    return {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "geometry": {"type": "Polygon", "coordinates": [coords]},
                "properties": {"type": "bbox"},
            }
        ],
    }


def build_points_geojson_from_nodes(
    nodes: List[Dict[str, Any]], clusters_map: Dict[int, int] = None
) -> Dict[str, Any]:
    features = []
    for i, n in enumerate(nodes):
        props = {"node_index": i}
        if clusters_map:
            props["cluster_id"] = clusters_map.get(i)
        feat = {
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": [n["lng"], n["lat"]]},
            "properties": props,
        }
        features.append(feat)
    return {"type": "FeatureCollection", "features": features}


def build_points_geojson_from_trees(trees: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Build GeoJSON from raw tree objects (with lat/lng or latitude/longitude)."""
    features = []
    for i, t in enumerate(trees):
        lat = t.get("lat") or t.get("latitude")
        lng = t.get("lng") or t.get("longitude")
        if lat is None or lng is None:
            continue
        props = {"tree_index": i}
        if "id" in t:
            props["tree_id"] = t["id"]
        feat = {
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": [lng, lat]},
            "properties": props,
        }
        features.append(feat)
    return {"type": "FeatureCollection", "features": features}


def build_cluster_polygons_geojson(
    nodes: List[Dict[str, Any]], clusters: List[Dict[str, Any]]
) -> Dict[str, Any]:
    """Build convex hull polygons for each cluster."""
    features = []
    for c in clusters:
        members = c.get("member_node_indices", [])
        if len(members) < 3:
            continue  # Need at least 3 points for a polygon

        # Get coordinates of cluster members
        points = [[nodes[i]["lng"], nodes[i]["lat"]] for i in members if i < len(nodes)]

        # Simple convex hull (could be improved with proper algorithm)
        # For now, just create a bounding box around the cluster
        if points:
            lngs = [p[0] for p in points]
            lats = [p[1] for p in points]
            min_lng, max_lng = min(lngs), max(lngs)
            min_lat, max_lat = min(lats), max(lats)

            coords = [
                [min_lng, min_lat],
                [max_lng, min_lat],
                [max_lng, max_lat],
                [min_lng, max_lat],
                [min_lng, min_lat],
            ]

            feat = {
                "type": "Feature",
                "geometry": {"type": "Polygon", "coordinates": [coords]},
                "properties": {"cluster_id": c.get("cluster_id"), "size": len(members)},
            }
            features.append(feat)

    return {"type": "FeatureCollection", "features": features}


def build_routes_geojson(
    nodes: List[Dict[str, Any]], routes: List[Dict[str, Any]]
) -> Dict[str, Any]:
    features = []
    for r in routes:
        route = r.get("route", [])
        coords = []
        for node_idx in route:
            try:
                i = int(node_idx)
            except (TypeError, ValueError):
                continue
            if 0 <= i < len(nodes):
                coords.append([nodes[i]["lng"], nodes[i]["lat"]])
        if len(coords) < 2:
            continue
        feat = {
            "type": "Feature",
            "geometry": {"type": "LineString", "coordinates": coords},
            "properties": {
                "cluster_id": r.get("cluster_id"),
                "size": r.get("size"),
                "total_minutes": r.get("total_minutes"),
            },
        }
        features.append(feat)
    return {"type": "FeatureCollection", "features": features}
