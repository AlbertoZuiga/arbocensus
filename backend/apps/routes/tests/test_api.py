from unittest.mock import MagicMock

import pytest
from apps.optimization.models import OptimizationJob, RoutingConfig, RoutingSolution
from apps.routes.models import Route, RouteStop
from rest_framework.test import APIClient
from tests.factories import CustomUserFactory

pytestmark = pytest.mark.django_db


@pytest.fixture
def surveyor():
    return CustomUserFactory(role="surveyor")


@pytest.fixture
def solution_with_route(make_dataset_with_trees, surveyor):
    dataset, trees = make_dataset_with_trees([(-70.65, -33.45), (-70.66, -33.46)])
    config = RoutingConfig.objects.create(dataset=dataset)
    job = OptimizationJob.objects.create(config=config)
    solution = RoutingSolution.objects.create(job=job, total_routes=1)
    solution.publish()
    route = Route.objects.create(
        solution=solution, route_number=1, total_trees=len(trees), surveyor=surveyor
    )
    stops = [
        RouteStop.objects.create(route=route, tree=tree, sequence=i)
        for i, tree in enumerate(trees)
    ]
    return solution, route, stops


def _client(user=None):
    client = APIClient()
    client.force_authenticate(user=user or CustomUserFactory())
    return client


def test_routes_filtered_by_solution(solution_with_route):
    solution, _, _ = solution_with_route
    admin = CustomUserFactory(role="admin")
    response = _client(admin).get(f"/api/routes/?solution_id={solution.id}")
    assert response.status_code == 200
    assert response.data["count"] == 1


def test_surveyor_lists_only_own_routes(solution_with_route, surveyor):
    _, route, _ = solution_with_route
    other = CustomUserFactory(role="surveyor")

    own = _client(surveyor).get("/api/routes/")
    assert own.status_code == 200
    assert [r["id"] for r in own.data["results"]] == [str(route.id)]

    foreign = _client(other).get("/api/routes/")
    assert foreign.status_code == 200
    assert foreign.data["results"] == []


def test_surveyor_cannot_retrieve_foreign_route(solution_with_route):
    _, route, _ = solution_with_route
    other = CustomUserFactory(role="surveyor")
    response = _client(other).get(f"/api/routes/{route.id}/")
    assert response.status_code == 404


def test_admin_lists_all_routes(solution_with_route):
    _, route, _ = solution_with_route
    admin = CustomUserFactory(role="admin")
    response = _client(admin).get("/api/routes/")
    assert response.status_code == 200
    assert [r["id"] for r in response.data["results"]] == [str(route.id)]


def test_geojson_returns_street_following_path_per_route(
    solution_with_route, monkeypatch
):
    solution, _, _ = solution_with_route
    street_path = [[-70.65, -33.45], [-70.655, -33.455], [-70.66, -33.46]]
    fetch = MagicMock(return_value=street_path)
    monkeypatch.setattr("apps.routes.views.fetch_route_path", fetch)

    admin = CustomUserFactory(role="admin")
    response = _client(admin).get(f"/api/routes/geojson/?solution_id={solution.id}")

    assert response.status_code == 200
    assert response.data["type"] == "FeatureCollection"
    feature = response.data["features"][0]
    assert feature["geometry"]["type"] == "LineString"
    assert feature["geometry"]["coordinates"] == street_path
    assert feature["properties"]["stops"] == [[-70.65, -33.45], [-70.66, -33.46]]
    fetch.assert_called_once_with([[-70.65, -33.45], [-70.66, -33.46]])


def test_visit_marks_stop_visited(solution_with_route, surveyor):
    _, _, stops = solution_with_route
    response = _client(surveyor).post(f"/api/routes/stops/{stops[0].id}/visit/")
    assert response.status_code == 200
    assert response.data["visited"] is True
    stops[0].refresh_from_db()
    assert stops[0].visited is True
    assert stops[0].visited_at is not None


def test_visit_next_pending_stop_in_order_succeeds(solution_with_route, surveyor):
    _, _, stops = solution_with_route
    first = _client(surveyor).post(f"/api/routes/stops/{stops[0].id}/visit/")
    assert first.status_code == 200
    second = _client(surveyor).post(f"/api/routes/stops/{stops[1].id}/visit/")
    assert second.status_code == 200
    stops[1].refresh_from_db()
    assert stops[1].visited is True


def test_visit_out_of_order_returns_400(solution_with_route, surveyor):
    _, _, stops = solution_with_route
    response = _client(surveyor).post(f"/api/routes/stops/{stops[1].id}/visit/")
    assert response.status_code == 400
    assert response.data["detail"] == "Debes visitar los árboles anteriores primero."
    stops[1].refresh_from_db()
    assert stops[1].visited is False


def test_revisiting_visited_stop_is_idempotent(solution_with_route, surveyor):
    _, _, stops = solution_with_route
    _client(surveyor).post(f"/api/routes/stops/{stops[0].id}/visit/")
    stops[0].refresh_from_db()
    first_visited_at = stops[0].visited_at
    response = _client(surveyor).post(f"/api/routes/stops/{stops[0].id}/visit/")
    assert response.status_code == 200
    assert response.data["visited"] is True
    stops[0].refresh_from_db()
    assert stops[0].visited_at == first_visited_at


def test_visit_foreign_stop_returns_404(solution_with_route):
    _, _, stops = solution_with_route
    other = CustomUserFactory(role="surveyor")
    response = _client(other).post(f"/api/routes/stops/{stops[0].id}/visit/")
    assert response.status_code == 404
    stops[0].refresh_from_db()
    assert stops[0].visited is False


def test_visit_rejected_for_non_surveyor(solution_with_route):
    _, _, stops = solution_with_route
    admin = CustomUserFactory(role="admin")
    response = _client(admin).post(f"/api/routes/stops/{stops[0].id}/visit/")
    assert response.status_code == 403


def test_admin_assigns_route_to_surveyor(solution_with_route):
    _, route, _ = solution_with_route
    admin = CustomUserFactory(role="admin")
    target = CustomUserFactory(role="surveyor")
    response = _client(admin).patch(
        f"/api/routes/{route.id}/assign/", {"surveyor_id": str(target.id)}
    )
    assert response.status_code == 200
    assert response.data["surveyor"] == target.id
    route.refresh_from_db()
    assert route.surveyor == target


def test_assign_rejected_for_non_admin(solution_with_route):
    _, route, _ = solution_with_route
    target = CustomUserFactory(role="surveyor")
    response = _client(target).patch(
        f"/api/routes/{route.id}/assign/", {"surveyor_id": str(target.id)}
    )
    assert response.status_code == 403


def test_assign_rejects_non_surveyor_target(solution_with_route):
    _, route, _ = solution_with_route
    admin = CustomUserFactory(role="admin")
    other_admin = CustomUserFactory(role="admin")
    response = _client(admin).patch(
        f"/api/routes/{route.id}/assign/", {"surveyor_id": str(other_admin.id)}
    )
    assert response.status_code == 400
    route.refresh_from_db()
    assert route.surveyor != other_admin


def test_assign_null_unassigns_route(solution_with_route, surveyor):
    _, route, _ = solution_with_route
    admin = CustomUserFactory(role="admin")
    response = _client(admin).patch(
        f"/api/routes/{route.id}/assign/", {"surveyor_id": None}, format="json"
    )
    assert response.status_code == 200
    assert response.data["surveyor"] is None
    route.refresh_from_db()
    assert route.surveyor is None


def test_assign_rejected_when_solution_not_published(solution_with_route):
    solution, route, _ = solution_with_route
    solution.unpublish()
    admin = CustomUserFactory(role="admin")
    target = CustomUserFactory(role="surveyor")
    response = _client(admin).patch(
        f"/api/routes/{route.id}/assign/", {"surveyor_id": str(target.id)}
    )
    assert response.status_code == 400
    route.refresh_from_db()
    assert route.surveyor != target


def test_unassign_allowed_when_solution_not_published(solution_with_route, surveyor):
    solution, route, _ = solution_with_route
    solution.unpublish()
    admin = CustomUserFactory(role="admin")
    response = _client(admin).patch(
        f"/api/routes/{route.id}/assign/", {"surveyor_id": None}, format="json"
    )
    assert response.status_code == 200
    route.refresh_from_db()
    assert route.surveyor is None


def test_my_route_returns_only_callers_routes(solution_with_route, surveyor):
    _, route, _ = solution_with_route
    other = CustomUserFactory(role="surveyor")
    response = _client(other).get("/api/routes/my-route/")
    assert response.status_code == 200
    assert response.data == []

    response = _client(surveyor).get("/api/routes/my-route/")
    assert response.status_code == 200
    assert [r["id"] for r in response.data] == [str(route.id)]


def test_my_route_rejected_for_non_surveyor(solution_with_route):
    admin = CustomUserFactory(role="admin")
    response = _client(admin).get("/api/routes/my-route/")
    assert response.status_code == 403


def test_my_route_excludes_unpublished_solution(solution_with_route, surveyor):
    solution, _, _ = solution_with_route
    solution.unpublish()
    response = _client(surveyor).get("/api/routes/my-route/")
    assert response.status_code == 200
    assert response.data == []
