import csv

import pytest
from apps.datasets import instances, legacy
from apps.datasets.models import Tree
from apps.optimization.cost_matrix import OSRMCostMatrixBuilder
from requests_mock import ANY

SQUARE = [(-33.40, -70.60), (-33.40, -70.50), (-33.50, -70.50), (-33.50, -70.60)]
FAR_SQUARE = [(-33.30, -70.40), (-33.30, -70.30), (-33.40, -70.30), (-33.40, -70.40)]
DEGENERATE = [(-33.40, -70.60), (-33.40, -70.50)]

AREAS = [
    (26, "Area 1", "Campaña Semiponti", SQUARE),
    (39, "Area 1", "Prueba", FAR_SQUARE),
    (40, "Area 1", "Campaña Prueba Steps", SQUARE),
    (99, "Area vacía", "Campaña Semiponti", DEGENERATE),
]

API_TREES = [
    (776, -33.45, -70.55, "Quillaja saponaria"),
    (777, -33.46, -70.56, ""),
    (778, -33.35, -70.35, ""),
]

APP_TREES = [
    legacy.LegacyTreeRow(
        source=legacy.SOURCE_APP, external_id=96905, lat=-33.41, lon=-70.53
    ),
    legacy.LegacyTreeRow(
        source=legacy.SOURCE_APP, external_id=211488, lat=-33.42, lon=-70.52
    ),
]


@pytest.fixture
def legacy_db(monkeypatch):
    monkeypatch.setattr(legacy, "_load_api", lambda: (AREAS, API_TREES))
    monkeypatch.setattr(legacy, "_load_app_trees", lambda: list(APP_TREES))


@pytest.fixture
def instance_csv(tmp_path):
    path = tmp_path / "area-26-n2.csv"
    instances.write_instance(
        path,
        [
            instances.InstanceTree(
                source=legacy.SOURCE_API,
                external_id=776,
                lat=-33.45,
                lon=-70.55,
                species="Quillaja saponaria",
            ),
            instances.InstanceTree(
                source=legacy.SOURCE_API, external_id=777, lat=-33.46, lon=-70.56
            ),
        ],
    )
    return path


def test_dump_writes_declared_columns(legacy_db, tmp_path):
    instances.dump_legacy_instances(tmp_path)

    with (tmp_path / "reference-n5.csv").open() as handle:
        reader = csv.DictReader(handle)
        assert reader.fieldnames == instances.COLUMNS
        rows = list(reader)

    assert len(rows) == 5
    assert {row["source"] for row in rows} == {legacy.SOURCE_API, legacy.SOURCE_APP}


def test_dump_deduplicates_areas_repeated_across_campaigns(legacy_db, tmp_path):
    instances.dump_legacy_instances(tmp_path)

    names = sorted(path.name for path in tmp_path.glob("*.csv"))

    assert names == ["area-26-n2.csv", "area-39-n1.csv", "reference-n5.csv"]


def test_dump_keeps_lat_and_lon_in_their_own_columns(legacy_db, tmp_path):
    instances.dump_legacy_instances(tmp_path)

    rows = instances.read_instance(tmp_path / "area-39-n1.csv")

    assert rows == [
        instances.InstanceTree(
            source=legacy.SOURCE_API, external_id=778, lat=-33.35, lon=-70.35
        )
    ]


@pytest.mark.django_db
def test_load_is_idempotent_and_keeps_uuids(instance_csv):
    first = instances.load_instance(instance_csv)
    first_ids = sorted(str(tree.id) for tree in Tree.objects.filter(dataset=first))

    second = instances.load_instance(instance_csv)
    second_ids = sorted(str(tree.id) for tree in Tree.objects.filter(dataset=second))

    assert second.id == first.id == instances.dataset_uuid("area-26-n2")
    assert second_ids == first_ids
    assert Tree.objects.count() == 2
    assert second.total_trees == 2


@pytest.mark.django_db
def test_load_places_point_as_lon_lat(instance_csv):
    dataset = instances.load_instance(instance_csv)

    tree = Tree.objects.get(dataset=dataset, external_id=776)

    assert (tree.location.x, tree.location.y) == (-70.55, -33.45)


@pytest.mark.django_db
def test_load_scopes_uuids_per_instance(instance_csv, tmp_path):
    overlapping = tmp_path / "reference-n1.csv"
    instances.write_instance(
        overlapping,
        [
            instances.InstanceTree(
                source=legacy.SOURCE_API, external_id=776, lat=-33.45, lon=-70.55
            )
        ],
    )

    area = instances.load_instance(instance_csv)
    reference = instances.load_instance(overlapping)

    assert Tree.objects.filter(dataset=area, external_id=776).count() == 1
    assert Tree.objects.filter(dataset=reference, external_id=776).count() == 1
    assert Tree.objects.filter(external_id=776).values("id").distinct().count() == 2


@pytest.mark.django_db
def test_reloaded_instance_hits_the_matrix_cache(instance_csv, requests_mock):
    adapter = requests_mock.get(ANY, json={"durations": [[0, 30], [30, 0]]})
    builder = OSRMCostMatrixBuilder()

    dataset = instances.load_instance(instance_csv)
    builder.build(list(Tree.objects.filter(dataset=dataset)))

    reloaded = instances.load_instance(instance_csv)
    cached = builder.get_cached(list(Tree.objects.filter(dataset=reloaded)))

    assert adapter.call_count == 1
    assert cached is not None
