import pytest
from django.core.cache import cache
from rest_framework.test import APIClient

pytestmark = pytest.mark.django_db

_LOCMEM_CACHE = {
    "default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}
}


@pytest.fixture(autouse=True)
def _use_locmem_cache(settings):
    settings.CACHES = _LOCMEM_CACHE
    cache.clear()


def test_token_obtain_is_throttled_after_rate_exceeded():
    client = APIClient()
    payload = {"username": "nobody", "password": "wrong"}

    for _ in range(5):
        response = client.post("/api/auth/token/", payload)
        assert response.status_code == 401

    response = client.post("/api/auth/token/", payload)
    assert response.status_code == 429
