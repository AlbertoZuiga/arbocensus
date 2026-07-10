import io

import pytest
from apps.optimization.models import OptimizationJob, RoutingConfig, RoutingSolution
from apps.routes.models import Route, RouteStop, TreeObservation
from django.core.files.uploadedfile import SimpleUploadedFile
from PIL import Image
from rest_framework.test import APIClient
from tests.factories import CustomUserFactory

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def media_root(settings, tmp_path):
    settings.MEDIA_ROOT = tmp_path


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


def _photo(name="obs.png"):
    buffer = io.BytesIO()
    Image.new("RGB", (4, 4), color=(0, 128, 0)).save(buffer, format="PNG")
    return SimpleUploadedFile(name, buffer.getvalue(), content_type="image/png")


def test_visit_with_photo_creates_observation(solution_with_route, surveyor):
    _, _, stops = solution_with_route
    response = _client(surveyor).post(
        f"/api/routes/stops/{stops[0].id}/visit/",
        {"photo": _photo(), "notes": "tronco sano"},
        format="multipart",
    )
    assert response.status_code == 200
    observation = TreeObservation.objects.get(tree=stops[0].tree)
    assert observation.status == TreeObservation.Status.ALIVE
    assert observation.route_stop == stops[0]
    assert observation.created_by == surveyor
    assert observation.notes == "tronco sano"
    assert observation.photo.name.startswith("observations/")
    assert observation.photo.storage.exists(observation.photo.name)


def test_visit_with_explicit_status_overrides_default(solution_with_route, surveyor):
    _, _, stops = solution_with_route
    response = _client(surveyor).post(
        f"/api/routes/stops/{stops[0].id}/visit/",
        {"photo": _photo(), "status": "other"},
        format="multipart",
    )
    assert response.status_code == 200
    observation = TreeObservation.objects.get(tree=stops[0].tree)
    assert observation.status == TreeObservation.Status.OTHER


def test_visit_without_photo_creates_observation(solution_with_route, surveyor):
    _, _, stops = solution_with_route
    response = _client(surveyor).post(f"/api/routes/stops/{stops[0].id}/visit/")
    assert response.status_code == 200
    observation = TreeObservation.objects.get(tree=stops[0].tree)
    assert observation.status == TreeObservation.Status.ALIVE
    assert not observation.photo


def test_visit_with_invalid_status_returns_400(solution_with_route, surveyor):
    _, _, stops = solution_with_route
    response = _client(surveyor).post(
        f"/api/routes/stops/{stops[0].id}/visit/",
        {"photo": _photo(), "status": "flying"},
        format="multipart",
    )
    assert response.status_code == 400
    stops[0].refresh_from_db()
    assert stops[0].status == RouteStop.Status.PENDING
    assert TreeObservation.objects.count() == 0


def test_revisit_does_not_duplicate_observation(solution_with_route, surveyor):
    _, _, stops = solution_with_route
    _client(surveyor).post(f"/api/routes/stops/{stops[0].id}/visit/")
    _client(surveyor).post(f"/api/routes/stops/{stops[0].id}/visit/")
    assert TreeObservation.objects.count() == 1


def test_skip_tree_not_found_creates_not_found_observation(
    solution_with_route, surveyor
):
    _, _, stops = solution_with_route
    response = _client(surveyor).post(
        f"/api/routes/stops/{stops[0].id}/skip/",
        {"reason": "Árbol inexistente"},
        format="json",
    )
    assert response.status_code == 200
    observation = TreeObservation.objects.get(tree=stops[0].tree)
    assert observation.status == TreeObservation.Status.NOT_FOUND
    assert observation.route_stop == stops[0]


def test_skip_other_reason_creates_unknown_observation(solution_with_route, surveyor):
    _, _, stops = solution_with_route
    response = _client(surveyor).post(
        f"/api/routes/stops/{stops[0].id}/skip/",
        {"reason": "Acceso bloqueado"},
        format="json",
    )
    assert response.status_code == 200
    observation = TreeObservation.objects.get(tree=stops[0].tree)
    assert observation.status == TreeObservation.Status.UNKNOWN


def test_skip_with_explicit_status_overrides_reason_mapping(
    solution_with_route, surveyor
):
    _, _, stops = solution_with_route
    response = _client(surveyor).post(
        f"/api/routes/stops/{stops[0].id}/skip/",
        {"reason": "Árbol inexistente", "status": "removed", "photo": _photo()},
        format="multipart",
    )
    assert response.status_code == 200
    observation = TreeObservation.objects.get(tree=stops[0].tree)
    assert observation.status == TreeObservation.Status.REMOVED
    assert observation.photo.name.startswith("observations/")


def test_skip_with_invalid_status_returns_400(solution_with_route, surveyor):
    _, _, stops = solution_with_route
    response = _client(surveyor).post(
        f"/api/routes/stops/{stops[0].id}/skip/",
        {"reason": "Árbol inexistente", "status": "flying"},
        format="multipart",
    )
    assert response.status_code == 400
    stops[0].refresh_from_db()
    assert stops[0].status == RouteStop.Status.PENDING
    assert TreeObservation.objects.count() == 0


def test_observations_list_ordered_desc(solution_with_route, surveyor):
    _, _, stops = solution_with_route
    client = _client(surveyor)
    client.post(f"/api/routes/stops/{stops[0].id}/visit/")
    client.post(
        f"/api/routes/stops/{stops[1].id}/skip/",
        {"reason": "Árbol inexistente"},
        format="json",
    )
    extra = TreeObservation.objects.create(
        tree=stops[0].tree, status=TreeObservation.Status.OTHER, created_by=surveyor
    )
    admin = CustomUserFactory(role="admin")
    response = _client(admin).get(
        f"/api/datasets/trees/{stops[0].tree.id}/observations/"
    )
    assert response.status_code == 200
    results = response.data["results"]
    assert [r["id"] for r in results] == [
        str(o.id)
        for o in TreeObservation.objects.filter(tree=stops[0].tree).order_by(
            "-observed_at"
        )
    ]
    assert results[0]["id"] == str(extra.id)
    assert results[0]["created_by_username"] == surveyor.username


def test_observations_list_accessible_to_surveyor(solution_with_route, surveyor):
    _, _, stops = solution_with_route
    client = _client(surveyor)
    client.post(f"/api/routes/stops/{stops[0].id}/visit/")
    response = client.get(f"/api/datasets/trees/{stops[0].tree.id}/observations/")
    assert response.status_code == 200
    assert response.data["count"] == 1


def test_observations_list_rejects_anonymous(solution_with_route):
    _, _, stops = solution_with_route
    response = APIClient().get(f"/api/datasets/trees/{stops[0].tree.id}/observations/")
    assert response.status_code == 401
