import requests
from django.conf import settings


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
