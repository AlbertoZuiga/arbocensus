import pytest
from apps.optimization.models import OptimizationJob, RoutingConfig, RoutingSolution
from apps.routes.models import Route, RouteStop
from django.db import connection
from django.test.utils import CaptureQueriesContext
from rest_framework.test import APIClient
from tests.factories import CustomUserFactory

pytestmark = pytest.mark.django_db


@pytest.fixture
def surveyor():
    return CustomUserFactory(role="surveyor")


@pytest.fixture
def make_solution(make_dataset_with_trees, surveyor):
    def _make(route_count):
        coords = [
            (-70.65 - i * 0.01, -33.45 - i * 0.01) for i in range(route_count * 2)
        ]
        dataset, trees = make_dataset_with_trees(coords)
        config = RoutingConfig.objects.create(dataset=dataset)
        job = OptimizationJob.objects.create(config=config)
        solution = RoutingSolution.objects.create(job=job, total_routes=route_count)
        solution.publish()
        routes = []
        for number in range(route_count):
            route = Route.objects.create(
                solution=solution,
                route_number=number,
                total_trees=2,
                surveyor=surveyor,
            )
            for sequence, tree in enumerate(trees[number * 2 : number * 2 + 2]):
                RouteStop.objects.create(route=route, tree=tree, sequence=sequence)
            routes.append(route)
        return solution, routes

    return _make


def _client(user):
    client = APIClient()
    client.force_authenticate(user=user)
    return client


def _list(client, solution):
    return client.get(f"/api/routes/?solution_id={solution.id}")


def test_list_reports_counts_per_status(make_solution, surveyor):
    solution, routes = make_solution(1)
    stops = list(routes[0].stops.all())
    stops[0].mark_visited()
    stops[1].mark_skipped("Acceso bloqueado")
    response = _list(_client(surveyor), solution)
    assert response.status_code == 200
    route = response.data["results"][0]
    assert route["visited_count"] == 1
    assert route["skipped_count"] == 1
    assert route["pending_count"] == 0


def test_list_query_count_does_not_grow_with_routes(make_solution, surveyor):
    client = _client(surveyor)
    solution_one, _ = make_solution(1)
    with CaptureQueriesContext(connection) as one_route:
        assert _list(client, solution_one).status_code == 200
    solution_many, _ = make_solution(5)
    with CaptureQueriesContext(connection) as many_routes:
        response = _list(client, solution_many)
    assert len(response.data["results"]) == 5
    assert len(many_routes.captured_queries) == len(one_route.captured_queries)


def test_my_route_reports_counts(make_solution, surveyor):
    _, routes = make_solution(1)
    routes[0].stops.all()[0].mark_visited()
    response = _client(surveyor).get("/api/routes/my-route/")
    assert response.status_code == 200
    assert response.data[0]["visited_count"] == 1
    assert response.data[0]["pending_count"] == 1


def test_retrieve_reports_counts(make_solution, surveyor):
    _, routes = make_solution(1)
    routes[0].stops.all()[0].mark_skipped("Acceso bloqueado")
    response = _client(surveyor).get(f"/api/routes/{routes[0].id}/")
    assert response.status_code == 200
    assert response.data["skipped_count"] == 1
    assert response.data["pending_count"] == 1
    assert len(response.data["stops"]) == 2
