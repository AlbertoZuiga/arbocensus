import pytest
from apps.optimization.models import OptimizationJob, RoutingConfig, RoutingSolution
from apps.routes.models import Route, RouteStop
from rest_framework.test import APIClient
from tests.factories import CustomUserFactory

pytestmark = pytest.mark.django_db


@pytest.fixture
def solution_with_route(make_dataset_with_trees):
    dataset, trees = make_dataset_with_trees([(-70.65, -33.45), (-70.66, -33.46)])
    config = RoutingConfig.objects.create(dataset=dataset)
    job = OptimizationJob.objects.create(config=config)
    solution = RoutingSolution.objects.create(job=job, total_routes=1)
    route = Route.objects.create(
        solution=solution, route_number=1, total_trees=len(trees)
    )
    stops = [
        RouteStop.objects.create(route=route, tree=tree, sequence=i)
        for i, tree in enumerate(trees)
    ]
    return solution, route, stops


def _client():
    client = APIClient()
    client.force_authenticate(user=CustomUserFactory())
    return client


def test_routes_filtered_by_solution(solution_with_route):
    solution, _, _ = solution_with_route
    response = _client().get(f"/api/routes/?solution_id={solution.id}")
    assert response.status_code == 200
    assert response.data["count"] == 1


def test_geojson_returns_linestring_per_route(solution_with_route):
    solution, _, _ = solution_with_route
    response = _client().get(f"/api/routes/geojson/?solution_id={solution.id}")
    assert response.status_code == 200
    assert response.data["type"] == "FeatureCollection"
    feature = response.data["features"][0]
    assert feature["geometry"]["type"] == "LineString"
    assert feature["geometry"]["coordinates"] == [[-70.65, -33.45], [-70.66, -33.46]]


def test_visit_marks_stop_visited(solution_with_route):
    _, _, stops = solution_with_route
    response = _client().post(f"/api/routes/stops/{stops[0].id}/visit/")
    assert response.status_code == 200
    assert response.data["visited"] is True
    stops[0].refresh_from_db()
    assert stops[0].visited is True
    assert stops[0].visited_at is not None
