from contextlib import closing
from dataclasses import dataclass

import psycopg2
from django.conf import settings
from django.contrib.gis.geos import Point, Polygon
from django.db import transaction

from .models import Dataset, Tree


class LegacyDatabaseNotConfiguredError(Exception):
    pass


_AREAS_SQL = """
    SELECT a.id, a.name, c.name, a.coordinates
    FROM arbocensus_api_app_area a
    JOIN arbocensus_api_app_campaign c ON c.id = a.campaign_id
    ORDER BY a.id
"""

_TREES_SQL = """
    SELECT id, latitude, longitude, COALESCE(tree_species, '')
    FROM arbocensus_api_app_tree
    ORDER BY id
"""


@dataclass
class LegacyTreeRow:
    external_id: int
    lat: float
    lon: float
    species: str


@dataclass
class LegacyAreaImport:
    dataset_name: str
    trees: list[LegacyTreeRow]


def _load():
    url = settings.LEGACY_DB_URL
    if not url:
        raise LegacyDatabaseNotConfiguredError(
            "LEGACY_DB_URL is not configured; legacy import is unavailable."
        )
    with closing(psycopg2.connect(url)) as conn:
        conn.set_session(readonly=True, autocommit=True)
        with conn.cursor() as cursor:
            cursor.execute(_AREAS_SQL)
            areas = cursor.fetchall()
            cursor.execute(_TREES_SQL)
            trees = cursor.fetchall()
    return areas, trees


def _polygon(coordinates):
    ring = [(lon, lat) for lat, lon in coordinates]
    if len(ring) < 3:
        return None
    if ring[0] != ring[-1]:
        ring.append(ring[0])
    return Polygon(ring)


def _trees_in_area(coordinates, trees) -> list[LegacyTreeRow]:
    polygon = _polygon(coordinates)
    if polygon is None:
        return []
    return [
        LegacyTreeRow(external_id=tree_id, lat=lat, lon=lon, species=species)
        for tree_id, lat, lon, species in trees
        if polygon.contains(Point(lon, lat))
    ]


def list_areas() -> list[dict]:
    areas, trees = _load()
    return [
        {
            "id": area_id,
            "name": name,
            "campaign": campaign,
            "tree_count": len(_trees_in_area(coordinates, trees)),
        }
        for area_id, name, campaign, coordinates in areas
    ]


def import_area(area_id: int) -> LegacyAreaImport:
    areas, trees = _load()
    for row_id, name, campaign, coordinates in areas:
        if row_id == area_id:
            area_trees = _trees_in_area(coordinates, trees)
            if not area_trees:
                raise ValueError(f"Legacy area {area_id} has no trees")
            return LegacyAreaImport(
                dataset_name=f"{campaign} — {name}",
                trees=area_trees,
            )
    raise ValueError(f"Legacy area {area_id} does not exist")


def import_all() -> list[LegacyAreaImport]:
    areas, trees = _load()
    imports = [
        LegacyAreaImport(
            dataset_name=f"{campaign} — {name}",
            trees=_trees_in_area(coordinates, trees),
        )
        for _, name, campaign, coordinates in areas
    ]
    return [area_import for area_import in imports if area_import.trees]


def create_datasets(imports: list[LegacyAreaImport]) -> list[Dataset]:
    datasets = []
    with transaction.atomic():
        for area_import in imports:
            dataset = Dataset.objects.create(
                name=area_import.dataset_name,
                total_trees=len(area_import.trees),
            )
            Tree.objects.bulk_create(
                Tree(
                    dataset=dataset,
                    location=Point(row.lon, row.lat),
                    species=row.species,
                    external_id=row.external_id,
                )
                for row in area_import.trees
            )
            datasets.append(dataset)
    return datasets
