import csv
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


def write_instance(path: Path, rows: Iterable[InstanceTree]) -> int:
    ordered = sorted(rows, key=lambda row: (row.source, row.external_id))
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
