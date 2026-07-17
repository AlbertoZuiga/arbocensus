import pytest
from apps.optimization.models import RoutingConfig
from django.core.exceptions import ValidationError
from tests.factories import DatasetFactory

pytestmark = pytest.mark.django_db


@pytest.mark.parametrize(
    "field",
    ["min_route_time_sec", "max_route_time_sec", "service_time_sec"],
)
def test_duration_fields_must_be_positive(field):
    config = RoutingConfig(dataset=DatasetFactory(), **{field: 0})
    with pytest.raises(ValidationError):
        config.full_clean()


def test_service_time_defaults_to_three_minutes():
    config = RoutingConfig(dataset=DatasetFactory())
    assert config.service_time_sec == 180


def test_max_route_time_must_not_be_below_min():
    config = RoutingConfig(
        dataset=DatasetFactory(),
        min_route_time_sec=7200,
        max_route_time_sec=3600,
    )
    with pytest.raises(ValidationError):
        config.full_clean()
