import hashlib
import time

import numpy as np
import requests
from apps.datasets.models import DistanceMatrix
from apps.optimization.profiling import PhaseTimer
from django.conf import settings

try:
    from line_profiler import profile  # type: ignore[import-untyped]
except ImportError:

    def profile(f):  # type: ignore[misc]
        return f


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
    @profile
    def build(self, trees, timer=None):
        timer = timer or PhaseTimer()
        trees = sorted(trees, key=lambda tree: tree.id)
        dataset = trees[0].dataset

        with timer.phase("cost_matrix", "hash"):
            source_hash = self._compute_hash(trees)

        with timer.phase("cost_matrix", "cache_lookup"):
            cached = self._lookup_cache(dataset, source_hash)
        if cached is not None:
            return cached

        fetch_start = time.perf_counter()
        matrix = self._fetch_from_osrm(trees, timer)
        fetch_elapsed = time.perf_counter() - fetch_start
        osrm_fetch_elapsed = timer.as_dict()["cost_matrix"]["osrm_fetch"]
        timer.record(
            "cost_matrix",
            max(0.0, fetch_elapsed - osrm_fetch_elapsed),
            "chunk_assembly",
        )

        with timer.phase("cost_matrix", "persist"):
            DistanceMatrix.objects.update_or_create(
                dataset=dataset,
                defaults={
                    "source_hash": source_hash,
                    "matrix_data": matrix.tolist(),
                    "dimension": matrix.shape[0],
                },
            )
        return matrix

    @profile
    def get_cached(self, trees):
        trees = sorted(trees, key=lambda tree: tree.id)
        dataset = trees[0].dataset
        source_hash = self._compute_hash(trees)
        return self._lookup_cache(dataset, source_hash)

    @profile
    def _lookup_cache(self, dataset, source_hash):
        cached = DistanceMatrix.objects.filter(dataset=dataset).first()
        if cached is not None and cached.source_hash == source_hash:
            return np.array(cached.matrix_data, dtype=float)
        return None

    @profile
    def _compute_hash(self, trees):
        ordered_ids = sorted(str(tree.id) for tree in trees)
        return hashlib.sha256(",".join(ordered_ids).encode()).hexdigest()

    @profile
    def _fetch_from_osrm(self, trees, timer=None):
        timer = timer or PhaseTimer()
        if len(trees) > OSRM_MAX_MATRIX_DIMENSION:
            raise ValueError(
                f"dataset excede la dimensión máxima de matriz OSRM "
                f"({OSRM_MAX_MATRIX_DIMENSION} árboles); dividir dataset"
            )
        coords = [(tree.location.x, tree.location.y) for tree in trees]
        if len(coords) <= OSRM_MAX_TREES_PER_REQUEST:
            with timer.phase("cost_matrix", "single_request"):
                durations = self._request_table(coords, timer=timer)
        else:
            durations = self._fetch_chunked(coords, timer=timer)
        return np.nan_to_num(durations, nan=UNREACHABLE_PENALTY)

    @profile
    def _fetch_chunked(self, coords, chunk_size=OSRM_CHUNK_SIZE, timer=None):
        timer = timer or PhaseTimer()
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
                    with timer.phase("cost_matrix", "chunked_diagonal"):
                        block = self._request_table(
                            [coords[i] for i in src_block], timer=timer
                        )
                else:
                    subset = list(dict.fromkeys(src_block + dst_block))
                    position = {original: k for k, original in enumerate(subset)}
                    with timer.phase("cost_matrix", "chunked_offdiagonal"):
                        block = self._request_table(
                            [coords[i] for i in subset],
                            sources=[position[i] for i in src_block],
                            destinations=[position[i] for i in dst_block],
                            timer=timer,
                        )
                matrix[np.ix_(src_block, dst_block)] = block
        return matrix

    @profile
    def _request_table(self, coords, sources=None, destinations=None, timer=None):
        timer = timer or PhaseTimer()
        coord_str = ";".join(f"{lon},{lat}" for lon, lat in coords)
        params = {"annotations": "duration"}
        if sources is not None and destinations is not None:
            params["sources"] = ";".join(str(i) for i in sources)
            params["destinations"] = ";".join(str(i) for i in destinations)
        url = f"{settings.OSRM_URL}/table/v1/foot/{coord_str}"
        with timer.phase("cost_matrix", "osrm_fetch"):
            response = requests.get(url, params=params, timeout=60)
            response.raise_for_status()
            durations = response.json()["durations"]
        return np.array(durations, dtype=float)
