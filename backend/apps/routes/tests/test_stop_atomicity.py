from unittest.mock import patch

import pytest
from apps.optimization.models import OptimizationJob, RoutingConfig, RoutingSolution
from apps.routes.models import Route, RouteStop, TreeObservation
from django.db import connection
from django.test.utils import CaptureQueriesContext
from rest_framework.test import APIClient
from tests.factories import CustomUserFactory

pytestmark = pytest.mark.django_db


@pytest.fixture
def surveyor():
    return CustomUserFactory(role="surveyor")


@pytest.fixture
def stops(make_dataset_with_trees, surveyor):
    dataset, trees = make_dataset_with_trees([(-70.65, -33.45), (-70.66, -33.46)])
    config = RoutingConfig.objects.create(dataset=dataset)
    job = OptimizationJob.objects.create(config=config)
    solution = RoutingSolution.objects.create(job=job, total_routes=1)
    solution.publish()
    route = Route.objects.create(
        solution=solution, route_number=1, total_trees=len(trees), surveyor=surveyor
    )
    return [
        RouteStop.objects.create(route=route, tree=tree, sequence=i)
        for i, tree in enumerate(trees)
    ]


def _client(user):
    client = APIClient()
    client.force_authenticate(user=user)
    return client


def _failing_observation_create():
    return patch.object(
        TreeObservation.objects, "create", side_effect=RuntimeError("storage caído")
    )


def test_visit_rolls_back_stop_when_observation_fails(stops, surveyor):
    client = _client(surveyor)
    url = f"/api/routes/stops/{stops[0].id}/visit/"
    with _failing_observation_create(), pytest.raises(RuntimeError):
        client.post(url, {"notes": "primer intento"}, format="json")
    stops[0].refresh_from_db()
    assert stops[0].status == RouteStop.Status.PENDING
    assert not stops[0].visited
    assert TreeObservation.objects.count() == 0

    response = client.post(url, {"notes": "reintento"}, format="json")
    assert response.status_code == 200
    stops[0].refresh_from_db()
    assert stops[0].status == RouteStop.Status.VISITED
    observation = TreeObservation.objects.get(route_stop=stops[0])
    assert observation.notes == "reintento"


def test_skip_rolls_back_stop_when_observation_fails(stops, surveyor):
    client = _client(surveyor)
    url = f"/api/routes/stops/{stops[0].id}/skip/"
    payload = {"reason": "Acceso bloqueado"}
    with _failing_observation_create(), pytest.raises(RuntimeError):
        client.post(url, payload, format="json")
    stops[0].refresh_from_db()
    assert stops[0].status == RouteStop.Status.PENDING
    assert stops[0].skip_reason == ""
    assert TreeObservation.objects.count() == 0

    response = client.post(url, payload, format="json")
    assert response.status_code == 200
    stops[0].refresh_from_db()
    assert stops[0].status == RouteStop.Status.SKIPPED
    assert TreeObservation.objects.filter(route_stop=stops[0]).count() == 1


def test_repeated_visit_is_idempotent(stops, surveyor):
    client = _client(surveyor)
    url = f"/api/routes/stops/{stops[0].id}/visit/"
    first = client.post(url, {"notes": "sano"}, format="json")
    second = client.post(url, {"notes": "sano"}, format="json")
    assert [first.status_code, second.status_code] == [200, 200]
    assert first.data == second.data
    assert TreeObservation.objects.filter(route_stop=stops[0]).count() == 1
    stops[0].refresh_from_db()
    assert stops[0].status == RouteStop.Status.VISITED


def test_repeated_skip_is_idempotent(stops, surveyor):
    client = _client(surveyor)
    url = f"/api/routes/stops/{stops[0].id}/skip/"
    payload = {"reason": "Acceso bloqueado"}
    first = client.post(url, payload, format="json")
    second = client.post(url, payload, format="json")
    assert [first.status_code, second.status_code] == [200, 200]
    assert TreeObservation.objects.filter(route_stop=stops[0]).count() == 1
    stops[0].refresh_from_db()
    assert stops[0].status == RouteStop.Status.SKIPPED


def test_visit_out_of_order_still_rejected(stops, surveyor):
    response = _client(surveyor).post(
        f"/api/routes/stops/{stops[1].id}/visit/", format="json"
    )
    assert response.status_code == 400
    stops[1].refresh_from_db()
    assert stops[1].status == RouteStop.Status.PENDING
    assert TreeObservation.objects.count() == 0


def test_skip_out_of_order_still_rejected(stops, surveyor):
    response = _client(surveyor).post(
        f"/api/routes/stops/{stops[1].id}/skip/",
        {"reason": "Acceso bloqueado"},
        format="json",
    )
    assert response.status_code == 400
    stops[1].refresh_from_db()
    assert stops[1].status == RouteStop.Status.PENDING
    assert TreeObservation.objects.count() == 0


@pytest.mark.parametrize(
    ("action", "payload"),
    [("visit", {}), ("skip", {"reason": "Acceso bloqueado"})],
)
def test_stop_is_locked_before_the_status_check(stops, surveyor, action, payload):
    with CaptureQueriesContext(connection) as queries:
        response = _client(surveyor).post(
            f"/api/routes/stops/{stops[0].id}/{action}/", payload, format="json"
        )
    assert response.status_code == 200
    locking = [q["sql"] for q in queries.captured_queries if "FOR UPDATE" in q["sql"]]
    assert len(locking) == 1
    assert 'FROM "routes_routestop"' in locking[0]
