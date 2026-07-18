import math
from contextlib import closing
from dataclasses import dataclass
from datetime import datetime

import psycopg2
from apps.routes.models import TreeObservation
from django.conf import settings
from django.contrib.gis.geos import Point, Polygon
from django.db import transaction

from .models import Dataset, Tree

SOURCE_API = "legacy_api"
SOURCE_APP = "legacy_app"
SOURCES = (SOURCE_API, SOURCE_APP)

_DEDUP_RADIUS_M = 5.0
_DEDUP_CELL_DEG = 0.0001


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
    WHERE s.qr IS NOT NULL AND s.qr <> '' AND s.qr !~ '^0+$'
      AND s.latitude IS NOT NULL AND s.longitude IS NOT NULL
      AND s.latitude BETWEEN -56 AND -17
      AND s.longitude BETWEEN -76 AND -66
    GROUP BY s.qr
    ORDER BY 1
"""

_API_OBSERVATIONS_SQL = """
    SELECT s.real_tree_id, s.date, s.completed,
           COALESCE(
               (SELECT a.answer_url FROM arbocensus_api_app_answer a
                WHERE a.sample_id = s.id AND a.answer_url <> ''
                ORDER BY a.id LIMIT 1),
               ''
           )
    FROM arbocensus_api_app_sample s
    WHERE s.real_tree_id = ANY(%s)
    ORDER BY s.date
"""

_APP_OBSERVATIONS_SQL = """
    SELECT s.qr::bigint, s.date, s.complete,
           COALESCE(
               (SELECT a.answer_url FROM arbocensus_app_answer a
                WHERE a.sample_id = s.id AND a.answer_url LIKE 'http%%'
                ORDER BY a.id LIMIT 1),
               ''
           )
    FROM arbocensus_app_sample s
    WHERE s.qr = ANY(%s)
    ORDER BY s.date
"""


@dataclass
class LegacyTreeRow:
    source: str
    external_id: int
    lat: float
    lon: float
    species: str = ""
    area_id: int | None = None


@dataclass
class LegacyAreaImport:
    dataset_name: str
    trees: list[LegacyTreeRow]
    area_id: int | None = None


@dataclass
class LegacyObservationRow:
    source: str
    tree_external_id: int
    observed_at: datetime
    completed: bool
    photo_url: str = ""


def _fetch(
    env_name: str, url: str, statements: list[tuple[str, tuple | None]]
) -> list[list[tuple]]:
    if not url:
        raise LegacyDatabaseNotConfiguredError(
            f"{env_name} is not configured; legacy import is unavailable."
        )
    with closing(psycopg2.connect(url)) as conn:
        conn.set_session(readonly=True, autocommit=True)
        with conn.cursor() as cursor:
            results = []
            for sql, params in statements:
                cursor.execute(sql, params)
                results.append(cursor.fetchall())
    return results


def _load_api():
    areas, trees = _fetch(
        "ARBOCENSUS_API_DB_URL",
        settings.LEGACY_API_DB_URL,
        [(_API_AREAS_SQL, None), (_API_TREES_SQL, None)],
    )
    return areas, trees


def _load_app_trees() -> list[LegacyTreeRow]:
    (rows,) = _fetch(
        "ARBOCENSUS_DB_URL", settings.LEGACY_APP_DB_URL, [(_APP_TREES_SQL, None)]
    )
    return [
        LegacyTreeRow(source=SOURCE_APP, external_id=tree_id, lat=lat, lon=lon)
        for tree_id, lat, lon in rows
    ]


def _load_api_observations(external_ids: list[int]) -> list[LegacyObservationRow]:
    (rows,) = _fetch(
        "ARBOCENSUS_API_DB_URL",
        settings.LEGACY_API_DB_URL,
        [(_API_OBSERVATIONS_SQL, (external_ids,))],
    )
    return [
        LegacyObservationRow(
            source=SOURCE_API,
            tree_external_id=tree_id,
            observed_at=observed_at,
            completed=completed,
            photo_url=photo_url,
        )
        for tree_id, observed_at, completed, photo_url in rows
    ]


def _load_app_observations(external_ids: list[int]) -> list[LegacyObservationRow]:
    (rows,) = _fetch(
        "ARBOCENSUS_DB_URL",
        settings.LEGACY_APP_DB_URL,
        [(_APP_OBSERVATIONS_SQL, ([str(tree_id) for tree_id in external_ids],))],
    )
    return [
        LegacyObservationRow(
            source=SOURCE_APP,
            tree_external_id=tree_id,
            observed_at=observed_at,
            completed=completed,
            photo_url=photo_url,
        )
        for tree_id, observed_at, completed, photo_url in rows
    ]


def _api_tree_rows() -> list[LegacyTreeRow]:
    areas, trees = _load_api()
    polygons = [
        (area_id, polygon)
        for area_id, _, _, coordinates in areas
        if (polygon := _polygon(coordinates)) is not None
    ]
    rows = []
    for tree_id, lat, lon, species in trees:
        point = Point(lon, lat)
        area_id = next(
            (aid for aid, polygon in polygons if polygon.contains(point)), None
        )
        rows.append(
            LegacyTreeRow(
                source=SOURCE_API,
                external_id=tree_id,
                lat=lat,
                lon=lon,
                species=species,
                area_id=area_id,
            )
        )
    return rows


def _polygon(coordinates):
    ring = [(lon, lat) for lat, lon in coordinates]
    if len(ring) < 3:
        return None
    if ring[0] != ring[-1]:
        ring.append(ring[0])
    return Polygon(ring)


def _polygon_geojson(polygon):
    if polygon is None:
        return None
    return {
        "type": "Polygon",
        "coordinates": [[list(point) for point in polygon.coords[0]]],
    }


def _trees_in_area(polygon, trees) -> list[LegacyTreeRow]:
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
    result = []
    for area_id, name, campaign, coordinates in areas:
        polygon = _polygon(coordinates)
        result.append(
            {
                "id": area_id,
                "name": name,
                "campaign": campaign,
                "tree_count": len(_trees_in_area(polygon, trees)),
                "polygon": _polygon_geojson(polygon),
            }
        )
    return result


def _haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    radius = 6371000
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = (
        math.sin(dphi / 2) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    )
    return 2 * radius * math.asin(math.sqrt(a))


def _dedup_app_against_api(
    api_rows: list[LegacyTreeRow], app_rows: list[LegacyTreeRow]
) -> list[LegacyTreeRow]:
    """Drop app trees co-located with an api tree; the api row is preferred because
    it carries species and area. The api extent is contained in the app extent, so
    the same physical tree can appear in both sources within GPS noise."""
    if not api_rows or not app_rows:
        return app_rows
    grid: dict[tuple[int, int], list[LegacyTreeRow]] = {}
    for row in api_rows:
        key = (round(row.lat / _DEDUP_CELL_DEG), round(row.lon / _DEDUP_CELL_DEG))
        grid.setdefault(key, []).append(row)
    kept = []
    for app_row in app_rows:
        base_lat = round(app_row.lat / _DEDUP_CELL_DEG)
        base_lon = round(app_row.lon / _DEDUP_CELL_DEG)
        neighbors = (
            api_row
            for dlat in (-1, 0, 1)
            for dlon in (-1, 0, 1)
            for api_row in grid.get((base_lat + dlat, base_lon + dlon), [])
        )
        if not any(
            _haversine_m(app_row.lat, app_row.lon, api_row.lat, api_row.lon)
            <= _DEDUP_RADIUS_M
            for api_row in neighbors
        ):
            kept.append(app_row)
    return kept


def list_trees() -> list[dict]:
    loaded: dict[str, list[LegacyTreeRow]] = {}
    errors = []
    for source, loader in ((SOURCE_API, _api_tree_rows), (SOURCE_APP, _load_app_trees)):
        try:
            loaded[source] = loader()
        except LegacyDatabaseNotConfiguredError as exc:
            errors.append(exc)
    if len(errors) == len(SOURCES):
        raise LegacyDatabaseNotConfiguredError(
            "Neither ARBOCENSUS_API_DB_URL nor ARBOCENSUS_DB_URL is configured; "
            "legacy import is unavailable."
        )
    api_rows = loaded.get(SOURCE_API, [])
    app_rows = loaded.get(SOURCE_APP, [])
    rows = api_rows + _dedup_app_against_api(api_rows, app_rows)
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
            "area_id": row.area_id,
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
            area_trees = _trees_in_area(_polygon(coordinates), trees)
            if not area_trees:
                raise ValueError(f"Legacy area {area_id} has no trees")
            return LegacyAreaImport(
                dataset_name=f"{campaign} — {name}",
                trees=area_trees,
            )
    raise ValueError(f"Legacy area {area_id} does not exist")


def list_distinct_areas() -> list[LegacyAreaImport]:
    """Non-empty areas deduplicated by polygon geometry.

    The same area is re-created for every campaign it takes part in, and area names
    are reused across unrelated geometries, so the geometry is the only stable key.
    Areas arrive ordered by id, so the first occurrence is the canonical one.
    """
    areas, trees = _load_api()
    distinct: dict[tuple, LegacyAreaImport] = {}
    for area_id, name, campaign, coordinates in areas:
        polygon = _polygon(coordinates)
        if polygon is None:
            continue
        area_trees = _trees_in_area(polygon, trees)
        if not area_trees:
            continue
        key = tuple(polygon.coords[0])
        distinct.setdefault(
            key,
            LegacyAreaImport(
                dataset_name=f"{campaign} — {name}",
                trees=area_trees,
                area_id=area_id,
            ),
        )
    return list(distinct.values())


def all_tree_rows() -> list[LegacyTreeRow]:
    _, trees = _load_api()
    api_rows = [
        LegacyTreeRow(
            source=SOURCE_API, external_id=tree_id, lat=lat, lon=lon, species=species
        )
        for tree_id, lat, lon, species in trees
    ]
    return api_rows + _dedup_app_against_api(api_rows, _load_app_trees())


def import_all() -> list[LegacyAreaImport]:
    areas, trees = _load_api()
    imports = [
        LegacyAreaImport(
            dataset_name=f"{campaign} — {name}",
            trees=_trees_in_area(_polygon(coordinates), trees),
        )
        for _, name, campaign, coordinates in areas
    ]
    return [area_import for area_import in imports if area_import.trees]


def _load_observations(
    rows: list[LegacyTreeRow],
) -> dict[tuple[str, int], list[LegacyObservationRow]]:
    loaders = {SOURCE_API: _load_api_observations, SOURCE_APP: _load_app_observations}
    grouped: dict[tuple[str, int], list[LegacyObservationRow]] = {}
    for source, loader in loaders.items():
        external_ids = [row.external_id for row in rows if row.source == source]
        if not external_ids:
            continue
        for observation in loader(external_ids):
            key = (observation.source, observation.tree_external_id)
            grouped.setdefault(key, []).append(observation)
    return grouped


def create_dataset(name: str, rows: list[LegacyTreeRow]) -> Dataset:
    observations = _load_observations(rows)
    with transaction.atomic():
        dataset = Dataset.objects.create(name=name, total_trees=len(rows))
        trees = Tree.objects.bulk_create(
            Tree(
                dataset=dataset,
                location=Point(row.lon, row.lat),
                species=row.species,
                source=row.source,
                external_id=row.external_id,
            )
            for row in rows
        )
        TreeObservation.objects.bulk_create(
            TreeObservation(
                tree=tree,
                status=(
                    TreeObservation.Status.ALIVE
                    if observation.completed
                    else TreeObservation.Status.UNKNOWN
                ),
                source=observation.source,
                photo_url=observation.photo_url,
                observed_at=observation.observed_at,
            )
            for tree in trees
            for observation in observations.get((tree.source, tree.external_id), [])
        )
    return dataset


def create_datasets(imports: list[LegacyAreaImport]) -> list[Dataset]:
    with transaction.atomic():
        return [
            create_dataset(area_import.dataset_name, area_import.trees)
            for area_import in imports
        ]
