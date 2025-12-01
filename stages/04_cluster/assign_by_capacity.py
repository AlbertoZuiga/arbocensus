#!/usr/bin/env python3
"""Assign trees to censantes by capacity (P0 - Haversine estimate).

Usage:
  python assign_by_capacity.py in_graph.json out_clusters.json --num-censantes 8

Outputs:
 - JSON with clusters and stats
 - per-cluster files `cluster_<id>.json` in the same folder as output

Algorithm (P0):
 - use kmeans++ seeding on node coordinates to pick representative centers
 - capacity = ceil(total_nodes / num_censantes)
 - assign nodes to nearest center greedily respecting capacity
 - estimate route length per-cluster via nearest-neighbor + optional 2-opt
 - compute service time = size * time_per_tree (minutes)
 - route minutes = meters -> minutes via walking_speed
"""
import json
import math
import os
import random
import sys
from typing import List, Dict, Any, Tuple


def haversine_m(lat1, lon1, lat2, lon2):
    R = 6371000.0
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2.0) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2.0) ** 2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c


def load_graph(path: str) -> Dict[str, Any]:
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)


def coords_from_nodes(nodes: List[Dict[str, Any]]) -> List[Tuple[float, float]]:
    return [(n['lat'], n['lng']) for n in nodes]


def kmeans_plus_plus_seeds(coords: List[Tuple[float, float]], k: int) -> List[int]:
    # coords: list of (lat,lng). Return indices of chosen seeds (node indices)
    n = len(coords)
    if k <= 0:
        return []
    seeds = []
    # pick first uniformly
    first = random.randrange(n)
    seeds.append(first)
    # distances squared to nearest seed
    dist2 = [0.0] * n
    for _ in range(1, k):
        total = 0.0
        for i in range(n):
            lat, lng = coords[i]
            s_lat, s_lng = coords[seeds[-1]]
            d = haversine_m(lat, lng, s_lat, s_lng)
            # compute distance to nearest existing seed
            if len(seeds) == 1:
                dist2[i] = d * d
            else:
                dist2[i] = min(dist2[i], d * d)
            total += dist2[i]
        if total == 0.0:
            # all points identical; pick random
            cand = random.randrange(n)
            seeds.append(cand)
            continue
        # pick next with probability proportional to dist2
        r = random.random() * total
        cum = 0.0
        for i in range(n):
            cum += dist2[i]
            if cum >= r:
                seeds.append(i)
                break
    return seeds


def assign_with_capacity(n_nodes: int, centers: List[int], distances: List[List[float]], capacity: int) -> Dict[int, List[int]]:
    # distances: n x n matrix in meters (symmetric). centers: node indices chosen as centers
    n = n_nodes
    k = len(centers)
    # precompute for each node the list of centers sorted by distance
    center_order = []
    for i in range(n):
        dlist = [(distances[i][c], idx) for idx, c in enumerate(centers)]
        dlist.sort(key=lambda x: x[0])
        center_order.append([ci for _, ci in dlist])

    clusters = {ci: [] for ci in range(k)}
    assigned = [False] * n

    # nodes sorted by distance to their nearest center (ascending)
    nodes_sorted = list(range(n))
    nodes_sorted.sort(key=lambda i: distances[i][centers[center_order[i][0]]])

    for i in nodes_sorted:
        for center_rank in center_order[i]:
            if len(clusters[center_rank]) < capacity:
                clusters[center_rank].append(i)
                assigned[i] = True
                break
        # if no center has capacity (shouldn't happen if capacity >= ceil(n/k)), assign to smallest cluster
        if not assigned[i]:
            smallest = min(clusters.items(), key=lambda x: len(x[1]))[0]
            clusters[smallest].append(i)
            assigned[i] = True

    return clusters


def nn_route_length(nodes_idx: List[int], distances: List[List[float]]) -> float:
    # returns total meters of NN tour (start at first node, return to start)
    if not nodes_idx:
        return 0.0
    unvisited = set(nodes_idx)
    curr = nodes_idx[0]
    unvisited.remove(curr)
    tour = [curr]
    total = 0.0
    while unvisited:
        nxt = min(unvisited, key=lambda x: distances[curr][x])
        total += distances[curr][nxt]
        curr = nxt
        tour.append(curr)
        unvisited.remove(curr)
    # return to start
    total += distances[curr][tour[0]]
    return total


def two_opt(route: List[int], distances: List[List[float]], max_iter: int = 50) -> List[int]:
    # simple 2-opt improving swap
    best = route[:]
    improved = True
    it = 0
    def route_length(r):
        s = 0.0
        for i in range(len(r)-1):
            s += distances[r[i]][r[i+1]]
        s += distances[r[-1]][r[0]]
        return s

    best_len = route_length(best)
    while improved and it < max_iter:
        improved = False
        it += 1
        for i in range(1, len(best)-2):
            for j in range(i+1, len(best)-1):
                if j - i == 1:
                    continue
                new_route = best[:i] + best[i:j+1][::-1] + best[j+1:]
                new_len = route_length(new_route)
                if new_len + 1e-6 < best_len:
                    best = new_route
                    best_len = new_len
                    improved = True
                    break
            if improved:
                break
    return best


def cluster_stats(cluster_nodes: List[int], distances: List[List[float]], time_per_tree: float, walking_speed_kmh: float, haversine_multiplier: float = 1.0) -> Dict[str, Any]:
    size = len(cluster_nodes)
    service_minutes = size * float(time_per_tree)
    if size <= 1:
        route_m = 0.0
    else:
        nn_m = nn_route_length(cluster_nodes, distances)
        # try light 2-opt
        try:
            route = cluster_nodes[:]
            route = two_opt(route, distances, max_iter=30)
            opt_m = 0.0
            for i in range(len(route)-1):
                opt_m += distances[route[i]][route[i+1]]
            opt_m += distances[route[-1]][route[0]]
            route_m = min(nn_m, opt_m)
        except Exception:
            route_m = nn_m
    # convert meters to minutes: minutes = meters * (60/1000) / kmh
    minutes = route_m * (60.0 / 1000.0) / float(walking_speed_kmh)
    minutes = minutes * float(haversine_multiplier)
    total_minutes = service_minutes + minutes
    return {
        'size': size,
        'service_minutes': service_minutes,
        'route_minutes': minutes,
        'total_minutes': total_minutes,
        'route_meters': route_m
    }


def save_output(out_path: str, clusters: Dict[int, List[int]], centers: List[int], nodes: List[Dict[str, Any]], distances: List[List[float]], time_per_tree: float, walking_speed_kmh: float, haversine_multiplier: float):
    out_dir = os.path.dirname(out_path)
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)
    result = {'clusters': [], 'summary': {}}
    cluster_objs = []
    total_minutes = 0.0
    for cid, members in clusters.items():
        stats = cluster_stats(members, distances, time_per_tree, walking_speed_kmh, haversine_multiplier)
        total_minutes += stats['total_minutes']
        cluster_obj = {
            'cluster_id': cid,
            'center_node': centers[cid],
            'member_node_indices': members,
            'size': stats['size'],
            'service_minutes': stats['service_minutes'],
            'route_minutes': stats['route_minutes'],
            'total_minutes': stats['total_minutes']
        }
        cluster_objs.append(cluster_obj)
        # write per-cluster file
        per_path = os.path.join(out_dir, f'cluster_{cid}.json')
        with open(per_path, 'w', encoding='utf-8') as f:
            json.dump(cluster_obj, f, ensure_ascii=False)

    result['clusters'] = cluster_objs
    result['summary']['num_clusters'] = len(clusters)
    result['summary']['total_minutes'] = total_minutes
    with open(out_path, 'w', encoding='utf-8') as f:
        json.dump(result, f, ensure_ascii=False)


def main(argv: List[str]):
    if len(argv) < 3:
        print('Usage: python assign_by_capacity.py in_graph.json out_clusters.json --num-censantes N [--time-per-tree 1.5] [--walking-speed 5]')
        sys.exit(2)
    inp = argv[1]
    outp = argv[2]
    # simple arg parsing
    num_censantes = 8
    time_per_tree = 1.5
    walking_speed = 5.0
    haversine_multiplier = 1.25
    i = 3
    while i < len(argv):
        a = argv[i]
        if a in ('--num-censantes', '--num') and i+1 < len(argv):
            num_censantes = int(argv[i+1]); i += 2; continue
        if a == '--time-per-tree' and i+1 < len(argv):
            time_per_tree = float(argv[i+1]); i += 2; continue
        if a == '--walking-speed' and i+1 < len(argv):
            walking_speed = float(argv[i+1]); i += 2; continue
        if a == '--haversine-multiplier' and i+1 < len(argv):
            haversine_multiplier = float(argv[i+1]); i += 2; continue
        i += 1

    data = load_graph(inp)
    nodes = data.get('nodes', [])
    distances = data.get('distances', [])
    n = len(nodes)
    if n == 0:
        print('No nodes found in graph input')
        sys.exit(1)
    if num_censantes <= 0:
        num_censantes = 1
    num_censantes = min(num_censantes, n)
    capacity = math.ceil(n / num_censantes)
    coords = coords_from_nodes(nodes)
    k = num_censantes
    seeds = kmeans_plus_plus_seeds(coords, k)
    print(f'Picked seeds: {seeds}')
    clusters = assign_with_capacity(n, seeds, distances, capacity)
    # map clusters keys to consecutive cluster ids (0..k-1)
    save_output(outp, clusters, seeds, nodes, distances, time_per_tree, walking_speed, haversine_multiplier)
    print(f'Wrote clusters to {outp} (k={k}, capacity={capacity})')


if __name__ == '__main__':
    main(sys.argv)
