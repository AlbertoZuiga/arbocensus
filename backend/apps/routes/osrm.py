from concurrent.futures import ThreadPoolExecutor

import requests
from django.conf import settings

# Bounded so a solution with many routes cannot flood the single OSRM container.
MAX_PARALLEL_ROUTE_REQUESTS = 8


def fetch_route_path(coordinates):
    if len(coordinates) < 2:
        return coordinates
    coords = ";".join(f"{lon},{lat}" for lon, lat in coordinates)
    url = f"{settings.OSRM_URL}/route/v1/foot/{coords}"
    response = requests.get(
        url,
        params={"overview": "full", "geometries": "geojson"},
        timeout=60,
    )
    response.raise_for_status()
    return response.json()["routes"][0]["geometry"]["coordinates"]


def fetch_route_paths(coordinate_lists):
    if not coordinate_lists:
        return []
    workers = min(MAX_PARALLEL_ROUTE_REQUESTS, len(coordinate_lists))
    with ThreadPoolExecutor(max_workers=workers) as executor:
        return list(executor.map(fetch_route_path, coordinate_lists))
