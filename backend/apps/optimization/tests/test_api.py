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
    solution = RoutingSolution.objects.create(job=job, total_routes=2)

    response = _client("admin").get(f"/api/optimization/jobs/{job.id}/")

    assert response.status_code == 200
    assert set(response.data) == {
        "id",
        "status",
        "error_message",
        "metrics",
        "started_at",
        "completed_at",
        "solution_id",
    }
    assert response.data["solution_id"] == solution.id


def test_get_job_without_solution_returns_null(make_dataset_with_trees):
    dataset, _ = make_dataset_with_trees([(-70.65, -33.45)])
    config = RoutingConfig.objects.create(dataset=dataset)
    job = OptimizationJob.objects.create(config=config)

    response = _client("admin").get(f"/api/optimization/jobs/{job.id}/")

    assert response.status_code == 200
    assert response.data["solution_id"] is None


def test_get_solution_shape(make_dataset_with_trees):
    dataset, _ = make_dataset_with_trees([(-70.65, -33.45)])
    config = RoutingConfig.objects.create(dataset=dataset)
    job = OptimizationJob.objects.create(config=config)
    solution = RoutingSolution.objects.create(
        job=job, total_routes=3, total_travel_time_sec=120.5, balance_score=0.8
    )

    response = _client("surveyor").get(f"/api/optimization/solutions/{solution.id}/")

    assert response.status_code == 200
    assert set(response.data) == {
        "id",
        "total_routes",
        "total_travel_time_sec",
        "balance_score",
        "generated_at",
        "job",
    }
    assert response.data["total_routes"] == 3
    assert response.data["job"] == str(job.id)
