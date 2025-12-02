"""Filter stage utilities"""

from typing import Any, Dict


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


def filter_trees(obj: Dict[str, Any]) -> Dict[str, Any]:
    trees = obj.get("trees", [])
    poly_coords = None
    if obj.get("polygon"):
        coords = obj["polygon"].get("coordinates")
        if coords and len(coords) > 0:
            ring = coords[0]
            poly_coords = [(p[0], p[1]) for p in ring]

    seen = set()
    out = []
    for t in trees:
        lat = None
        lng = None
        if isinstance(t, dict):
            lat = t.get("lat") or t.get("latitude")
            lng = t.get("lng") or t.get("longitude")
        if lat is None or lng is None:
            continue
        try:
            latf = float(lat)
            lngf = float(lng)
        except Exception:
            continue
        key = (round(latf, 6), round(lngf, 6))
        if key in seen:
            continue
        if poly_coords:
            if not point_in_poly(lngf, latf, poly_coords):
                continue
        seen.add(key)
        out.append(
            {
                "lat": latf,
                "lng": lngf,
                "meta": t.get("meta") if isinstance(t, dict) else None,
            }
        )

    res = obj.copy()
    res["trees"] = out
    return res
