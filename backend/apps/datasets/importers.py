import csv
import io
import json
from abc import ABC, abstractmethod
from collections.abc import Iterator

from django.contrib.gis.geos import Point

from .models import Dataset, Tree

_LAT_NAMES = {"lat", "latitude", "latitud"}
_LON_NAMES = {"lon", "lng", "longitude", "longitud"}

_IMPORTERS: dict[str, type["BaseImporter"]] = {}

_BATCH_SIZE = 500


def _detect_key(keys: list[str], candidates: set[str]) -> str | None:
    for key in keys:
        if key.strip().lower() in candidates:
            return key
    return None


class BaseImporter(ABC):
    def __init_subclass__(cls, ext: str, **kwargs):
        super().__init_subclass__(**kwargs)
        _IMPORTERS[ext] = cls

    @abstractmethod
    def _parse(self, file) -> Iterator[tuple[float, float] | None]:
        """Yields (lat, lon) pairs, or None for rows with missing/null coordinates."""

    def import_into(self, file, dataset: Dataset) -> tuple[int, int]:
        total = 0
        skipped = 0
        batch: list[Tree] = []

        for coords in self._parse(file):
            if coords is None:
                skipped += 1
                continue
            lat, lon = coords
            batch.append(Tree(dataset=dataset, location=Point(lon, lat)))
            if len(batch) == _BATCH_SIZE:
                Tree.objects.bulk_create(batch)
                total += len(batch)
                batch.clear()

        if batch:
            Tree.objects.bulk_create(batch)
            total += len(batch)

        dataset.total_trees = total
        dataset.save(update_fields=["total_trees"])
        return total, skipped


class CsvImporter(BaseImporter, ext="csv"):
    def _parse(self, file) -> Iterator[tuple[float, float] | None]:
        content = file.read()
        if isinstance(content, bytes):
            content = content.decode("utf-8-sig")
        try:
            dialect = csv.Sniffer().sniff(content[:4096], delimiters=",;\t|")
        except csv.Error:
            dialect = csv.excel
        reader = csv.DictReader(io.StringIO(content), dialect=dialect)
        columns = list(reader.fieldnames or [])

        lat_col = _detect_key(columns, _LAT_NAMES)
        lon_col = _detect_key(columns, _LON_NAMES)

        if not lat_col:
            raise ValueError(f"No lat column found. Got: {columns}")
        if not lon_col:
            raise ValueError(f"No lon column found. Got: {columns}")

        for row in reader:
            lat, lon = row.get(lat_col), row.get(lon_col)
            if lat and lon:
                yield float(lat.replace(",", ".")), float(lon.replace(",", "."))
            else:
                yield None


class JsonImporter(BaseImporter, ext="json"):
    def _parse(self, file) -> Iterator[tuple[float, float] | None]:
        data = json.load(file)

        if not isinstance(data, dict) or not isinstance(data.get("trees"), list):
            raise ValueError("JSON must have a top-level 'trees' array")

        entries: list[dict] = data["trees"]
        if not entries:
            return

        first_keys = list(entries[0].keys())
        lat_key = _detect_key(first_keys, _LAT_NAMES)
        lon_key = _detect_key(first_keys, _LON_NAMES)

        if not lat_key:
            raise ValueError(f"No lat key found. Got: {first_keys}")
        if not lon_key:
            raise ValueError(f"No lon key found. Got: {first_keys}")

        for entry in entries:
            lat, lon = entry.get(lat_key), entry.get(lon_key)
            if lat is not None and lon is not None:
                yield float(lat), float(lon)
            else:
                yield None


def import_file(file, dataset: Dataset, filename: str) -> tuple[int, int]:
    ext = filename.rsplit(".", 1)[-1].lower()
    importer_cls = _IMPORTERS.get(ext)
    if not importer_cls:
        raise ValueError(f"Unsupported format: .{ext}. Supported: {sorted(_IMPORTERS)}")
    return importer_cls().import_into(file, dataset)
