"""Filter stage utilities"""

from typing import Any, Dict, List, Optional, Tuple


def point_in_poly(x, y, poly):
    inside = False
    n = len(poly)
    for i in range(n):
        xi, yi = poly[i]
        xj, yj = poly[(i + 1) % n]
        intersect = ((yi > y) != (yj > y)) and (
            x < (xj - xi) * (y - yi) / (yj - yi + 1e-16) + xi
        )
        if intersect:
            inside = not inside
    return inside


def _extract_polygon_coords(obj: Dict[str, Any]) -> Optional[List[Tuple[float, float]]]:
    """Extract polygon coordinates from bbox object."""
    if not obj.get("polygon"):
        return None
    coords = obj["polygon"].get("coordinates")
    if coords and len(coords) > 0:
        ring = coords[0]
        return [(p[0], p[1]) for p in ring]
    return None


def _extract_lat_lng(tree: Any) -> Tuple[Optional[float], Optional[float]]:
    """Extract latitude and longitude from tree object."""
    if not isinstance(tree, dict):
        return None, None
    lat = tree.get("lat") or tree.get("latitude")
    lng = tree.get("lng") or tree.get("longitude")
    return lat, lng


def _convert_to_float(lat, lng) -> Optional[Tuple[float, float]]:
    """Convert lat/lng to float, return None if invalid."""
    try:
        return float(lat), float(lng)
    except (ValueError, TypeError):
        return None


def _is_within_polygon(lngf: float, latf: float, poly_coords: Optional[List]) -> bool:
    """Check if point is within polygon, or True if no polygon."""
    if not poly_coords:
        return True
    return point_in_poly(lngf, latf, poly_coords)


def _create_tree_entry(latf: float, lngf: float, tree: Any) -> Dict[str, Any]:
    """Create a filtered tree entry."""
    return {
        "lat": latf,
        "lng": lngf,
        "meta": tree.get("meta") if isinstance(tree, dict) else None,
    }


def filter_trees(obj: Dict[str, Any]) -> Dict[str, Any]:
    trees = obj.get("trees", [])
    poly_coords = _extract_polygon_coords(obj)

    seen = set()
    out = []

    for tree in trees:
        lat, lng = _extract_lat_lng(tree)
        if lat is None or lng is None:
            continue

        coords = _convert_to_float(lat, lng)
        if coords is None:
            continue
        latf, lngf = coords

        key = (round(latf, 6), round(lngf, 6))
        if key in seen:
            continue

        if not _is_within_polygon(lngf, latf, poly_coords):
            continue

        seen.add(key)
        out.append(_create_tree_entry(latf, lngf, tree))

    res = obj.copy()
    res["trees"] = out
    return res
