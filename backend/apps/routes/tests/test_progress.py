import uuid

import pytest
from apps.optimization.models import OptimizationJob, RoutingConfig, RoutingSolution
from apps.routes.models import Route, RouteStop
from rest_framework.test import APIClient
from tests.factories import CustomUserFactory

pytestmark = pytest.mark.django_db


@pytest.fixture
def make_solution(make_dataset_with_trees):
    def _make(coords, published=True):
        dataset, trees = make_dataset_with_trees(coords)
        config = RoutingConfig.objects.create(dataset=dataset)
        job = OptimizationJob.objects.create(config=config)
        solution = RoutingSolution.objects.create(job=job, total_routes=1)
        if published:
            solution.publish()
        return dataset, trees, solution

    return _make


def _make_route(solution, trees, surveyor=None, statuses=None):
    route_number = solution.routes.count() + 1
    route = Route.objects.create(
        solution=solution,
        route_number=route_number,
        total_trees=len(trees),
        surveyor=surveyor,
    )
    for index, tree in enumerate(trees):
        RouteStop.objects.create(
            route=route,
            tree=tree,
            sequence=index,
            status=(statuses or [])[index] if statuses else RouteStop.Status.PENDING,
        )
    return route


def _admin_client():
    client = APIClient()
    client.force_authenticate(user=CustomUserFactory(role="admin"))
    return client


def test_progress_aggregates_totals_routes_and_surveyors(make_solution):
    dataset, trees, solution = make_solution(
        [(-70.65, -33.45), (-70.66, -33.46), (-70.67, -33.47), (-70.68, -33.48)]
    )
    ana = CustomUserFactory(username="ana", role="surveyor")
    _make_route(
        solution,
        trees[:2],
        surveyor=ana,
        statuses=[RouteStop.Status.VISITED, RouteStop.Status.SKIPPED],
    )
    _make_route(
        solution,
        trees[2:],
        statuses=[RouteStop.Status.VISITED, RouteStop.Status.PENDING],
    )

    response = _admin_client().get(f"/api/routes/progress/?dataset={dataset.id}")

    assert response.status_code == 200
    assert response.data["solution"]["id"] == str(solution.id)
    assert response.data["totals"] == {
        "total": 4,
        "visited": 2,
        "skipped": 1,
        "pending": 1,
    }
    assert [route["route_number"] for route in response.data["routes"]] == [1, 2]
    assert response.data["routes"][0] == {
        "id": str(solution.routes.get(route_number=1).id),
        "route_number": 1,
        "surveyor_id": str(ana.id),
        "surveyor_name": "ana",
        "total": 2,
        "visited": 1,
        "skipped": 1,
        "pending": 0,
    }
    assert [s["surveyor_name"] for s in response.data["surveyors"]] == [
        "ana",
        "Sin asignar",
    ]
    assert response.data["surveyors"][1]["route_count"] == 1
    assert response.data["surveyors"][1]["pending"] == 1


def test_progress_groups_every_route_of_a_surveyor(make_solution):
    dataset, trees, solution = make_solution(
        [(-70.65, -33.45), (-70.66, -33.46), (-70.67, -33.47)]
    )
    ana = CustomUserFactory(username="ana", role="surveyor")
    _make_route(
        solution, trees[:2], surveyor=ana, statuses=[RouteStop.Status.VISITED] * 2
    )
    _make_route(solution, trees[2:], surveyor=ana, statuses=[RouteStop.Status.PENDING])

    response = _admin_client().get(f"/api/routes/progress/?dataset={dataset.id}")

    assert response.data["surveyors"] == [
        {
            "surveyor_id": str(ana.id),
            "surveyor_name": "ana",
            "route_count": 2,
            "total": 3,
            "visited": 2,
            "skipped": 0,
            "pending": 1,
        }
    ]


def test_progress_ignores_unpublished_solution(make_solution):
    dataset, trees, solution = make_solution([(-70.65, -33.45)], published=False)
    _make_route(solution, trees)

    response = _admin_client().get(f"/api/routes/progress/?dataset={dataset.id}")

    assert response.status_code == 200
    assert response.data["solution"] is None
    assert response.data["routes"] == []
    assert response.data["totals"]["total"] == 0


def test_progress_requires_valid_dataset(make_solution):
    client = _admin_client()

    assert client.get("/api/routes/progress/").status_code == 400
    assert client.get("/api/routes/progress/?dataset=nope").status_code == 400
    assert (
        client.get(f"/api/routes/progress/?dataset={uuid.uuid4()}").status_code == 404
    )


def test_progress_is_admin_only(make_solution):
    dataset, _, _ = make_solution([(-70.65, -33.45)])
    client = APIClient()
    client.force_authenticate(user=CustomUserFactory(role="surveyor"))

    response = client.get(f"/api/routes/progress/?dataset={dataset.id}")

    assert response.status_code == 403


def test_progress_geojson_returns_stops_with_status(make_solution):
    dataset, trees, solution = make_solution([(-70.65, -33.45), (-70.66, -33.46)])
    ana = CustomUserFactory(username="ana", role="surveyor")
    _make_route(
        solution,
        trees,
        surveyor=ana,
        statuses=[RouteStop.Status.VISITED, RouteStop.Status.PENDING],
    )

    response = _admin_client().get(
        f"/api/routes/progress-geojson/?dataset={dataset.id}"
    )

    assert response.status_code == 200
    features = response.data["features"]
    assert len(features) == 2
    assert features[0]["geometry"]["coordinates"] == [-70.65, -33.45]
    assert features[0]["properties"]["status"] == RouteStop.Status.VISITED
    assert features[0]["properties"]["surveyor_name"] == "ana"
    assert features[1]["properties"]["status"] == RouteStop.Status.PENDING


def test_progress_geojson_empty_without_published_solution(make_solution):
    dataset, trees, solution = make_solution([(-70.65, -33.45)], published=False)
    _make_route(solution, trees)

    response = _admin_client().get(
        f"/api/routes/progress-geojson/?dataset={dataset.id}"
    )

    assert response.status_code == 200
    assert response.data["features"] == []
