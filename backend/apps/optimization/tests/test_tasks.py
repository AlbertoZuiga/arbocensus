from typing import cast

import pytest
from apps.optimization.models import OptimizationJob, RoutingConfig
from apps.optimization.tasks import run_optimization
from celery import Task

task = cast(Task, run_optimization)

pytestmark = pytest.mark.django_db


def make_job(dataset):
    config = RoutingConfig.objects.create(dataset=dataset)
    return OptimizationJob.objects.create(config=config)


def test_success_sets_running_then_completed(make_dataset_with_trees, monkeypatch):
    dataset, _ = make_dataset_with_trees([(-70.65, -33.45), (-70.66, -33.46)])
    job = make_job(dataset)

    seen_status = {}

    def fake_run(self):
        seen_status["during"] = OptimizationJob.objects.get(id=job.id).status
        return {"total_routes": 1}

    monkeypatch.setattr("apps.optimization.pipeline.OptimizationPipeline.run", fake_run)

    result = task.apply(args=[str(job.id)]).get()

    assert seen_status["during"] == OptimizationJob.Status.RUNNING
    job.refresh_from_db()
    assert job.status == OptimizationJob.Status.COMPLETED
    assert job.metrics == {"total_routes": 1}
    assert result == {"total_routes": 1}


def test_failure_sets_error_before_reraise(make_dataset_with_trees, monkeypatch):
    dataset, _ = make_dataset_with_trees([(-70.65, -33.45), (-70.66, -33.46)])
    job = make_job(dataset)

    def fake_run(self):
        raise ValueError("boom")

    monkeypatch.setattr("apps.optimization.pipeline.OptimizationPipeline.run", fake_run)

    outcome = task.apply(args=[str(job.id)])
    assert outcome.failed()

    job.refresh_from_db()
    assert job.status == OptimizationJob.Status.FAILED
    assert job.error_message == "boom"


def test_task_configured_with_max_retries():
    assert run_optimization.max_retries == 1


def test_task_imports_without_app_registry_error():
    import importlib

    module = importlib.import_module("apps.optimization.tasks")
    assert hasattr(module, "run_optimization")
