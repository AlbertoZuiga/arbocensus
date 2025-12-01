#!/usr/bin/env python3
"""Filter trees: remove duplicates, missing coords, optional polygon clipping.

Usage:
  python filter.py input.json output.json

Produces a JSON with same bbox fields and `trees` array of filtered points.
"""
import json
import sys
import os
from typing import List, Dict, Any


def point_in_poly(x, y, poly):
    # Ray casting algorithm for point in polygon. poly = [(lng, lat), ...]
    inside = False
    n = len(poly)
    for i in range(n):
        xi, yi = poly[i]
        xj, yj = poly[(i + 1) % n]
        intersect = ((yi > y) != (yj > y)) and (x < (xj - xi) * (y - yi) / (yj - yi + 1e-16) + xi)
        if intersect:
            inside = not inside
    return inside


def load_json(path: str) -> Dict[str, Any]:
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)


def save_json(obj: Dict[str, Any], path: str) -> None:
    d = os.path.dirname(path)
    if d:
        os.makedirs(d, exist_ok=True)
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(obj, f, indent=2)


def filter_trees(obj: Dict[str, Any]) -> Dict[str, Any]:
    trees = obj.get('trees', [])
    poly_coords = None
    if obj.get('polygon'):
        coords = obj['polygon'].get('coordinates')
        if coords and len(coords) > 0:
            # assume first ring
            ring = coords[0]
            # ring is list of [lng, lat]
            poly_coords = [(p[0], p[1]) for p in ring]

    seen = set()
    out = []
    for t in trees:
        lat = None
        lng = None
        if isinstance(t, dict):
            lat = t.get('lat') or t.get('latitude')
            lng = t.get('lng') or t.get('longitude')
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
        out.append({'lat': latf, 'lng': lngf, 'meta': t.get('meta') if isinstance(t, dict) else None})

    res = obj.copy()
    res['trees'] = out
    return res


def main(argv: List[str]):
    if len(argv) < 3:
        print('Usage: python filter.py input.json output.json')
        sys.exit(2)
    inp = argv[1]
    outp = argv[2]
    data = load_json(inp)
    filtered = filter_trees(data)
    save_json(filtered, outp)
    print(f'Filtered {len(data.get("trees", []))} -> {len(filtered.get("trees", []))} trees')


if __name__ == '__main__':
    main(sys.argv)
