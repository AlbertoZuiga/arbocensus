"""Graph stage: build nodes and distance matrix"""

from typing import Any, Dict, List

from .utils import haversine_m


def build_nodes(trees: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    nodes = []
    for i, t in enumerate(trees):
        lat = t.get("lat") if isinstance(t, dict) else None
        lng = t.get("lng") if isinstance(t, dict) else None
        if lat is None:
            lat = t.get("latitude")
        if lng is None:
            lng = t.get("longitude")
        nodes.append(
            {
                "id": i,
                "lat": float(lat),
                "lng": float(lng),
                "meta": t.get("meta") if isinstance(t, dict) else None,
            }
        )
    return nodes


def compute_matrix(nodes: List[Dict[str, Any]]) -> List[List[float]]:
    n = len(nodes)
    mat = [[0.0] * n for _ in range(n)]
    for i in range(n):
        lat1 = nodes[i]["lat"]
        lon1 = nodes[i]["lng"]
        for j in range(i + 1, n):
            lat2 = nodes[j]["lat"]
            lon2 = nodes[j]["lng"]
            d = haversine_m(lat1, lon1, lat2, lon2)
            mat[i][j] = d
            mat[j][i] = d
    return mat
