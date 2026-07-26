import pytest
from apps.datasets import legacy, partition
from apps.datasets.models import Dataset, Tree
from rest_framework.test import APIClient
from tests.factories import CustomUserFactory

from .test_legacy import API_TREES, legacy_db  # noqa: F401


def _row(external_id, lat, lon):
    return legacy.LegacyTreeRow(
        source=legacy.SOURCE_API, external_id=external_id, lat=lat, lon=lon
    )


def _cloud(first_id, lon):
    return [
        _row(first_id + i, -33.45 + i * 0.0001, lon + i * 0.0001) for i in range(60)
    ]


WEST = _cloud(1, -70.70)
EAST = _cloud(1000, -70.20)


def test_kmeans_splits_two_distant_clouds():
    partitions = partition.by_kmeans("Selección", WEST + EAST, 2)

    assert [p.dataset_name for p in partitions] == ["Selección — 1", "Selección — 2"]
    grouped = {frozenset(row.external_id for row in p.trees) for p in partitions}
    assert grouped == {
        frozenset(row.external_id for row in WEST),
        frozenset(row.external_id for row in EAST),
    }


def test_kmeans_keeps_every_tree_exactly_once():
    rows = WEST + EAST
    partitions = partition.by_kmeans("Selección", rows, 3)

    assigned = [row.external_id for p in partitions for row in p.trees]
    assert sorted(assigned) == sorted(row.external_id for row in rows)


def test_kmeans_preserves_source_and_external_id():
    partitions = partition.by_kmeans("Selección", WEST + EAST, 2)

    assert all(
        row.source == legacy.SOURCE_API and row.external_id
        for p in partitions
        for row in p.trees
    )


@pytest.mark.parametrize("k", [1, 4])
def test_kmeans_rejects_a_k_that_starves_the_datasets(k):
    with pytest.raises(ValueError, match="between 2 and 3"):
        partition.by_kmeans("Selección", WEST + EAST, k)


def test_kmeans_rejects_a_selection_too_small_to_split():
    rows = WEST[: partition.MIN_TREES_PER_DATASET]

    with pytest.raises(ValueError, match="at most 1 datasets"):
        partition.by_kmeans("Selección", rows, 2)


@pytest.fixture
def small_datasets_allowed(monkeypatch):
    monkeypatch.setattr(partition, "MIN_TREES_PER_DATASET", 2)


def _admin_client():
    client = APIClient()
    client.force_authenticate(user=CustomUserFactory(role="admin"))
    return client


def _payload(**extra):
    return {
        "name": "Selección",
        "trees": [
            {"source": legacy.SOURCE_API, "external_id": external_id}
            for external_id, *_ in API_TREES
        ],
        **extra,
    }


@pytest.mark.django_db
def test_partition_endpoint_creates_one_dataset_per_cluster(
    legacy_db,  # noqa: F811
    small_datasets_allowed,
):
    response = _admin_client().post(
        "/api/datasets/partition-legacy-selection/", _payload(k=2), format="json"
    )

    assert response.status_code == 201
    assert len(response.data) == 2
    assert Dataset.objects.count() == 2
    assert sum(dataset["total_trees"] for dataset in response.data) == len(API_TREES)


@pytest.mark.django_db
def test_partition_endpoint_keeps_the_natural_key_of_every_tree(
    legacy_db,  # noqa: F811
    small_datasets_allowed,
):
    _admin_client().post(
        "/api/datasets/partition-legacy-selection/", _payload(k=2), format="json"
    )

    keys = set(Tree.objects.values_list("source", "external_id"))
    assert keys == {(legacy.SOURCE_API, external_id) for external_id, *_ in API_TREES}


@pytest.mark.django_db
def test_partition_endpoint_requires_k(legacy_db):  # noqa: F811
    response = _admin_client().post(
        "/api/datasets/partition-legacy-selection/", _payload(), format="json"
    )

    assert response.status_code == 400
    assert not Dataset.objects.exists()


@pytest.mark.django_db
def test_partition_endpoint_rejects_a_k_that_starves_the_datasets(
    legacy_db,  # noqa: F811
):
    response = _admin_client().post(
        "/api/datasets/partition-legacy-selection/", _payload(k=2), format="json"
    )

    assert response.status_code == 400
    assert "k" in response.data
    assert not Dataset.objects.exists()


@pytest.mark.django_db
def test_partition_endpoint_forbidden_for_surveyor(
    legacy_db,  # noqa: F811
    small_datasets_allowed,
):
    client = APIClient()
    client.force_authenticate(user=CustomUserFactory(role="surveyor"))

    response = client.post(
        "/api/datasets/partition-legacy-selection/", _payload(k=2), format="json"
    )

    assert response.status_code == 403
