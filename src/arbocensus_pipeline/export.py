"""Export utilities for GeoJSON visualization"""
from typing import List, Dict, Any
import os
import json


def write_geojson(obj: Dict[str, Any], path: str):
    d = os.path.dirname(path)
    if d:
        os.makedirs(d, exist_ok=True)
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(obj, f, ensure_ascii=False)


def build_points_geojson_from_nodes(nodes: List[Dict[str, Any]], clusters_map: Dict[int, int] = None) -> Dict[str, Any]:
    features = []
    for i, n in enumerate(nodes):
        props = {'node_index': i}
        if clusters_map:
            props['cluster_id'] = clusters_map.get(i)
        feat = {'type': 'Feature', 'geometry': {'type': 'Point', 'coordinates': [n['lng'], n['lat']]}, 'properties': props}
        features.append(feat)
    return {'type': 'FeatureCollection', 'features': features}


def build_routes_geojson(nodes: List[Dict[str, Any]], routes: List[Dict[str, Any]]) -> Dict[str, Any]:
    features = []
    for r in routes:
        tour = r.get('route', [])
        coords = [[nodes[i]['lng'], nodes[i]['lat']] for i in tour]
        feat = {'type': 'Feature', 'geometry': {'type': 'LineString', 'coordinates': coords}, 'properties': {'cluster_id': r.get('cluster_id'), 'size': r.get('size'), 'total_minutes': r.get('total_minutes')}}
        features.append(feat)
    return {'type': 'FeatureCollection', 'features': features}
