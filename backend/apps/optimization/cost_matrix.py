import hashlib

import numpy as np
import requests
from apps.datasets.models import DistanceMatrix
from django.conf import settings

UNREACHABLE_PENALTY = 9_999_999.0
# Cap from GET URL length (~8KB), not OSRM's --max-table-size (5000): the table
# request encodes every coordinate in the URL, so it fails on URL length first.
OSRM_MAX_TREES_PER_REQUEST = 350
# Each chunked request carries source-block + destination-block coordinates,
# so half the single-request cap keeps every URL within the same length budget.
OSRM_CHUNK_SIZE = OSRM_MAX_TREES_PER_REQUEST // 2
# matrix_data JSON grows O(n²): 2000² floats ≈ 32MB per DistanceMatrix row.
OSRM_MAX_MATRIX_DIMENSION = 2000


class OSRMCostMatrixBuilder:
    def build(self, trees):
        trees = sorted(trees, key=lambda tree: tree.id)
        dataset = trees[0].dataset
        source_hash = self._compute_hash(trees)

        cached = self._lookup_cache(dataset, source_hash)
        if cached is not None:
            return cached

        matrix = self._fetch_from_osrm(trees)
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
        return self._lookup_cache(dataset, source_hash)

    def _lookup_cache(self, dataset, source_hash):
        cached = DistanceMatrix.objects.filter(dataset=dataset).first()
        if cached is not None and cached.source_hash == source_hash:
            return np.array(cached.matrix_data, dtype=float)
        return None

    def _compute_hash(self, trees):
        ordered_ids = sorted(str(tree.id) for tree in trees)
        return hashlib.sha256(",".join(ordered_ids).encode()).hexdigest()

    def _fetch_from_osrm(self, trees):
        if len(trees) > OSRM_MAX_MATRIX_DIMENSION:
            raise ValueError(
                f"dataset excede la dimensión máxima de matriz OSRM "
                f"({OSRM_MAX_MATRIX_DIMENSION} árboles); dividir dataset"
            )
        coords = [(tree.location.x, tree.location.y) for tree in trees]
        if len(coords) <= OSRM_MAX_TREES_PER_REQUEST:
            durations = self._request_table(coords)
        else:
            durations = self._fetch_chunked(coords)
        return np.nan_to_num(durations, nan=UNREACHABLE_PENALTY)

    def _fetch_chunked(self, coords, chunk_size=OSRM_CHUNK_SIZE):
        n = len(coords)
        matrix = np.empty((n, n), dtype=float)
        blocks = [
            list(range(start, min(start + chunk_size, n)))
            for start in range(0, n, chunk_size)
        ]
        for src_block in blocks:
            for dst_block in blocks:
                if src_block is dst_block:
                    # Diagonal block: subset == src_block == dst_block, so an
                    # explicit sources/destinations filter is a same-size no-op
                    # that only inflates the URL. Omit it.
                    block = self._request_table([coords[i] for i in src_block])
                else:
                    subset = list(dict.fromkeys(src_block + dst_block))
                    position = {original: k for k, original in enumerate(subset)}
                    block = self._request_table(
                        [coords[i] for i in subset],
                        sources=[position[i] for i in src_block],
                        destinations=[position[i] for i in dst_block],
                    )
                matrix[np.ix_(src_block, dst_block)] = block
        return matrix

    def _request_table(self, coords, sources=None, destinations=None):
        coord_str = ";".join(f"{lon},{lat}" for lon, lat in coords)
        params = {"annotations": "duration"}
        if sources is not None and destinations is not None:
            params["sources"] = ";".join(str(i) for i in sources)
            params["destinations"] = ";".join(str(i) for i in destinations)
        url = f"{settings.OSRM_URL}/table/v1/foot/{coord_str}"
        response = requests.get(url, params=params, timeout=60)
        response.raise_for_status()
        return np.array(response.json()["durations"], dtype=float)
