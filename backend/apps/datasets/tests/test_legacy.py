import pytest
from apps.datasets import legacy
from apps.datasets.models import Dataset, Tree
from rest_framework.test import APIClient
from tests.factories import CustomUserFactory

SQUARE = [(-33.40, -70.60), (-33.40, -70.50), (-33.50, -70.50), (-33.50, -70.60)]
FAR_SQUARE = [(-34.40, -71.60), (-34.40, -71.50), (-34.50, -71.50), (-34.50, -71.60)]

AREAS = [
    (26, "Area 1", "Campaña Semiponti", SQUARE),
    (48, "Area 1", "Campaña Defensa 2024", FAR_SQUARE),
    (99, "Area vacía", "Campaña Semiponti", [(-33.40, -70.60), (-33.40, -70.50)]),
]

TREES = [
    (776, -33.45, -70.55, "Quillaja saponaria"),
    (777, -33.46, -70.56, ""),
    (778, -34.45, -71.55, "Peumus boldus"),
    (779, -10.0, -60.0, ""),
]


@pytest.fixture
def legacy_db(monkeypatch, settings):
    settings.LEGACY_DB_URL = "postgres://legacy/test"
    monkeypatch.setattr(legacy, "_load", lambda: (AREAS, TREES))


def _client(role):
    client = APIClient()
    client.force_authenticate(user=CustomUserFactory(role=role))
    return client


def test_list_areas_counts_trees_inside_polygon(legacy_db):
    areas = legacy.list_areas()
    assert areas == [
        {"id": 26, "name": "Area 1", "campaign": "Campaña Semiponti", "tree_count": 2},
        {
            "id": 48,
            "name": "Area 1",
            "campaign": "Campaña Defensa 2024",
            "tree_count": 1,
        },
        {
            "id": 99,
            "name": "Area vacía",
            "campaign": "Campaña Semiponti",
            "tree_count": 0,
        },
    ]


def test_import_area_returns_rows_with_species_and_external_id(legacy_db):
    area_import = legacy.import_area(26)
    assert area_import.dataset_name == "Campaña Semiponti — Area 1"
    assert [
        (row.external_id, row.lat, row.lon, row.species) for row in area_import.trees
    ] == [
        (776, -33.45, -70.55, "Quillaja saponaria"),
        (777, -33.46, -70.56, ""),
    ]


def test_import_area_unknown_id_raises(legacy_db):
    with pytest.raises(ValueError, match="123"):
        legacy.import_area(123)


def test_import_area_without_trees_raises(legacy_db):
    with pytest.raises(ValueError, match="no trees"):
        legacy.import_area(99)


def test_import_all_skips_areas_without_trees(legacy_db):
    imports = legacy.import_all()
    assert [ai.dataset_name for ai in imports] == [
        "Campaña Semiponti — Area 1",
        "Campaña Defensa 2024 — Area 1",
    ]


def test_load_without_url_raises_not_configured(settings):
    settings.LEGACY_DB_URL = ""
    with pytest.raises(legacy.LegacyDatabaseNotConfiguredError):
        legacy.list_areas()


@pytest.mark.django_db
def test_create_datasets_persists_trees_with_point_lon_lat(legacy_db):
    datasets = legacy.create_datasets([legacy.import_area(26)])
    assert len(datasets) == 1
    dataset = Dataset.objects.get(id=datasets[0].id)
    assert dataset.name == "Campaña Semiponti — Area 1"
    assert dataset.total_trees == 2
    tree = Tree.objects.get(dataset=dataset, external_id=776)
    assert tree.location.x == -70.55
    assert tree.location.y == -33.45
    assert tree.species == "Quillaja saponaria"


@pytest.mark.django_db
def test_legacy_areas_endpoint_returns_counts(legacy_db):
    response = _client("admin").get("/api/datasets/legacy/areas/")
    assert response.status_code == 200
    assert response.data[0] == {
        "id": 26,
        "name": "Area 1",
        "campaign": "Campaña Semiponti",
        "tree_count": 2,
    }


@pytest.mark.django_db
def test_legacy_areas_endpoint_forbidden_for_surveyor(legacy_db):
    response = _client("surveyor").get("/api/datasets/legacy/areas/")
    assert response.status_code == 403


@pytest.mark.django_db
def test_legacy_areas_returns_503_when_not_configured(settings):
    settings.LEGACY_DB_URL = ""
    response = _client("admin").get("/api/datasets/legacy/areas/")
    assert response.status_code == 503
    assert "LEGACY_DB_URL" in response.data["detail"]


@pytest.mark.django_db
def test_import_legacy_single_area_creates_dataset(legacy_db):
    response = _client("admin").post(
        "/api/datasets/import-legacy/", {"area_id": 26}, format="json"
    )
    assert response.status_code == 201
    assert len(response.data) == 1
    assert response.data[0]["name"] == "Campaña Semiponti — Area 1"
    assert response.data[0]["total_trees"] == 2
    assert Tree.objects.filter(dataset_id=response.data[0]["id"]).count() == 2


@pytest.mark.django_db
def test_import_legacy_all_creates_dataset_per_area(legacy_db):
    response = _client("admin").post(
        "/api/datasets/import-legacy/", {"area_id": "all"}, format="json"
    )
    assert response.status_code == 201
    assert Dataset.objects.count() == 2
    assert Tree.objects.count() == 3


@pytest.mark.django_db
def test_import_legacy_unknown_area_returns_400(legacy_db):
    response = _client("admin").post(
        "/api/datasets/import-legacy/", {"area_id": 123}, format="json"
    )
    assert response.status_code == 400
    assert not Dataset.objects.exists()


@pytest.mark.django_db
def test_import_legacy_empty_area_returns_400(legacy_db):
    response = _client("admin").post(
        "/api/datasets/import-legacy/", {"area_id": 99}, format="json"
    )
    assert response.status_code == 400
    assert not Dataset.objects.exists()


@pytest.mark.django_db
def test_import_legacy_without_area_id_returns_400(legacy_db):
    response = _client("admin").post("/api/datasets/import-legacy/", {}, format="json")
    assert response.status_code == 400


@pytest.mark.django_db
def test_import_legacy_returns_503_when_not_configured(settings):
    settings.LEGACY_DB_URL = ""
    response = _client("admin").post(
        "/api/datasets/import-legacy/", {"area_id": 26}, format="json"
    )
    assert response.status_code == 503
