import hashlib

import numpy as np
import requests
from apps.datasets.models import DistanceMatrix
from django.conf import settings

UNREACHABLE_PENALTY = 9_999_999.0
# Cap from GET URL length (~8KB), not OSRM's --max-table-size (5000): the table
# request encodes every coordinate in the URL, so it fails on URL length first.
OSRM_MAX_TREES_PER_REQUEST = 350


class OSRMCostMatrixBuilder:
    def build(self, trees):
        trees = sorted(trees, key=lambda tree: tree.id)
        dataset = trees[0].dataset

        cached = self.get_cached(trees)
        if cached is not None:
            return cached

        matrix = self._fetch_from_osrm(trees)
        source_hash = self._compute_hash(trees)
        DistanceMatrix.objects.update_or_create(
            dataset=dataset,
            defaults={
                "source_hash": source_hash,
                "matrix_data": matrix.tolist(),
                "dimension": matrix.shape[0],
            },
        )
        return matrix

    def get_cached(self, trees):
        trees = sorted(trees, key=lambda tree: tree.id)
        dataset = trees[0].dataset
        source_hash = self._compute_hash(trees)

        cached = DistanceMatrix.objects.filter(dataset=dataset).first()
        if cached is not None and cached.source_hash == source_hash:
            return np.array(cached.matrix_data, dtype=float)
        return None

    def _compute_hash(self, trees):
        ordered_ids = sorted(str(tree.id) for tree in trees)
        return hashlib.sha256(",".join(ordered_ids).encode()).hexdigest()

    def _fetch_from_osrm(self, trees):
        if len(trees) > OSRM_MAX_TREES_PER_REQUEST:
            raise ValueError(
                f"dataset excede el máximo de árboles por consulta OSRM "
                f"({OSRM_MAX_TREES_PER_REQUEST} árboles); dividir dataset"
            )
        coords = ";".join(f"{tree.location.x},{tree.location.y}" for tree in trees)
        url = f"{settings.OSRM_URL}/table/v1/foot/{coords}"
        response = requests.get(url, params={"annotations": "duration"}, timeout=60)
        response.raise_for_status()

        durations = np.array(response.json()["durations"], dtype=float)
        return np.nan_to_num(durations, nan=UNREACHABLE_PENALTY)
