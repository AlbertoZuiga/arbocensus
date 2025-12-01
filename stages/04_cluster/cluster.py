#!/usr/bin/env python3
"""Cluster nodes by recursive median split.

Simple, dependency-free clustering: if number of nodes > max_size, split the node set
along the longest geographic axis at the median and recurse. Produces balanced clusters
by count and preserves spatial locality. Good for splitting large TSP into subproblems.

Usage:
  python cluster.py input_graph.json out_clusters.json --max-size 100

Output: JSON with `clusters`: list of clusters each with `id` and `node_ids`.
Also writes per-cluster files `stages/04_cluster/cluster_<id>.json` with node entries.
"""
import json
import os
import sys
from typing import List, Dict, Any, Tuple


def load_graph(path: str) -> Dict[str, Any]:
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)


def save_json(obj: Any, path: str):
    d = os.path.dirname(path)
    if d:
        os.makedirs(d, exist_ok=True)
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(obj, f, indent=2)


def bounding_box(nodes: List[Dict[str, Any]]) -> Tuple[float,float,float,float]:
    lats = [n['lat'] for n in nodes]
    lngs = [n['lng'] for n in nodes]
    return min(lats), max(lats), min(lngs), max(lngs)


def longest_axis(nodes: List[Dict[str, Any]]) -> str:
    min_lat, max_lat, min_lng, max_lng = bounding_box(nodes)
    lat_span = max_lat - min_lat
    lng_span = max_lng - min_lng
    return 'lat' if lat_span >= lng_span else 'lng'


def recursive_split(node_list: List[int], nodes: List[Dict[str, Any]], max_size: int, out_clusters: List[List[int]]):
    if len(node_list) <= max_size:
        out_clusters.append(node_list)
        return

    # prepare subset coordinates
    subset = [nodes[i] for i in node_list]
    axis = longest_axis(subset)
    # sort ids by axis
    if axis == 'lat':
        node_list.sort(key=lambda i: nodes[i]['lat'])
    else:
        node_list.sort(key=lambda i: nodes[i]['lng'])

    mid = len(node_list) // 2
    left = node_list[:mid]
    right = node_list[mid:]
    # recurse
    recursive_split(left, nodes, max_size, out_clusters)
    recursive_split(right, nodes, max_size, out_clusters)


def make_clusters(graph: Dict[str, Any], max_size: int = 100) -> Dict[str, Any]:
    nodes = graph.get('nodes', [])
    n = len(nodes)
    if n == 0:
        return {'clusters': []}

    all_ids = list(range(n))
    clusters: List[List[int]] = []
    recursive_split(all_ids, nodes, max_size, clusters)

    out = {'clusters': []}
    for cid, lst in enumerate(clusters):
        out['clusters'].append({'id': cid, 'node_ids': lst, 'size': len(lst)})

    return out


def write_cluster_files(clusters: Dict[str, Any], nodes: List[Dict[str, Any]], base_dir: str):
    for c in clusters['clusters']:
        cid = c['id']
        ids = c['node_ids']
        objs = [nodes[i] for i in ids]
        save_json({'id': cid, 'nodes': objs}, os.path.join(base_dir, f'cluster_{cid}.json'))


def main(argv: List[str]):
    if len(argv) < 3:
        print('Usage: python cluster.py input_graph.json out_clusters.json [--max-size N]')
        sys.exit(2)
    inp = argv[1]
    outp = argv[2]
    max_size = 100
    if '--max-size' in argv:
        try:
            max_size = int(argv[argv.index('--max-size')+1])
        except Exception:
            pass

    graph = load_graph(inp)
    nodes = graph.get('nodes', [])
    clusters = make_clusters(graph, max_size=max_size)
    save_json(clusters, outp)
    # also write per-cluster files
    base_dir = os.path.join(os.path.dirname(outp), '')
    write_cluster_files(clusters, nodes, base_dir)
    print(f'Wrote {len(clusters.get("clusters", []))} clusters to {outp} (max {max_size})')


if __name__ == '__main__':
    main(sys.argv)
