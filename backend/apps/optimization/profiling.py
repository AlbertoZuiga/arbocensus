import time
from contextlib import contextmanager

# Every group/subkey must be pre-populated so the persisted `timing` dict has
# the same key set on every run, regardless of which code path executed
# (cache hit vs miss, chunked vs single OSRM request, first solution found or not).
PHASE_SCHEMA = {
    "cost_matrix": [
        "total",
        "cache_lookup",
        "hash",
        "persist",
        "osrm_fetch",
        "chunk_assembly",
        "single_request",
        "chunked_diagonal",
        "chunked_offdiagonal",
    ],
    "model_build": [
        "total",
        "geo_matrix",
        "disjunctions",
        "vehicle_bounds",
        "search_params",
    ],
    "solve": ["total", "first_solution", "metaheuristic"],
    "solution_extraction": ["total"],
    "metrics": ["total"],
}


class PhaseTimer:
    def __init__(self, schema=None):
        schema = schema or PHASE_SCHEMA
        self._data = {group: dict.fromkeys(keys, 0.0) for group, keys in schema.items()}

    @contextmanager
    def phase(self, group, name="total"):
        start = time.perf_counter()
        try:
            yield
        finally:
            self.record(group, time.perf_counter() - start, name)

    def record(self, group, elapsed, name="total"):
        bucket = self._data.setdefault(group, {})
        bucket[name] = bucket.get(name, 0.0) + elapsed

    def as_dict(self):
        return {group: dict(values) for group, values in self._data.items()}


def merge_timing(*timings):
    merged = {}
    for timing in timings:
        for group, values in timing.items():
            bucket = merged.setdefault(group, {})
            for name, elapsed in values.items():
                bucket[name] = bucket.get(name, 0.0) + elapsed
    merged["pipeline_total"] = sum(
        values.get("total", 0.0) for values in merged.values()
    )
    return merged
