import pytest
from apps.accounts.models import CustomUser
from rest_framework.test import APIClient
from tests.factories import CustomUserFactory

pytestmark = pytest.mark.django_db

USERS_URL = "/api/auth/users/"


def admin_client():
    admin = CustomUserFactory(role=CustomUser.Role.ADMIN)
    client = APIClient()
    client.force_authenticate(user=admin)
    return admin, client


def test_admin_creates_surveyor_and_admin():
    _, client = admin_client()

    for role in (CustomUser.Role.SURVEYOR, CustomUser.Role.ADMIN):
        response = client.post(
            USERS_URL,
            {
                "username": f"new_{role}",
                "email": f"{role}@example.com",
                "role": role,
                "password": "s3cret-pass",
            },
        )
        assert response.status_code == 201, response.data
        assert response.data["role"] == role
        assert "password" not in response.data


def test_create_hashes_password():
    _, client = admin_client()
    response = client.post(
        USERS_URL,
        {
            "username": "hashed",
            "role": CustomUser.Role.SURVEYOR,
            "password": "raw-pass",
        },
    )
    assert response.status_code == 201
    user = CustomUser.objects.get(username="hashed")
    assert user.password != "raw-pass"
    assert user.check_password("raw-pass")


def test_non_admin_forbidden():
    surveyor = CustomUserFactory(role=CustomUser.Role.SURVEYOR)
    client = APIClient()
    client.force_authenticate(user=surveyor)
    assert client.get(USERS_URL).status_code == 403
    assert client.post(USERS_URL, {"username": "x"}).status_code == 403


def test_last_admin_demote_blocked():
    admin = CustomUserFactory(role=CustomUser.Role.ADMIN)
    target = CustomUserFactory(role=CustomUser.Role.ADMIN)
    client = APIClient()
    client.force_authenticate(user=admin)

    admin.is_active = False
    admin.save(update_fields=["is_active"])

    response = client.patch(
        f"{USERS_URL}{target.id}/", {"role": CustomUser.Role.SURVEYOR}
    )
    assert response.status_code == 400
    target.refresh_from_db()
    assert target.role == CustomUser.Role.ADMIN


def test_self_demote_blocked():
    admin, client = admin_client()
    response = client.patch(
        f"{USERS_URL}{admin.id}/", {"role": CustomUser.Role.SURVEYOR}
    )
    assert response.status_code == 400
    admin.refresh_from_db()
    assert admin.role == CustomUser.Role.ADMIN


def test_deactivate_soft_deletes():
    _, client = admin_client()
    target = CustomUserFactory(role=CustomUser.Role.SURVEYOR)

    response = client.delete(f"{USERS_URL}{target.id}/")
    assert response.status_code == 204
    assert CustomUser.objects.filter(id=target.id).exists()
    target.refresh_from_db()
    assert target.is_active is False


def test_surveyor_list_still_returns_only_surveyors():
    admin, client = admin_client()
    surveyor = CustomUserFactory(role=CustomUser.Role.SURVEYOR)

    response = client.get("/api/auth/surveyors/")
    assert response.status_code == 200
    results = response.data["results"] if "results" in response.data else response.data
    roles = {row["role"] for row in results}
    assert roles == {CustomUser.Role.SURVEYOR}
    assert str(surveyor.id) in [row["id"] for row in results]
