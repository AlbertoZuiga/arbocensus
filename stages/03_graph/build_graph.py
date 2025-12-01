#!/usr/bin/env python3
"""Build graph: nodes + distance matrix (Haversine meters) from filtered trees.

Usage:
  python build_graph.py input_filtered.json out_graph.json

Output format (JSON):
{
  "nodes": [{"id": 0, "lat": ..., "lng": ..., "meta": {...}}, ...],
  "distances": [[0.0, 123.4, ...], [...], ...],
  "metric": "haversine_m"
}
"""
import json
import math
import sys
import os
from typing import List, Dict, Any


def haversine_m(lat1, lon1, lat2, lon2):
    # returns distance in meters between two (lat, lon)
    R = 6371000.0
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi/2.0)**2 + math.cos(phi1)*math.cos(phi2)*math.sin(dlambda/2.0)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
    return R * c


def load_filtered(path: str) -> Dict[str, Any]:
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)


def build_nodes(trees: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    nodes = []
    for i, t in enumerate(trees):
        lat = t.get('lat') if isinstance(t, dict) else None
        lng = t.get('lng') if isinstance(t, dict) else None
        # some fallback keys
        if lat is None:
            lat = t.get('latitude')
        if lng is None:
            lng = t.get('longitude')
        nodes.append({'id': i, 'lat': float(lat), 'lng': float(lng), 'meta': t.get('meta') if isinstance(t, dict) else None})
    return nodes


def compute_matrix(nodes: List[Dict[str, Any]]) -> List[List[float]]:
    n = len(nodes)
    mat = [[0.0]*n for _ in range(n)]
    for i in range(n):
        lat1 = nodes[i]['lat']
        lon1 = nodes[i]['lng']
        for j in range(i+1, n):
            lat2 = nodes[j]['lat']
            lon2 = nodes[j]['lng']
            d = haversine_m(lat1, lon1, lat2, lon2)
            mat[i][j] = d
            mat[j][i] = d
    return mat


def save_graph(nodes: List[Dict[str, Any]], mat: List[List[float]], out_path: str):
    obj = {'nodes': nodes, 'distances': mat, 'metric': 'haversine_m'}
    d = os.path.dirname(out_path)
    if d:
        os.makedirs(d, exist_ok=True)
    with open(out_path, 'w', encoding='utf-8') as f:
        json.dump(obj, f)


def main(argv: List[str]):
    if len(argv) < 3:
        print('Usage: python build_graph.py input_filtered.json out_graph.json')
        sys.exit(2)
    inp = argv[1]
    outp = argv[2]
    data = load_filtered(inp)
    trees = data.get('trees', [])
    nodes = build_nodes(trees)
    print(f'Building graph for {len(nodes)} nodes...')
    mat = compute_matrix(nodes)
    save_graph(nodes, mat, outp)
    print(f'Wrote graph to {outp}')


if __name__ == '__main__':
    main(sys.argv)
