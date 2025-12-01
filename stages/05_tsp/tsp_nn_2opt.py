#!/usr/bin/env python3
"""TSP stage: nearest-neighbor + 2-opt improvement.

Usage:
  python tsp_nn_2opt.py --graph stages/03_graph/03_graph.json --clusters stages/04_cluster/clusters_by_censantes.json --out stages/05_tsp/routes_by_cluster.json

If `--clusters` is omitted, the script computes a single route for the whole graph.
"""
import json
import math
import sys
import os
from typing import List, Dict, Any


def nn_tour(start: int, nodes: List[int], distances: List[List[float]]) -> List[int]:
    if not nodes:
        return []
    unvisited = set(nodes)
    tour = [start]
    unvisited.remove(start)
    curr = start
    while unvisited:
        nxt = min(unvisited, key=lambda x: distances[curr][x])
        tour.append(nxt)
        unvisited.remove(nxt)
        curr = nxt
    return tour


def tour_length(tour: List[int], distances: List[List[float]]) -> float:
    if not tour:
        return 0.0
    s = 0.0
    for i in range(len(tour)-1):
        s += distances[tour[i]][tour[i+1]]
    s += distances[tour[-1]][tour[0]]
    return s


def two_opt(tour: List[int], distances: List[List[float]], max_iter: int = 100) -> List[int]:
    best = tour[:]
    best_len = tour_length(best, distances)
    improved = True
    it = 0
    while improved and it < max_iter:
        improved = False
        it += 1
        n = len(best)
        for i in range(1, n-2):
            for j in range(i+1, n-1):
                if j - i == 1:
                    continue
                new = best[:i] + best[i:j+1][::-1] + best[j+1:]
                nl = tour_length(new, distances)
                if nl + 1e-9 < best_len:
                    best = new
                    best_len = nl
                    improved = True
                    break
            if improved:
                break
    return best


def compute_route_for_cluster(members: List[int], distances: List[List[float]], time_per_tree: float, walking_speed_kmh: float, haversine_multiplier: float = 1.0) -> Dict[str, Any]:
    if not members:
        return {'route': [], 'route_meters': 0.0, 'service_minutes': 0.0, 'route_minutes': 0.0, 'total_minutes': 0.0}
    start = members[0]
    tour = nn_tour(start, members, distances)
    if len(tour) > 2:
        tour = two_opt(tour, distances, max_iter=50)
    meters = tour_length(tour, distances)
    route_minutes = meters * (60.0 / 1000.0) / float(walking_speed_kmh) * float(haversine_multiplier)
    service_minutes = len(members) * float(time_per_tree)
    total = route_minutes + service_minutes
    return {'route': tour, 'route_meters': meters, 'service_minutes': service_minutes, 'route_minutes': route_minutes, 'total_minutes': total}


def load_json(path: str):
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)


def main(argv: List[str]):
    # simple arg parsing
    graph_path = None
    clusters_path = None
    out_path = 'stages/05_tsp/routes_by_cluster.json'
    time_per_tree = 1.5
    walking_speed = 5.0
    haversine_multiplier = 1.25
    i = 1
    while i < len(argv):
        a = argv[i]
        if a == '--graph' and i+1 < len(argv):
            graph_path = argv[i+1]; i += 2; continue
        if a == '--clusters' and i+1 < len(argv):
            clusters_path = argv[i+1]; i += 2; continue
        if a == '--out' and i+1 < len(argv):
            out_path = argv[i+1]; i += 2; continue
        if a == '--time-per-tree' and i+1 < len(argv):
            time_per_tree = float(argv[i+1]); i += 2; continue
        if a == '--walking-speed' and i+1 < len(argv):
            walking_speed = float(argv[i+1]); i += 2; continue
        if a == '--haversine-multiplier' and i+1 < len(argv):
            haversine_multiplier = float(argv[i+1]); i += 2; continue
        i += 1

    if not graph_path:
        print('Error: --graph GRAPH.json is required')
        sys.exit(2)
    graph = load_json(graph_path)
    nodes = graph.get('nodes', [])
    distances = graph.get('distances', [])
    n = len(nodes)
    if clusters_path:
        clusters_data = load_json(clusters_path)
        clusters_list = clusters_data.get('clusters', [])
        results = {'routes': [], 'summary': {}}
        total_minutes = 0.0
        for c in clusters_list:
            members = c.get('member_node_indices') or c.get('members') or []
            res = compute_route_for_cluster(members, distances, time_per_tree, walking_speed, haversine_multiplier)
            res_out = {'cluster_id': c.get('cluster_id'), 'size': len(members), 'route': res['route'], 'route_meters': res['route_meters'], 'service_minutes': res['service_minutes'], 'route_minutes': res['route_minutes'], 'total_minutes': res['total_minutes']}
            total_minutes += res['total_minutes']
            results['routes'].append(res_out)
        results['summary']['total_minutes'] = total_minutes
        out_dir = os.path.dirname(out_path)
        if out_dir:
            os.makedirs(out_dir, exist_ok=True)
        with open(out_path, 'w', encoding='utf-8') as f:
            json.dump(results, f, ensure_ascii=False)
        print(f'Wrote routes for {len(results["routes"])} clusters to {out_path}')
    else:
        # compute single route for whole graph
        members = list(range(n))
        res = compute_route_for_cluster(members, distances, time_per_tree, walking_speed, haversine_multiplier)
        out = {'route': res['route'], 'route_meters': res['route_meters'], 'service_minutes': res['service_minutes'], 'route_minutes': res['route_minutes'], 'total_minutes': res['total_minutes']}
        out_dir = os.path.dirname(out_path)
        if out_dir:
            os.makedirs(out_dir, exist_ok=True)
        with open(out_path, 'w', encoding='utf-8') as f:
            json.dump(out, f, ensure_ascii=False)
        print(f'Wrote single route to {out_path}')


if __name__ == '__main__':
    main(sys.argv)
