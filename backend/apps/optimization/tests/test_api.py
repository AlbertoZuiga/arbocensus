from unittest.mock import MagicMock

import pytest
from apps.optimization.models import OptimizationJob, RoutingConfig, RoutingSolution
from rest_framework.test import APIClient
from tests.factories import CustomUserFactory

pytestmark = pytest.mark.django_db


def _client(role="admin"):
    client = APIClient()
    client.force_authenticate(user=CustomUserFactory(role=role))
    return client


def _payload(dataset):
    return {
        "dataset": str(dataset.id),
        "min_route_time_sec": 3600,
        "max_route_time_sec": 7200,
        "service_time_sec": 300,
    }


def test_admin_creates_job_and_triggers_task(make_dataset_with_trees, monkeypatch):
    dataset, _ = make_dataset_with_trees([(-70.65, -33.45)])
    delay = MagicMock()
    monkeypatch.setattr("apps.optimization.views.run_optimization.delay", delay)

    response = _client("admin").post(
        "/api/optimization/jobs/", _payload(dataset), format="json"
    )

    assert response.status_code == 201
    job = OptimizationJob.objects.get(id=response.data["id"])
    config = RoutingConfig.objects.get(dataset=dataset)
    assert job.config == config
    assert config.min_route_time_sec == 3600
    assert response.data["status"] == OptimizationJob.Status.QUEUED
    delay.assert_called_once_with(str(job.id))


def test_create_job_rejected_for_non_admin(make_dataset_with_trees, monkeypatch):
    dataset, _ = make_dataset_with_trees([(-70.65, -33.45)])
    delay = MagicMock()
    monkeypatch.setattr("apps.optimization.views.run_optimization.delay", delay)

    response = _client("surveyor").post(
        "/api/optimization/jobs/", _payload(dataset), format="json"
    )

    assert response.status_code == 403
    assert not OptimizationJob.objects.exists()
    delay.assert_not_called()


def test_create_job_rejects_max_below_min(make_dataset_with_trees, monkeypatch):
    dataset, _ = make_dataset_with_trees([(-70.65, -33.45)])
    monkeypatch.setattr("apps.optimization.views.run_optimization.delay", MagicMock())

    payload = _payload(dataset)
    payload["max_route_time_sec"] = 1800
    response = _client("admin").post("/api/optimization/jobs/", payload, format="json")

    assert response.status_code == 400
    assert not OptimizationJob.objects.exists()


def test_get_job_status_shape(make_dataset_with_trees):
    dataset, _ = make_dataset_with_trees([(-70.65, -33.45)])
    config = RoutingConfig.objects.create(dataset=dataset)
    job = OptimizationJob.objects.create(config=config)
    solution = RoutingSolution.objects.create(
        job=job, strategy="global", total_routes=2
    )

    response = _client("admin").get(f"/api/optimization/jobs/{job.id}/")

    assert response.status_code == 200
    assert set(response.data) == {
        "id",
        "status",
        "error_message",
        "metrics",
        "started_at",
        "completed_at",
        "solution_ids",
    }
    assert response.data["solution_ids"] == {"global": str(solution.id)}


def test_get_job_without_solution_returns_null(make_dataset_with_trees):
    dataset, _ = make_dataset_with_trees([(-70.65, -33.45)])
    config = RoutingConfig.objects.create(dataset=dataset)
    job = OptimizationJob.objects.create(config=config)

    response = _client("admin").get(f"/api/optimization/jobs/{job.id}/")

    assert response.status_code == 200
    assert response.data["solution_ids"] == {}


def test_list_jobs_filtered_by_dataset_newest_first(make_dataset_with_trees):
    dataset, _ = make_dataset_with_trees([(-70.65, -33.45)])
    other_dataset, _ = make_dataset_with_trees([(-70.66, -33.46)])
    config = RoutingConfig.objects.create(dataset=dataset)
    older = OptimizationJob.objects.create(config=config)
    newer = OptimizationJob.objects.create(config=config)
    other_config = RoutingConfig.objects.create(dataset=other_dataset)
    OptimizationJob.objects.create(config=other_config)

    response = _client("admin").get(f"/api/optimization/jobs/?dataset={dataset.id}")

    assert response.status_code == 200
    ids = [job["id"] for job in response.data["results"]]
    assert ids == [str(newer.id), str(older.id)]


def test_list_jobs_rejected_for_non_admin(make_dataset_with_trees):
    dataset, _ = make_dataset_with_trees([(-70.65, -33.45)])

    response = _client("surveyor").get(f"/api/optimization/jobs/?dataset={dataset.id}")

    assert response.status_code == 403


def test_get_solution_shape(make_dataset_with_trees):
    dataset, _ = make_dataset_with_trees([(-70.65, -33.45)])
    config = RoutingConfig.objects.create(dataset=dataset)
    job = OptimizationJob.objects.create(config=config)
    solution = RoutingSolution.objects.create(
        job=job,
        strategy="global",
        total_routes=3,
        total_travel_time_sec=120.5,
        balance_score=0.8,
    )

    response = _client("admin").get(f"/api/optimization/solutions/{solution.id}/")

    assert response.status_code == 200
    assert set(response.data) == {
        "id",
        "strategy",
        "total_routes",
        "total_travel_time_sec",
        "balance_score",
        "sum_max_radius_m",
        "interleave_total",
        "interleave_per_route",
        "worst_pair_iou",
        "generated_at",
        "published_at",
        "job",
        "dataset",
    }
    assert response.data["total_routes"] == 3
    assert response.data["job"] == str(job.id)


def _solution_with_surveyor_route(make_dataset_with_trees, surveyor):
    from apps.routes.models import Route

    dataset, _ = make_dataset_with_trees([(-70.65, -33.45)])
    config = RoutingConfig.objects.create(dataset=dataset)
    job = OptimizationJob.objects.create(config=config)
    solution = RoutingSolution.objects.create(job=job, total_routes=1)
    Route.objects.create(
        solution=solution, route_number=1, total_trees=1, surveyor=surveyor
    )
    return solution


def test_surveyor_gets_own_solution(make_dataset_with_trees):
    surveyor = CustomUserFactory(role="surveyor")
    solution = _solution_with_surveyor_route(make_dataset_with_trees, surveyor)

    client = APIClient()
    client.force_authenticate(user=surveyor)
    response = client.get(f"/api/optimization/solutions/{solution.id}/")

    assert response.status_code == 200
    assert response.data["id"] == str(solution.id)


def test_surveyor_cannot_get_foreign_solution(make_dataset_with_trees):
    owner = CustomUserFactory(role="surveyor")
    solution = _solution_with_surveyor_route(make_dataset_with_trees, owner)
    other = CustomUserFactory(role="surveyor")

    client = APIClient()
    client.force_authenticate(user=other)
    response = client.get(f"/api/optimization/solutions/{solution.id}/")

    assert response.status_code == 404


def test_admin_gets_any_solution(make_dataset_with_trees):
    surveyor = CustomUserFactory(role="surveyor")
    solution = _solution_with_surveyor_route(make_dataset_with_trees, surveyor)

    response = _client("admin").get(f"/api/optimization/solutions/{solution.id}/")

    assert response.status_code == 200
    assert response.data["id"] == str(solution.id)


def test_admin_publishes_solution(make_dataset_with_trees):
    dataset, _ = make_dataset_with_trees([(-70.65, -33.45)])
    config = RoutingConfig.objects.create(dataset=dataset)
    job = OptimizationJob.objects.create(config=config)
    solution = RoutingSolution.objects.create(job=job, total_routes=1)

    response = _client("admin").post(f"/api/optimization/solutions/{solution.id}/publish/")

    assert response.status_code == 200
    assert response.data["published_at"] is not None
    solution.refresh_from_db()
    assert solution.published_at is not None


def test_publishing_new_solution_unpublishes_previous_for_same_dataset(
    make_dataset_with_trees,
):
    dataset, _ = make_dataset_with_trees([(-70.65, -33.45)])
    config = RoutingConfig.objects.create(dataset=dataset)
    older_job = OptimizationJob.objects.create(config=config)
    newer_job = OptimizationJob.objects.create(config=config)
    older = RoutingSolution.objects.create(
        job=older_job, strategy="global", total_routes=1
    )
    newer = RoutingSolution.objects.create(
        job=newer_job, strategy="global", total_routes=2
    )
    older.publish()

    response = _client("admin").post(f"/api/optimization/solutions/{newer.id}/publish/")

    assert response.status_code == 200
    older.refresh_from_db()
    newer.refresh_from_db()
    assert older.published_at is None
    assert newer.published_at is not None


def test_publish_rejected_for_non_admin(make_dataset_with_trees):
    dataset, _ = make_dataset_with_trees([(-70.65, -33.45)])
    config = RoutingConfig.objects.create(dataset=dataset)
    job = OptimizationJob.objects.create(config=config)
    solution = RoutingSolution.objects.create(job=job, total_routes=1)

    response = _client("surveyor").post(f"/api/optimization/solutions/{solution.id}/publish/")

    assert response.status_code == 403
    solution.refresh_from_db()
    assert solution.published_at is None


def test_admin_unpublishes_solution(make_dataset_with_trees):
    dataset, _ = make_dataset_with_trees([(-70.65, -33.45)])
    config = RoutingConfig.objects.create(dataset=dataset)
    job = OptimizationJob.objects.create(config=config)
    solution = RoutingSolution.objects.create(job=job, total_routes=1)
    solution.publish()

    response = _client("admin").post(f"/api/optimization/solutions/{solution.id}/unpublish/")

    assert response.status_code == 200
    assert response.data["published_at"] is None
    solution.refresh_from_db()
    assert solution.published_at is None
