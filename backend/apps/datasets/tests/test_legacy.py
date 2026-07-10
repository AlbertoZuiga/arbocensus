import pytest
from apps.datasets import legacy
from apps.datasets.models import Dataset, Tree
from rest_framework.test import APIClient
from tests.factories import CustomUserFactory

SQUARE = [(-33.40, -70.60), (-33.40, -70.50), (-33.50, -70.50), (-33.50, -70.60)]
FAR_SQUARE = [(-34.40, -71.60), (-34.40, -71.50), (-34.50, -71.50), (-34.50, -71.60)]


def _geojson_polygon(coordinates):
    ring = [[lon, lat] for lat, lon in coordinates]
    ring.append(ring[0])
    return {"type": "Polygon", "coordinates": [ring]}


AREAS = [
    (26, "Area 1", "Campaña Semiponti", SQUARE),
    (48, "Area 1", "Campaña Defensa 2024", FAR_SQUARE),
    (99, "Area vacía", "Campaña Semiponti", [(-33.40, -70.60), (-33.40, -70.50)]),
]

API_TREES = [
    (776, -33.45, -70.55, "Quillaja saponaria"),
    (777, -33.46, -70.56, ""),
    (778, -34.45, -71.55, "Peumus boldus"),
    (779, -10.0, -60.0, ""),
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
def legacy_db(monkeypatch, settings):
    settings.LEGACY_API_DB_URL = "postgres://legacy-api/test"
    settings.LEGACY_APP_DB_URL = "postgres://legacy-app/test"
    monkeypatch.setattr(legacy, "_load_api", lambda: (AREAS, API_TREES))
    monkeypatch.setattr(legacy, "_load_app_trees", lambda: list(APP_TREES))


def _client(role):
    client = APIClient()
    client.force_authenticate(user=CustomUserFactory(role=role))
    return client


def test_list_areas_counts_trees_inside_polygon(legacy_db):
    areas = legacy.list_areas()
    assert areas == [
        {
            "id": 26,
            "name": "Area 1",
            "campaign": "Campaña Semiponti",
            "tree_count": 2,
            "polygon": _geojson_polygon(SQUARE),
        },
        {
            "id": 48,
            "name": "Area 1",
            "campaign": "Campaña Defensa 2024",
            "tree_count": 1,
            "polygon": _geojson_polygon(FAR_SQUARE),
        },
        {
            "id": 99,
            "name": "Area vacía",
            "campaign": "Campaña Semiponti",
            "tree_count": 0,
            "polygon": None,
        },
    ]


def test_import_area_returns_rows_with_species_and_external_id(legacy_db):
    area_import = legacy.import_area(26)
    assert area_import.dataset_name == "Campaña Semiponti — Area 1"
    assert [
        (row.source, row.external_id, row.lat, row.lon, row.species)
        for row in area_import.trees
    ] == [
        (legacy.SOURCE_API, 776, -33.45, -70.55, "Quillaja saponaria"),
        (legacy.SOURCE_API, 777, -33.46, -70.56, ""),
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


def test_load_without_api_url_raises_not_configured(settings):
    settings.LEGACY_API_DB_URL = ""
    with pytest.raises(legacy.LegacyDatabaseNotConfiguredError):
        legacy.list_areas()


@pytest.mark.django_db
def test_list_trees_combines_both_sources(legacy_db):
    trees = legacy.list_trees()
    assert [(t["source"], t["external_id"]) for t in trees] == [
        (legacy.SOURCE_API, 776),
        (legacy.SOURCE_API, 777),
        (legacy.SOURCE_API, 778),
        (legacy.SOURCE_API, 779),
        (legacy.SOURCE_APP, 96905),
        (legacy.SOURCE_APP, 211488),
    ]
    assert all(t["already_imported"] is False for t in trees)


@pytest.mark.django_db
def test_list_trees_assigns_area_id_by_polygon_containment(legacy_db):
    trees = legacy.list_trees()
    by_key = {(t["source"], t["external_id"]): t["area_id"] for t in trees}
    assert by_key[(legacy.SOURCE_API, 776)] == 26
    assert by_key[(legacy.SOURCE_API, 777)] == 26
    assert by_key[(legacy.SOURCE_API, 778)] == 48
    assert by_key[(legacy.SOURCE_API, 779)] is None
    assert by_key[(legacy.SOURCE_APP, 96905)] is None
    assert by_key[(legacy.SOURCE_APP, 211488)] is None


@pytest.mark.django_db
def test_list_trees_flags_already_imported(legacy_db):
    legacy.create_dataset("Existing", [APP_TREES[0]])
    trees = legacy.list_trees()
    flagged = {(t["source"], t["external_id"]) for t in trees if t["already_imported"]}
    assert flagged == {(legacy.SOURCE_APP, 96905)}


@pytest.mark.django_db
def test_list_trees_works_with_single_source_configured(
    legacy_db, monkeypatch, settings
):
    settings.LEGACY_APP_DB_URL = ""

    def app_not_configured():
        raise legacy.LegacyDatabaseNotConfiguredError("ARBOCENSUS_DB_URL missing")

    monkeypatch.setattr(legacy, "_load_app_trees", app_not_configured)
    trees = legacy.list_trees()
    assert {t["source"] for t in trees} == {legacy.SOURCE_API}


def test_list_trees_without_any_url_raises_not_configured(settings):
    settings.LEGACY_API_DB_URL = ""
    settings.LEGACY_APP_DB_URL = ""
    with pytest.raises(legacy.LegacyDatabaseNotConfiguredError):
        legacy.list_trees()


def test_load_selection_returns_rows_across_sources(legacy_db):
    rows = legacy.load_selection([(legacy.SOURCE_APP, 96905), (legacy.SOURCE_API, 776)])
    assert [(row.source, row.external_id) for row in rows] == [
        (legacy.SOURCE_APP, 96905),
        (legacy.SOURCE_API, 776),
    ]


def test_load_selection_unknown_tree_raises(legacy_db):
    with pytest.raises(ValueError, match="99999"):
        legacy.load_selection([(legacy.SOURCE_API, 99999)])


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
    assert tree.source == legacy.SOURCE_API


@pytest.mark.django_db
def test_legacy_areas_endpoint_returns_counts(legacy_db):
    response = _client("admin").get("/api/datasets/legacy/areas/")
    assert response.status_code == 200
    assert response.data[0] == {
        "id": 26,
        "name": "Area 1",
        "campaign": "Campaña Semiponti",
        "tree_count": 2,
        "polygon": _geojson_polygon(SQUARE),
    }


@pytest.mark.django_db
def test_legacy_areas_endpoint_forbidden_for_surveyor(legacy_db):
    response = _client("surveyor").get("/api/datasets/legacy/areas/")
    assert response.status_code == 403


@pytest.mark.django_db
def test_legacy_areas_returns_503_when_not_configured(settings):
    settings.LEGACY_API_DB_URL = ""
    response = _client("admin").get("/api/datasets/legacy/areas/")
    assert response.status_code == 503
    assert "ARBOCENSUS_API_DB_URL" in response.data["detail"]


@pytest.mark.django_db
def test_legacy_trees_endpoint_returns_both_sources(legacy_db):
    response = _client("admin").get("/api/datasets/legacy/trees/")
    assert response.status_code == 200
    assert len(response.data) == 6
    assert response.data[0] == {
        "source": legacy.SOURCE_API,
        "external_id": 776,
        "lat": -33.45,
        "lon": -70.55,
        "species": "Quillaja saponaria",
        "area_id": 26,
        "already_imported": False,
    }


@pytest.mark.django_db
def test_legacy_trees_endpoint_forbidden_for_surveyor(legacy_db):
    response = _client("surveyor").get("/api/datasets/legacy/trees/")
    assert response.status_code == 403


@pytest.mark.django_db
def test_legacy_trees_returns_503_when_not_configured(settings):
    settings.LEGACY_API_DB_URL = ""
    settings.LEGACY_APP_DB_URL = ""
    response = _client("admin").get("/api/datasets/legacy/trees/")
    assert response.status_code == 503
    assert "ARBOCENSUS_API_DB_URL" in response.data["detail"]
    assert "ARBOCENSUS_DB_URL" in response.data["detail"]


@pytest.mark.django_db
def test_from_legacy_selection_creates_exact_trees(legacy_db):
    response = _client("admin").post(
        "/api/datasets/from-legacy-selection/",
        {
            "name": "Selección mixta",
            "trees": [
                {"source": legacy.SOURCE_API, "external_id": 776},
                {"source": legacy.SOURCE_APP, "external_id": 96905},
            ],
        },
        format="json",
    )
    assert response.status_code == 201
    assert response.data["name"] == "Selección mixta"
    assert response.data["total_trees"] == 2
    trees = Tree.objects.filter(dataset_id=response.data["id"])
    assert {(tree.source, tree.external_id) for tree in trees} == {
        (legacy.SOURCE_API, 776),
        (legacy.SOURCE_APP, 96905),
    }


@pytest.mark.django_db
def test_from_legacy_selection_deduplicates_selection(legacy_db):
    response = _client("admin").post(
        "/api/datasets/from-legacy-selection/",
        {
            "name": "Con duplicados",
            "trees": [
                {"source": legacy.SOURCE_API, "external_id": 776},
                {"source": legacy.SOURCE_API, "external_id": 776},
            ],
        },
        format="json",
    )
    assert response.status_code == 201
    assert response.data["total_trees"] == 1


@pytest.mark.django_db
def test_from_legacy_selection_unknown_tree_returns_400(legacy_db):
    response = _client("admin").post(
        "/api/datasets/from-legacy-selection/",
        {
            "name": "Inexistente",
            "trees": [{"source": legacy.SOURCE_API, "external_id": 99999}],
        },
        format="json",
    )
    assert response.status_code == 400
    assert not Dataset.objects.exists()


@pytest.mark.django_db
def test_from_legacy_selection_empty_trees_returns_400(legacy_db):
    response = _client("admin").post(
        "/api/datasets/from-legacy-selection/",
        {"name": "Vacío", "trees": []},
        format="json",
    )
    assert response.status_code == 400


@pytest.mark.django_db
def test_from_legacy_selection_forbidden_for_surveyor(legacy_db):
    response = _client("surveyor").post(
        "/api/datasets/from-legacy-selection/",
        {
            "name": "X",
            "trees": [{"source": legacy.SOURCE_API, "external_id": 776}],
        },
        format="json",
    )
    assert response.status_code == 403


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
    settings.LEGACY_API_DB_URL = ""
    response = _client("admin").post(
        "/api/datasets/import-legacy/", {"area_id": 26}, format="json"
    )
    assert response.status_code == 503
