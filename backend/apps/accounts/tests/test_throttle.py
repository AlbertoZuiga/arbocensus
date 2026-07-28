import pytest
from django.core.cache import cache
from rest_framework.test import APIClient

pytestmark = pytest.mark.django_db


def test_token_obtain_is_throttled_after_rate_exceeded():
    cache.clear()
    client = APIClient()
    payload = {"username": "nobody", "password": "wrong"}

    for _ in range(5):
        response = client.post("/api/auth/token/", payload)
        assert response.status_code == 401

    response = client.post("/api/auth/token/", payload)
    assert response.status_code == 429
