from contextlib import closing
from dataclasses import dataclass

import psycopg2
from django.conf import settings
from django.contrib.gis.geos import Point, Polygon
from django.db import transaction

from .models import Dataset, Tree

SOURCE_API = "legacy_api"
SOURCE_APP = "legacy_app"
SOURCES = (SOURCE_API, SOURCE_APP)


class LegacyDatabaseNotConfiguredError(Exception):
    pass


_API_AREAS_SQL = """
    SELECT a.id, a.name, c.name, a.coordinates
    FROM arbocensus_api_app_area a
    JOIN arbocensus_api_app_campaign c ON c.id = a.campaign_id
    ORDER BY a.id
"""

_API_TREES_SQL = """
    SELECT id, latitude, longitude, COALESCE(tree_species, '')
    FROM arbocensus_api_app_tree
    ORDER BY id
"""

_APP_TREES_SQL = """
    SELECT s.qr::bigint,
           percentile_cont(0.5) WITHIN GROUP (ORDER BY s.latitude),
           percentile_cont(0.5) WITHIN GROUP (ORDER BY s.longitude)
    FROM arbocensus_app_sample s
    JOIN (SELECT DISTINCT tree_id FROM arbocensus_app_mltree) m ON m.tree_id = s.qr
    WHERE s.latitude IS NOT NULL AND s.longitude IS NOT NULL AND s.latitude <> 0
    GROUP BY s.qr
    ORDER BY 1
"""


@dataclass
class LegacyTreeRow:
    source: str
    external_id: int
    lat: float
    lon: float
    species: str = ""


@dataclass
class LegacyAreaImport:
    dataset_name: str
    trees: list[LegacyTreeRow]


def _fetch(env_name: str, url: str, statements: list[str]) -> list[list[tuple]]:
    if not url:
        raise LegacyDatabaseNotConfiguredError(
            f"{env_name} is not configured; legacy import is unavailable."
        )
    with closing(psycopg2.connect(url)) as conn:
        conn.set_session(readonly=True, autocommit=True)
        with conn.cursor() as cursor:
            results = []
            for sql in statements:
                cursor.execute(sql)
                results.append(cursor.fetchall())
    return results


def _load_api():
    areas, trees = _fetch(
        "ARBOCENSUS_API_DB_URL",
        settings.LEGACY_API_DB_URL,
        [_API_AREAS_SQL, _API_TREES_SQL],
    )
    return areas, trees


def _load_app_trees() -> list[LegacyTreeRow]:
    (rows,) = _fetch("ARBOCENSUS_DB_URL", settings.LEGACY_APP_DB_URL, [_APP_TREES_SQL])
    return [
        LegacyTreeRow(source=SOURCE_APP, external_id=tree_id, lat=lat, lon=lon)
        for tree_id, lat, lon in rows
    ]


def _api_tree_rows() -> list[LegacyTreeRow]:
    _, trees = _load_api()
    return [
        LegacyTreeRow(
            source=SOURCE_API, external_id=tree_id, lat=lat, lon=lon, species=species
        )
        for tree_id, lat, lon, species in trees
    ]


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
        LegacyTreeRow(
            source=SOURCE_API, external_id=tree_id, lat=lat, lon=lon, species=species
        )
        for tree_id, lat, lon, species in trees
        if polygon.contains(Point(lon, lat))
    ]


def list_areas() -> list[dict]:
    areas, trees = _load_api()
    return [
        {
            "id": area_id,
            "name": name,
            "campaign": campaign,
            "tree_count": len(_trees_in_area(coordinates, trees)),
        }
        for area_id, name, campaign, coordinates in areas
    ]


def list_trees() -> list[dict]:
    rows: list[LegacyTreeRow] = []
    errors = []
    for loader in (_api_tree_rows, _load_app_trees):
        try:
            rows.extend(loader())
        except LegacyDatabaseNotConfiguredError as exc:
            errors.append(exc)
    if len(errors) == len(SOURCES):
        raise LegacyDatabaseNotConfiguredError(
            "Neither ARBOCENSUS_API_DB_URL nor ARBOCENSUS_DB_URL is configured; "
            "legacy import is unavailable."
        )
    imported = set(
        Tree.objects.filter(source__in=SOURCES, external_id__isnull=False).values_list(
            "source", "external_id"
        )
    )
    return [
        {
            "source": row.source,
            "external_id": row.external_id,
            "lat": row.lat,
            "lon": row.lon,
            "species": row.species,
            "already_imported": (row.source, row.external_id) in imported,
        }
        for row in rows
    ]


def load_selection(selection: list[tuple[str, int]]) -> list[LegacyTreeRow]:
    requested_sources = {source for source, _ in selection}
    available: dict[tuple[str, int], LegacyTreeRow] = {}
    if SOURCE_API in requested_sources:
        for row in _api_tree_rows():
            available[(row.source, row.external_id)] = row
    if SOURCE_APP in requested_sources:
        for row in _load_app_trees():
            available[(row.source, row.external_id)] = row
    missing = [key for key in selection if key not in available]
    if missing:
        raise ValueError(f"Unknown legacy trees: {missing}")
    return [available[key] for key in selection]


def import_area(area_id: int) -> LegacyAreaImport:
    areas, trees = _load_api()
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
    areas, trees = _load_api()
    imports = [
        LegacyAreaImport(
            dataset_name=f"{campaign} — {name}",
            trees=_trees_in_area(coordinates, trees),
        )
        for _, name, campaign, coordinates in areas
    ]
    return [area_import for area_import in imports if area_import.trees]


def create_dataset(name: str, rows: list[LegacyTreeRow]) -> Dataset:
    with transaction.atomic():
        dataset = Dataset.objects.create(name=name, total_trees=len(rows))
        Tree.objects.bulk_create(
            Tree(
                dataset=dataset,
                location=Point(row.lon, row.lat),
                species=row.species,
                source=row.source,
                external_id=row.external_id,
            )
            for row in rows
        )
    return dataset


def create_datasets(imports: list[LegacyAreaImport]) -> list[Dataset]:
    with transaction.atomic():
        return [
            create_dataset(area_import.dataset_name, area_import.trees)
            for area_import in imports
        ]
