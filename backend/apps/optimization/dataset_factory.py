import math

import requests
from apps.datasets.models import Dataset, Tree
from django.conf import settings
from django.contrib.gis.geos import Point

LAT_MIN, LAT_MAX = -33.45, -33.41
LON_MIN, LON_MAX = -70.66, -70.58

DISTRIBUTIONS = ("uniform", "clustered", "multizone")

CLUSTER_SPREAD_M = 250.0

MULTIZONE = (
    (-33.430, -70.620, 400.0, 0.5),
    (-33.415, -70.600, 600.0, 0.3),
    (-33.445, -70.590, 900.0, 0.2),
)


def _meters_to_deg_lat(meters):
    return meters / 111_000.0


def _meters_to_deg_lon(meters, lat):
    return meters / (111_000.0 * math.cos(math.radians(lat)))


def _gaussian_point(rng, lat_c, lon_c, spread_m):
    lat = lat_c + rng.gauss(0, _meters_to_deg_lat(spread_m))
    lon = lon_c + rng.gauss(0, _meters_to_deg_lon(spread_m, lat_c))
    lat = min(max(lat, LAT_MIN), LAT_MAX)
    lon = min(max(lon, LON_MIN), LON_MAX)
    return (lon, lat)


def _uniform(rng, n):
    return [
        (rng.uniform(LON_MIN, LON_MAX), rng.uniform(LAT_MIN, LAT_MAX)) for _ in range(n)
    ]


def _clustered(rng, n, clusters):
    centers = [
        (rng.uniform(LON_MIN, LON_MAX), rng.uniform(LAT_MIN, LAT_MAX))
        for _ in range(clusters)
    ]
    points = []
    for _ in range(n):
        lon_c, lat_c = rng.choice(centers)
        points.append(_gaussian_point(rng, lat_c, lon_c, CLUSTER_SPREAD_M))
    return points


def _multizone(rng, n):
    zones = [(lat, lon, spread) for lat, lon, spread, _ in MULTIZONE]
    weights = [weight for *_, weight in MULTIZONE]
    points = []
    for _ in range(n):
        lat_c, lon_c, spread = rng.choices(zones, weights=weights, k=1)[0]
        points.append(_gaussian_point(rng, lat_c, lon_c, spread))
    return points


def generate_points(rng, n, distribution, clusters):
    if distribution == "uniform":
        return _uniform(rng, n)
    if distribution == "clustered":
        return _clustered(rng, n, clusters)
    if distribution == "multizone":
        return _multizone(rng, n)
    raise ValueError(f"Unknown distribution: {distribution}")


def snap_to_streets(points):
    snapped = []
    for lon, lat in points:
        url = f"{settings.OSRM_URL}/nearest/v1/foot/{lon},{lat}"
        response = requests.get(url, timeout=30)
        response.raise_for_status()
        body = response.json()
        if body.get("code") != "Ok":
            snapped.append((lon, lat))
            continue
        snap_lon, snap_lat = body["waypoints"][0]["location"]
        snapped.append((snap_lon, snap_lat))
    return snapped


def create_dataset(name, points):
    dataset = Dataset.objects.create(name=name)
    Tree.objects.bulk_create(
        [Tree(dataset=dataset, location=Point(lon, lat)) for lon, lat in points]
    )
    dataset.total_trees = len(points)
    dataset.save(update_fields=["total_trees"])
    return dataset
