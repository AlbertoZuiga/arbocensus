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


def build_points_geojson_from_nodes(nodes: List[Dict[str, Any]], clusters_map: Dict[int, int] = None) -> Dict[str, Any]:
    features = []
    for i, n in enumerate(nodes):
        props = {'node_index': i}
        if clusters_map:
            props['cluster_id'] = clusters_map.get(i)
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


def build_points_geojson_from_trees(trees: List[Dict[str, Any]]) -> Dict[str, Any]:
    features = []
    for i, t in enumerate(trees):
        lat = t.get('lat') or t.get('latitude')
        lng = t.get('lng') or t.get('longitude')
        props = {k: v for k, v in t.items() if k not in ('lat', 'lng', 'latitude', 'longitude')}
        props['index'] = i
        feat = {
            'type': 'Feature',
            'geometry': {'type': 'Point', 'coordinates': [float(lng), float(lat)]},
            'properties': props
        }
        features.append(feat)
    return {'type': 'FeatureCollection', 'features': features}


def main(argv: List[str]):
    graph_path = 'stages/03_graph/03_graph.json'
    clusters_path = 'stages/04_cluster/clusters_by_censantes.json'
    routes_path = 'stages/05_tsp/routes_by_cluster.json'
    out_dir = 'stages/06_output'
    input_path = 'stages/01_bbox_input/01_input.json'
    filtered_path = 'stages/02_filter/02_filtered.json'
    bbox_path = 'saved_bbox.json'
    # simple args
    if len(argv) > 1:
        graph_path = argv[1]
    if len(argv) > 2:
        clusters_path = argv[2]
    if len(argv) > 3:
        routes_path = argv[3]

    # Graph / nodes
    graph = load(graph_path) if os.path.exists(graph_path) else {'nodes': []}
    nodes = graph.get('nodes', [])

    # Input trees
    if os.path.exists(input_path):
        inp = load(input_path)
        trees = inp.get('trees') or inp.get('data') or []
        pts = build_points_geojson_from_trees(trees)
        write_geojson(pts, os.path.join(out_dir, 'input_points.geojson'))
        print('Wrote input_points.geojson')

    # Filtered
    if os.path.exists(filtered_path):
        fdata = load(filtered_path)
        ftrees = fdata.get('trees') or fdata.get('data') or []
        fpts = build_points_geojson_from_trees(ftrees)
        write_geojson(fpts, os.path.join(out_dir, 'filtered_points.geojson'))
        print('Wrote filtered_points.geojson')

    # BBox polygon (if saved_bbox.json exists with 'polygon' or 'bbox')
    if os.path.exists(bbox_path):
        b = load(bbox_path)
        geom = None
        if 'polygon' in b:
            geom = {'type': 'Polygon', 'coordinates': b['polygon']}
        elif 'bbox' in b:
            # bbox as [minx,miny,maxx,maxy]
            bb = b['bbox']
            minx, miny, maxx, maxy = bb
            coords = [[minx, miny], [minx, maxy], [maxx, maxy], [maxx, miny], [minx, miny]]
            geom = {'type': 'Polygon', 'coordinates': [coords]}
        if geom:
            feat = {'type': 'FeatureCollection', 'features': [{'type': 'Feature', 'geometry': geom, 'properties': {}}]}
            write_geojson(feat, os.path.join(out_dir, 'bbox.geojson'))
            print('Wrote bbox.geojson')

    # clusters
    if os.path.exists(clusters_path):
        clusters_data = load(clusters_path)
        clusters = clusters_data.get('clusters', [])
        # build map node_index -> cluster_id
        clusters_map = {}
        for c in clusters:
            cid = c.get('cluster_id')
            members = c.get('member_node_indices', [])
            for m in members:
                clusters_map[m] = cid
        pts = build_points_geojson_from_nodes(nodes, clusters_map)
        write_geojson(pts, os.path.join(out_dir, 'clusters.geojson'))
        print('Wrote clusters.geojson')

    # routes
    if os.path.exists(routes_path):
        routes_data = load(routes_path)
        routes = routes_data.get('routes') or routes_data.get('routes', [])
        if routes:
            routes_geo = build_routes_geojson(nodes, routes)
            write_geojson(routes_geo, os.path.join(out_dir, 'routes.geojson'))
            print('Wrote routes.geojson')


if __name__ == '__main__':
    main(sys.argv)
