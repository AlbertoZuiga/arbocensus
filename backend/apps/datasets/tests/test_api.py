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


def test_surveyor_cannot_create_dataset():
    upload = SimpleUploadedFile("trees.csv", CSV, content_type="text/csv")
    response = _client("surveyor").post(
        "/api/datasets/", {"name": "Test", "file": upload}, format="multipart"
    )
    assert response.status_code == 403


def test_trees_endpoint_returns_geojson(make_dataset_with_trees):
    dataset, _ = make_dataset_with_trees([(-70.65, -33.45), (-70.66, -33.46)])
    response = _client("surveyor").get(f"/api/datasets/{dataset.id}/trees/")
    assert response.status_code == 200
    assert response.data["type"] == "FeatureCollection"
    coordinates = [f["geometry"]["coordinates"] for f in response.data["features"]]
    assert sorted(coordinates) == [[-70.66, -33.46], [-70.65, -33.45]]
