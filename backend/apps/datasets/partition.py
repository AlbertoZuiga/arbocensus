from apps.optimization.strategies import kmeans, project_equirectangular

from .legacy import LegacyAreaImport, LegacyTreeRow

# A dataset smaller than one shift cannot produce a usable route: one shift is
# DEFAULT_MAX_ROUTE_TIME_SEC (10800) over the per-tree work, DEFAULT_SERVICE_TIME_SEC
# (180) plus ~90 s of walk to the next tree. k-means does not balance its clusters, so
# this bounds the AVERAGE dataset, not the smallest one — past that bound every split
# is starved by construction.
MIN_TREES_PER_DATASET = 40


def by_kmeans(name: str, rows: list[LegacyTreeRow], k: int) -> list[LegacyAreaImport]:
    max_k = len(rows) // MIN_TREES_PER_DATASET
    if not 2 <= k <= max_k:
        raise ValueError(
            f"{len(rows)} trees allow at most {max_k} datasets averaging "
            f"{MIN_TREES_PER_DATASET} trees; k must be between 2 and {max_k}"
        )
    coords = project_equirectangular([(row.lat, row.lon) for row in rows])
    labels = kmeans(coords, k)
    groups: dict[int, list[LegacyTreeRow]] = {}
    for label, row in zip(labels, rows, strict=True):
        groups.setdefault(int(label), []).append(row)
    return [
        LegacyAreaImport(dataset_name=f"{name} — {index}", trees=groups[label])
        for index, label in enumerate(sorted(groups), start=1)
    ]
