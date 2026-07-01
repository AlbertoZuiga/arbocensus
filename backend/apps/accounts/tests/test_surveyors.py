import pytest
from rest_framework.test import APIClient
from tests.factories import CustomUserFactory

pytestmark = pytest.mark.django_db


def test_admin_lists_only_surveyors():
    admin = CustomUserFactory(role="admin")
    surveyor = CustomUserFactory(role="surveyor", email="s@example.com")
    CustomUserFactory(role="admin")

    client = APIClient()
    client.force_authenticate(user=admin)
    response = client.get("/api/auth/surveyors/")

    assert response.status_code == 200
    results = response.data["results"] if "results" in response.data else response.data
    ids = [row["id"] for row in results]
    assert str(surveyor.id) in ids
    assert str(admin.id) not in ids
    for row in results:
        assert row["role"] == "surveyor"


def test_surveyor_response_exposes_expected_fields():
    admin = CustomUserFactory(role="admin")
    CustomUserFactory(
        role="surveyor",
        first_name="Ada",
        last_name="Lovelace",
        email="ada@example.com",
    )

    client = APIClient()
    client.force_authenticate(user=admin)
    response = client.get("/api/auth/surveyors/")

    results = response.data["results"] if "results" in response.data else response.data
    row = next(r for r in results if r["email"] == "ada@example.com")
    assert set(row.keys()) == {
        "id",
        "username",
        "first_name",
        "last_name",
        "email",
        "role",
        "role_display",
    }
    assert row["first_name"] == "Ada"
    assert row["last_name"] == "Lovelace"


def test_surveyor_forbidden_for_non_admin():
    surveyor = CustomUserFactory(role="surveyor")
    client = APIClient()
    client.force_authenticate(user=surveyor)
    response = client.get("/api/auth/surveyors/")
    assert response.status_code == 403


def test_surveyor_requires_authentication():
    response = APIClient().get("/api/auth/surveyors/")
    assert response.status_code == 401
