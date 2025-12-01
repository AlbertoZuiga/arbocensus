#!/usr/bin/env python3
"""Export clusters and routes to GeoJSON for visualization.

Reads:
 - stages/03_graph/03_graph.json (nodes + coordinates)
 - stages/04_cluster/clusters_by_censantes.json (clusters)
 - stages/05_tsp/routes_by_cluster.json (optional routes)

Writes:
 - stages/06_output/clusters.geojson (Point features, property cluster_id)
 - stages/06_output/routes.geojson (LineString features per cluster if routes available)

"""
import json
import os
import sys
from typing import List, Dict, Any


def load(path: str):
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)


def write_geojson(obj, path: str):
    d = os.path.dirname(path)
    if d:
        os.makedirs(d, exist_ok=True)
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(obj, f, ensure_ascii=False)


def build_points_geojson(nodes: List[Dict[str, Any]], clusters_map: Dict[int, int]) -> Dict[str, Any]:
    features = []
    for i, n in enumerate(nodes):
        props = {'node_index': i, 'cluster_id': clusters_map.get(i)}
        feat = {
            'type': 'Feature',
            'geometry': {'type': 'Point', 'coordinates': [n['lng'], n['lat']]},
            'properties': props
        }
        features.append(feat)
    return {'type': 'FeatureCollection', 'features': features}


def build_routes_geojson(nodes: List[Dict[str, Any]], routes: List[Dict[str, Any]]) -> Dict[str, Any]:
    features = []
    for r in routes:
        tour = r.get('route', [])
        coords = [[nodes[i]['lng'], nodes[i]['lat']] for i in tour]
        feat = {
            'type': 'Feature',
            'geometry': {'type': 'LineString', 'coordinates': coords},
            'properties': {'cluster_id': r.get('cluster_id'), 'size': r.get('size'), 'total_minutes': r.get('total_minutes')}
        }
        features.append(feat)
    return {'type': 'FeatureCollection', 'features': features}


def main(argv: List[str]):
    graph_path = 'stages/03_graph/03_graph.json'
    clusters_path = 'stages/04_cluster/clusters_by_censantes.json'
    routes_path = 'stages/05_tsp/routes_by_cluster.json'
    out_dir = 'stages/06_output'
    # simple args
    if len(argv) > 1:
        graph_path = argv[1]
    if len(argv) > 2:
        clusters_path = argv[2]
    if len(argv) > 3:
        routes_path = argv[3]

    graph = load(graph_path)
    nodes = graph.get('nodes', [])
    clusters_data = load(clusters_path)
    clusters = clusters_data.get('clusters', [])
    # build map node_index -> cluster_id
    clusters_map = {}
    for c in clusters:
        cid = c.get('cluster_id')
        members = c.get('member_node_indices', [])
        for m in members:
            clusters_map[m] = cid

    points = build_points_geojson(nodes, clusters_map)
    write_geojson(points, os.path.join(out_dir, 'clusters.geojson'))
    print('Wrote clusters.geojson')

    # if routes exist
    if os.path.exists(routes_path):
        routes_data = load(routes_path)
        routes = routes_data.get('routes') or routes_data.get('routes', [])
        if routes:
            routes_geo = build_routes_geojson(nodes, routes)
            write_geojson(routes_geo, os.path.join(out_dir, 'routes.geojson'))
            print('Wrote routes.geojson')


if __name__ == '__main__':
    main(sys.argv)
