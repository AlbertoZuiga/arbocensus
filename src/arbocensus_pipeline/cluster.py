"""Clustering helpers: recursive split and capacity assignment"""
from typing import List, Dict, Any, Tuple
import math
from .utils import two_opt, nn_tour


def bounding_box(nodes: List[Dict[str, Any]]) -> Tuple[float, float, float, float]:
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

    subset = [nodes[i] for i in node_list]
    axis = longest_axis(subset)
    if axis == 'lat':
        node_list.sort(key=lambda i: nodes[i]['lat'])
    else:
        node_list.sort(key=lambda i: nodes[i]['lng'])

    mid = len(node_list) // 2
    left = node_list[:mid]
    right = node_list[mid:]
    recursive_split(left, nodes, max_size, out_clusters)
    recursive_split(right, nodes, max_size, out_clusters)


def make_clusters_recursive(nodes: List[Dict[str, Any]], max_size: int = 100) -> List[List[int]]:
    n = len(nodes)
    if n == 0:
        return []
    all_ids = list(range(n))
    clusters: List[List[int]] = []
    recursive_split(all_ids, nodes, max_size, clusters)
    return clusters


def reorder_by_nn(cluster_members: List[int], distances: List[List[float]]) -> List[int]:
    if not cluster_members:
        return []
    tour = nn_tour(cluster_members[0], cluster_members, distances)
    if len(tour) > 2:
        tour = two_opt(tour, distances, max_iter=50)
    return tour
