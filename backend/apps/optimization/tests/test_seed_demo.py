import numpy as np
import pytest
from apps.datasets.models import Dataset
from apps.optimization.management.commands.seed_demo import PROFILES
from apps.optimization.models import OptimizationJob, RoutingSolution
from apps.routes.models import Route, RouteStop
from django.core.management import call_command
from requests_mock import ANY

pytestmark = pytest.mark.django_db

MEDIUM_TREES = PROFILES["medium"]


@pytest.fixture(autouse=True)
def fast_solver(monkeypatch):
    monkeypatch.setattr("apps.optimization.pipeline.SOLVER_TIME_LIMIT_SEC", 2)


def mock_osrm(requests_mock, n):
    matrix = np.full((n, n), 60.0)
    np.fill_diagonal(matrix, 0.0)
    requests_mock.get(ANY, json={"durations": matrix.tolist()})


def test_seed_demo_medium_profile_persists_routed_solution(
    tmp_path, requests_mock, settings
):
    settings.EXPERIMENTS_DIR = tmp_path / "experiments"
    mock_osrm(requests_mock, MEDIUM_TREES)

    call_command("seed_demo", profile="medium")

    dataset = Dataset.objects.get()
    assert dataset.total_trees == MEDIUM_TREES

    job = OptimizationJob.objects.get()
    assert job.status == OptimizationJob.Status.COMPLETED
    assert job.metrics["solutions"][job.strategy]["solution_id"]
    assert job.metrics["dropped_trees"] == []

    solution = RoutingSolution.objects.get(job=job)
    assert solution.strategy == job.strategy
    assert solution.total_routes >= 1

    routes = Route.objects.filter(solution=solution)
    assert routes.count() == solution.total_routes
    assert RouteStop.objects.filter(route__in=routes).count() == MEDIUM_TREES
