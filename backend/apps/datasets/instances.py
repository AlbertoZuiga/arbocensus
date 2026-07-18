import csv
import math
import uuid
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

from django.conf import settings
from django.contrib.gis.geos import Point
from django.db import transaction

from . import legacy
from .models import Dataset, Tree

INSTANCE_NAMESPACE = uuid.UUID("9c6bdc3b-7462-40b6-b891-43dfbc54c43b")
COLUMNS = ["source", "external_id", "lat", "lon", "species"]

# Centroid of the 12,946 georeferenced trees (median lat/lon per QR). Frozen as a
# constant so the growth ordering stays fixed even if the legacy database shifts.
BATTERY_SEED = (-33.41947947204772, -70.56545962517218)
BATTERY_SIZES = (50, 100, 200, 400, 800, 1000)
BATTERY_SPARSE_STEPS = {"battery-sparse-n500": 2, "battery-sparse-n250": 4}


@dataclass(frozen=True)
class InstanceTree:
    source: str
    external_id: int
    lat: float
    lon: float
    species: str = ""


def instances_dir() -> Path:
    return Path(settings.EXPERIMENTS_DIR) / "instances"


def dataset_uuid(slug: str) -> uuid.UUID:
    return uuid.uuid5(INSTANCE_NAMESPACE, f"instance:{slug}")


def tree_uuid(slug: str, source: str, external_id: int) -> uuid.UUID:
    # Scoped to the instance because legacy areas overlap and the reference repeats
    # their trees: a UUID keyed only on (source, external_id) would collide across
    # datasets loaded into the same database.
    return uuid.uuid5(dataset_uuid(slug), f"{source}:{external_id}")


def write_instance(
    path: Path, rows: Iterable[InstanceTree], *, sort: bool = True
) -> int:
    ordered = (
        sorted(rows, key=lambda row: (row.source, row.external_id))
        if sort
        else list(rows)
    )
    with path.open("w", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(COLUMNS)
        for row in ordered:
            writer.writerow(
                [row.source, row.external_id, row.lat, row.lon, row.species]
            )
    return len(ordered)


def read_instance(path: Path) -> list[InstanceTree]:
    with path.open(newline="") as handle:
        return [
            InstanceTree(
                source=row["source"],
                external_id=int(row["external_id"]),
                lat=float(row["lat"]),
                lon=float(row["lon"]),
                species=row["species"],
            )
            for row in csv.DictReader(handle)
        ]


def load_instance(path: Path) -> Dataset:
    slug = path.stem
    rows = read_instance(path)
    with transaction.atomic():
        dataset, _ = Dataset.objects.update_or_create(
            id=dataset_uuid(slug),
            defaults={"name": slug, "total_trees": len(rows)},
        )
        Tree.objects.bulk_create(
            [
                Tree(
                    id=tree_uuid(slug, row.source, row.external_id),
                    dataset=dataset,
                    location=Point(row.lon, row.lat),
                    species=row.species,
                    source=row.source,
                    external_id=row.external_id,
                )
                for row in rows
            ],
            ignore_conflicts=True,
        )
    return dataset


def _instance_rows(rows: list[legacy.LegacyTreeRow]) -> list[InstanceTree]:
    return [
        InstanceTree(
            source=row.source,
            external_id=row.external_id,
            lat=float(row.lat),
            lon=float(row.lon),
            species=row.species,
        )
        for row in rows
    ]


def dump_legacy_instances(output_dir: Path) -> list[tuple[Path, int]]:
    output_dir.mkdir(parents=True, exist_ok=True)
    written = []
    for area in legacy.list_distinct_areas():
        rows = _instance_rows(area.trees)
        path = output_dir / f"area-{area.area_id}-n{len(rows)}.csv"
        written.append((path, write_instance(path, rows)))

    reference = _instance_rows(legacy.all_tree_rows())
    path = output_dir / f"reference-n{len(reference)}.csv"
    written.append((path, write_instance(path, reference)))
    return written


def _haversine(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = (
        math.sin(dphi / 2) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    )
    return 2 * 6371000 * math.asin(math.sqrt(a))


def _sort_by_seed(rows: list[InstanceTree]) -> list[InstanceTree]:
    seed_lat, seed_lon = BATTERY_SEED
    return sorted(
        rows,
        key=lambda row: (
            _haversine(seed_lat, seed_lon, row.lat, row.lon),
            row.external_id,
        ),
    )


def build_battery(rows: list[InstanceTree]) -> list[tuple[str, list[InstanceTree]]]:
    ordered = _sort_by_seed(rows)
    battery = [(f"battery-n{n}", ordered[:n]) for n in BATTERY_SIZES]
    largest = ordered[: max(BATTERY_SIZES)]
    battery += [(slug, largest[::step]) for slug, step in BATTERY_SPARSE_STEPS.items()]
    return battery


def dump_battery_instances(output_dir: Path) -> list[tuple[Path, int]]:
    output_dir.mkdir(parents=True, exist_ok=True)
    written = []
    for slug, rows in build_battery(_instance_rows(legacy.battery_tree_rows())):
        path = output_dir / f"{slug}.csv"
        written.append((path, write_instance(path, rows, sort=False)))
    return written
