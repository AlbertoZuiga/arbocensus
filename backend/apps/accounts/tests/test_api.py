import pytest
from rest_framework.test import APIClient
from tests.factories import CustomUserFactory

pytestmark = pytest.mark.django_db


def test_me_returns_authenticated_user():
    user = CustomUserFactory(role="admin")
    client = APIClient()
    client.force_authenticate(user=user)
    response = client.get("/api/auth/me/")
    assert response.status_code == 200
    assert response.data["username"] == user.username
    assert response.data["role"] == "admin"


def test_me_requires_authentication():
    response = APIClient().get("/api/auth/me/")
    assert response.status_code == 401
