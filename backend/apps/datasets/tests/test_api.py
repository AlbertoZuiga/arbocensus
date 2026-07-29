import pytest
from apps.datasets.models import Dataset
from django.core.files.uploadedfile import SimpleUploadedFile
from rest_framework.test import APIClient
from tests.factories import CustomUserFactory

pytestmark = pytest.mark.django_db

CSV = b"lat,lon\n-33.45,-70.65\n-33.46,-70.66\n"


def _client(role):
    client = APIClient()
    client.force_authenticate(user=CustomUserFactory(role=role))
    return client


def test_admin_upload_csv_sets_tree_count():
    upload = SimpleUploadedFile("trees.csv", CSV, content_type="text/csv")
    response = _client("admin").post(
        "/api/datasets/", {"name": "Test", "file": upload}, format="multipart"
    )
    assert response.status_code == 201
    assert response.data["total_trees"] == 2
    assert Dataset.objects.get(id=response.data["id"]).total_trees == 2


def test_upload_without_lat_column_returns_400_and_creates_no_dataset():
    bad_csv = b"foo,lon\n1,2\n"
    upload = SimpleUploadedFile("trees.csv", bad_csv, content_type="text/csv")
    response = _client("admin").post(
        "/api/datasets/", {"name": "Broken", "file": upload}, format="multipart"
    )
    assert response.status_code == 400
    assert "No lat column" in str(response.data)
    assert not Dataset.objects.exists()


def test_upload_reports_skipped_rows():
    csv = b"lat,lon\n-33.45,-70.65\n,-70.66\n-33.47,\n"
    upload = SimpleUploadedFile("trees.csv", csv, content_type="text/csv")
    response = _client("admin").post(
        "/api/datasets/", {"name": "Partial", "file": upload}, format="multipart"
    )
    assert response.status_code == 201
    assert response.data["total_trees"] == 1
    assert response.data["skipped_rows"] == 2


def test_surveyor_cannot_create_dataset():
    upload = SimpleUploadedFile("trees.csv", CSV, content_type="text/csv")
    response = _client("surveyor").post(
        "/api/datasets/", {"name": "Test", "file": upload}, format="multipart"
    )
    assert response.status_code == 403


def test_admin_can_patch_name_and_description(make_dataset_with_trees):
    dataset, _ = make_dataset_with_trees([(-70.65, -33.45)])
    response = _client("admin").patch(
        f"/api/datasets/{dataset.id}/",
        {"name": "Renamed", "description": "Nueva descripción"},
        format="json",
    )
    assert response.status_code == 200
    assert response.data["name"] == "Renamed"
    assert response.data["description"] == "Nueva descripción"
    dataset.refresh_from_db()
    assert dataset.name == "Renamed"
    assert dataset.description == "Nueva descripción"


def test_patch_does_not_alter_total_trees(make_dataset_with_trees):
    dataset, trees = make_dataset_with_trees([(-70.65, -33.45), (-70.66, -33.46)])
    original_count = dataset.total_trees
    response = _client("admin").patch(
        f"/api/datasets/{dataset.id}/", {"name": "Edited"}, format="json"
    )
    assert response.status_code == 200
    assert response.data["total_trees"] == original_count
    dataset.refresh_from_db()
    assert dataset.total_trees == original_count
    assert dataset.tree_set.count() == len(trees)


def test_surveyor_cannot_update_dataset(make_dataset_with_trees):
    dataset, _ = make_dataset_with_trees([(-70.65, -33.45)])
    response = _client("surveyor").patch(
        f"/api/datasets/{dataset.id}/", {"name": "Renamed"}, format="multipart"
    )
    assert response.status_code == 403


def test_admin_can_delete_dataset(make_dataset_with_trees):
    dataset, _ = make_dataset_with_trees([(-70.65, -33.45)])
    response = _client("admin").delete(f"/api/datasets/{dataset.id}/")
    assert response.status_code == 204
    assert not Dataset.objects.filter(id=dataset.id).exists()


def test_surveyor_cannot_delete_dataset(make_dataset_with_trees):
    dataset, _ = make_dataset_with_trees([(-70.65, -33.45)])
    response = _client("surveyor").delete(f"/api/datasets/{dataset.id}/")
    assert response.status_code == 403
    assert Dataset.objects.filter(id=dataset.id).exists()


def test_trees_endpoint_returns_geojson(make_dataset_with_trees):
    dataset, _ = make_dataset_with_trees([(-70.65, -33.45), (-70.66, -33.46)])
    response = _client("surveyor").get(f"/api/datasets/{dataset.id}/trees/")
    assert response.status_code == 200
    assert response.data["type"] == "FeatureCollection"
    coordinates = [f["geometry"]["coordinates"] for f in response.data["features"]]
    assert sorted(coordinates) == [[-70.66, -33.46], [-70.65, -33.45]]


def test_deactivate_marks_trees_inactive(make_dataset_with_trees):
    dataset, trees = make_dataset_with_trees([(-70.65, -33.45), (-70.66, -33.46)])
    response = _client("admin").post(
        f"/api/datasets/{dataset.id}/trees/deactivate/",
        {"tree_ids": [str(trees[0].id)]},
        format="json",
    )
    assert response.status_code == 200
    trees[0].refresh_from_db()
    trees[1].refresh_from_db()
    assert trees[0].is_active is False
    assert trees[1].is_active is True


def test_deactivate_recalculates_total_trees(make_dataset_with_trees):
    dataset, trees = make_dataset_with_trees([(-70.65, -33.45), (-70.66, -33.46)])
    _client("admin").post(
        f"/api/datasets/{dataset.id}/trees/deactivate/",
        {"tree_ids": [str(trees[0].id)]},
        format="json",
    )
    dataset.refresh_from_db()
    assert dataset.total_trees == 1


def test_deactivate_leaves_routestop_intact(make_dataset_with_trees):
    from apps.optimization.models import OptimizationJob, RoutingConfig, RoutingSolution
    from apps.routes.models import Route, RouteStop

    dataset, trees = make_dataset_with_trees([(-70.65, -33.45), (-70.66, -33.46)])
    config = RoutingConfig.objects.create(dataset=dataset)
    job = OptimizationJob.objects.create(config=config)
    solution = RoutingSolution.objects.create(
        job=job, strategy="global", total_routes=1
    )
    route = Route.objects.create(solution=solution, route_number=1, total_trees=1)
    stop = RouteStop.objects.create(route=route, tree=trees[0], sequence=1)

    _client("admin").post(
        f"/api/datasets/{dataset.id}/trees/deactivate/",
        {"tree_ids": [str(trees[0].id)]},
        format="json",
    )

    assert RouteStop.objects.filter(id=stop.id).exists()
    trees[0].refresh_from_db()
    assert trees[0].is_active is False


def test_deactivated_tree_not_in_trees_endpoint(make_dataset_with_trees):
    dataset, trees = make_dataset_with_trees([(-70.65, -33.45), (-70.66, -33.46)])
    _client("admin").post(
        f"/api/datasets/{dataset.id}/trees/deactivate/",
        {"tree_ids": [str(trees[0].id)]},
        format="json",
    )
    response = _client("surveyor").get(f"/api/datasets/{dataset.id}/trees/")
    assert response.status_code == 200
    ids_in_response = {f["properties"]["id"] for f in response.data["features"]}
    assert str(trees[0].id) not in ids_in_response
    assert str(trees[1].id) in ids_in_response


def test_deactivate_requires_admin(make_dataset_with_trees):
    dataset, trees = make_dataset_with_trees([(-70.65, -33.45)])
    response = _client("surveyor").post(
        f"/api/datasets/{dataset.id}/trees/deactivate/",
        {"tree_ids": [str(trees[0].id)]},
        format="json",
    )
    assert response.status_code == 403
