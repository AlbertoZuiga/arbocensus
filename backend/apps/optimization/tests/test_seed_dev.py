import pytest
from apps.datasets.models import Dataset
from django.contrib.auth import get_user_model
from django.core.management import call_command


@pytest.mark.django_db
def test_seed_dev_creates_users_and_dataset(settings):
    settings.SEED_ADMIN_COUNT = 1
    settings.SEED_SURVEYOR_COUNT = 2
    settings.SEED_DEV_TREES = 5
    settings.SEED_USER_PASSWORD = "secret-dev"
    user_model = get_user_model()

    call_command("seed_dev")

    assert user_model.objects.count() == 3
    admin = user_model.objects.get(username="admin1")
    surveyor = user_model.objects.get(username="surveyor2")
    assert admin.role == user_model.Role.ADMIN
    assert surveyor.role == user_model.Role.SURVEYOR
    assert surveyor.check_password("secret-dev")
    dataset = Dataset.objects.get(name=settings.SEED_DEV_DATASET_NAME)
    assert dataset.total_trees == 5


@pytest.mark.django_db
def test_seed_dev_is_idempotent(settings):
    settings.SEED_ADMIN_COUNT = 1
    settings.SEED_SURVEYOR_COUNT = 2
    settings.SEED_DEV_TREES = 5
    user_model = get_user_model()

    call_command("seed_dev")
    call_command("seed_dev")

    assert user_model.objects.count() == 3
    assert Dataset.objects.filter(name=settings.SEED_DEV_DATASET_NAME).count() == 1
