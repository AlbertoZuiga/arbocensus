from unittest.mock import MagicMock

import pytest
from apps.optimization.config_presets import CONFIG_PRESETS
from apps.optimization.models import OptimizationJob, RoutingConfig, RoutingSolution
from apps.optimization.recommendation import BALANCE_GATE
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


def test_default_create_produces_4_explicit_jobs(make_dataset_with_trees, monkeypatch):
    dataset, _ = make_dataset_with_trees([(-70.65, -33.45), (-70.66, -33.46)])
    delay = MagicMock()
    monkeypatch.setattr("apps.optimization.views.run_optimization.delay", delay)

    response = _client("admin").post(
        "/api/optimization/jobs/", _payload(dataset), format="json"
    )

    assert response.status_code == 201
    assert len(response.data) == 4
    config = RoutingConfig.objects.get(dataset=dataset)
    assert config.min_route_time_sec == 3600
    jobs = list(OptimizationJob.objects.filter(config=config))
    assert len(jobs) == 4
    strategies = {job.strategy for job in jobs}
    assert OptimizationJob.Strategy.COMPARE not in strategies
    assert OptimizationJob.Strategy.CLUSTER_FIRST not in strategies
    assert all(job.status == OptimizationJob.Status.QUEUED for job in jobs)
    assert delay.call_count == 4


def test_full_comparison_creates_compare_jobs_for_all_presets(
    make_dataset_with_trees, monkeypatch
):
    dataset, _ = make_dataset_with_trees([(-70.65, -33.45), (-70.66, -33.46)])
    delay = MagicMock()
    monkeypatch.setattr("apps.optimization.views.run_optimization.delay", delay)

    payload = {**_payload(dataset), "full_comparison": True}
    response = _client("admin").post("/api/optimization/jobs/", payload, format="json")

    assert response.status_code == 201
    assert len(response.data) == len(CONFIG_PRESETS)
    jobs = list(OptimizationJob.objects.filter(config__dataset=dataset))
    assert {job.config_preset for job in jobs} == set(CONFIG_PRESETS)
    assert all(job.strategy == OptimizationJob.Strategy.COMPARE for job in jobs)
    assert delay.call_count == len(CONFIG_PRESETS)


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
        "config",
        "strategy",
        "config_preset",
        "status",
        "error_message",
        "metrics",
        "created_at",
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
        "config_preset",
        "config_preset_label",
        "total_routes",
        "total_travel_time_sec",
        "total_service_time_sec",
        "total_time_sec",
        "balance_score",
        "balance_below_gate",
        "dropped_trees",
        "dropped_tree_ids",
        "travel_margin_pct",
        "technical_tie",
        "degenerate_routes",
        "sum_max_radius_m",
        "interleave_total",
        "interleave_per_route",
        "worst_pair_iou",
        "timing",
        "generated_at",
        "published_at",
        "recommended",
        "job",
        "dataset",
        "config",
    }
    assert response.data["total_routes"] == 3
    assert response.data["job"] == str(job.id)
    assert response.data["total_service_time_sec"] == 0
    assert response.data["total_time_sec"] == 120.5


def test_solution_exposes_the_backend_balance_gate(make_dataset_with_trees):
    dataset, _ = make_dataset_with_trees([(-70.65, -33.45)])
    config = RoutingConfig.objects.create(dataset=dataset)
    job = OptimizationJob.objects.create(
        config=config, status=OptimizationJob.Status.COMPLETED
    )
    unbalanced = RoutingSolution.objects.create(
        job=job, strategy="global", total_routes=1, balance_score=BALANCE_GATE - 0.01
    )
    balanced = RoutingSolution.objects.create(
        job=job, strategy="spatial_term", total_routes=1, balance_score=BALANCE_GATE
    )

    client = _client("admin")
    assert (
        client.get(f"/api/optimization/solutions/{unbalanced.id}/").data[
            "balance_below_gate"
        ]
        is True
    )
    assert (
        client.get(f"/api/optimization/solutions/{balanced.id}/").data[
            "balance_below_gate"
        ]
        is False
    )


def test_list_solutions_filters_by_dataset_and_flags_recommended(
    make_dataset_with_trees,
):
    dataset, _ = make_dataset_with_trees([(-70.65, -33.45)])
    other_dataset, _ = make_dataset_with_trees([(-70.66, -33.46)])
    config = RoutingConfig.objects.create(dataset=dataset)
    other_config = RoutingConfig.objects.create(dataset=other_dataset)
    job = OptimizationJob.objects.create(
        config=config, status=OptimizationJob.Status.COMPLETED
    )
    other_job = OptimizationJob.objects.create(
        config=other_config, status=OptimizationJob.Status.COMPLETED
    )
    slow = RoutingSolution.objects.create(
        job=job, strategy="global", total_routes=1, total_travel_time_sec=900.0
    )
    fast = RoutingSolution.objects.create(
        job=job,
        strategy="spatial_term",
        total_routes=1,
        total_travel_time_sec=100.0,
    )
    RoutingSolution.objects.create(
        job=other_job,
        strategy="global",
        total_routes=1,
        total_travel_time_sec=1.0,
    )

    response = _client("admin").get(
        "/api/optimization/solutions/", {"dataset": str(dataset.id)}
    )

    assert response.status_code == 200
    ids = {row["id"] for row in response.data["results"]}
    assert ids == {str(slow.id), str(fast.id)}
    recommended = {row["id"]: row["recommended"] for row in response.data["results"]}
    assert recommended[str(fast.id)] is True
    assert recommended[str(slow.id)] is False


def test_list_solutions_ordered_best_first(make_dataset_with_trees):
    dataset, _ = make_dataset_with_trees([(-70.65, -33.45)])
    config = RoutingConfig.objects.create(dataset=dataset)
    job = OptimizationJob.objects.create(
        config=config, status=OptimizationJob.Status.COMPLETED
    )
    with_drops = RoutingSolution.objects.create(
        job=job,
        strategy="global",
        total_routes=1,
        total_travel_time_sec=1.0,
        balance_score=0.9,
        dropped_trees=1,
    )
    slow = RoutingSolution.objects.create(
        job=job,
        strategy="spatial_term",
        total_routes=1,
        total_travel_time_sec=900.0,
        balance_score=0.9,
    )
    fast = RoutingSolution.objects.create(
        job=job,
        strategy="cluster_first",
        total_routes=1,
        total_travel_time_sec=100.0,
        balance_score=0.9,
    )

    response = _client("admin").get(
        "/api/optimization/solutions/", {"dataset": str(dataset.id)}
    )

    assert response.status_code == 200
    ids = [row["id"] for row in response.data["results"]]
    assert ids == [str(fast.id), str(slow.id), str(with_drops.id)]


def test_list_solutions_without_dataset_filter_flags_recommended_per_dataset(
    make_dataset_with_trees,
):
    dataset, _ = make_dataset_with_trees([(-70.65, -33.45)])
    other_dataset, _ = make_dataset_with_trees([(-70.66, -33.46)])
    config = RoutingConfig.objects.create(dataset=dataset)
    other_config = RoutingConfig.objects.create(dataset=other_dataset)
    job = OptimizationJob.objects.create(
        config=config, status=OptimizationJob.Status.COMPLETED
    )
    other_job = OptimizationJob.objects.create(
        config=other_config, status=OptimizationJob.Status.COMPLETED
    )
    slow = RoutingSolution.objects.create(
        job=job, strategy="global", total_routes=1, total_travel_time_sec=900.0
    )
    fast = RoutingSolution.objects.create(
        job=job,
        strategy="spatial_term",
        total_routes=1,
        total_travel_time_sec=100.0,
    )
    other_fast = RoutingSolution.objects.create(
        job=other_job,
        strategy="global",
        total_routes=1,
        total_travel_time_sec=1.0,
    )

    response = _client("admin").get("/api/optimization/solutions/")

    assert response.status_code == 200
    recommended = {row["id"]: row["recommended"] for row in response.data["results"]}
    assert recommended[str(fast.id)] is True
    assert recommended[str(slow.id)] is False
    assert recommended[str(other_fast.id)] is True


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

    response = _client("admin").post(
        f"/api/optimization/solutions/{solution.id}/publish/"
    )

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

    response = _client("surveyor").post(
        f"/api/optimization/solutions/{solution.id}/publish/"
    )

    assert response.status_code == 403
    solution.refresh_from_db()
    assert solution.published_at is None


def test_admin_unpublishes_solution(make_dataset_with_trees):
    dataset, _ = make_dataset_with_trees([(-70.65, -33.45)])
    config = RoutingConfig.objects.create(dataset=dataset)
    job = OptimizationJob.objects.create(config=config)
    solution = RoutingSolution.objects.create(job=job, total_routes=1)
    solution.publish()

    response = _client("admin").post(
        f"/api/optimization/solutions/{solution.id}/unpublish/"
    )

    assert response.status_code == 200
    assert response.data["published_at"] is None
    solution.refresh_from_db()
    assert solution.published_at is None


def test_fleet_estimate_requires_dataset_param():
    response = _client("admin").get("/api/optimization/estimate/")

    assert response.status_code == 400


def test_fleet_estimate_rejects_invalid_dataset_uuid():
    response = _client("admin").get(
        "/api/optimization/estimate/", {"dataset": "not-a-uuid"}
    )

    assert response.status_code == 400


def test_fleet_estimate_excludes_solver_headroom_buffer(
    make_dataset_with_trees, monkeypatch
):
    from apps.datasets.models import DistanceMatrix
    from apps.optimization.cost_matrix import OSRMCostMatrixBuilder

    dataset, trees = make_dataset_with_trees([(-70.65, -33.45), (-70.66, -33.46)])
    builder = OSRMCostMatrixBuilder()
    sorted_trees = sorted(trees, key=lambda tree: tree.id)
    DistanceMatrix.objects.create(
        dataset=dataset,
        source_hash=builder._compute_hash(sorted_trees),
        matrix_data=[[0, 5], [5, 0]],
        dimension=2,
    )
    estimate_max_vehicles = MagicMock(return_value=1)
    monkeypatch.setattr(
        "apps.optimization.pipeline.estimate_max_vehicles", estimate_max_vehicles
    )

    response = _client("admin").get(
        "/api/optimization/estimate/", {"dataset": str(dataset.id)}
    )

    assert response.status_code == 200
    assert estimate_max_vehicles.call_args.kwargs["buffer"] == 0


def test_fleet_estimate_rejects_non_integer_time_params(make_dataset_with_trees):
    dataset, _ = make_dataset_with_trees([(-70.65, -33.45), (-70.66, -33.46)])

    response = _client("admin").get(
        "/api/optimization/estimate/",
        {"dataset": str(dataset.id), "min_route_time_sec": "not-a-number"},
    )

    assert response.status_code == 400


def test_fleet_estimate_uses_query_params_over_defaults(
    make_dataset_with_trees, monkeypatch
):
    from apps.datasets.models import DistanceMatrix
    from apps.optimization.cost_matrix import OSRMCostMatrixBuilder

    dataset, trees = make_dataset_with_trees([(-70.65, -33.45), (-70.66, -33.46)])
    builder = OSRMCostMatrixBuilder()
    sorted_trees = sorted(trees, key=lambda tree: tree.id)
    DistanceMatrix.objects.create(
        dataset=dataset,
        source_hash=builder._compute_hash(sorted_trees),
        matrix_data=[[0, 5], [5, 0]],
        dimension=2,
    )
    estimate_max_vehicles = MagicMock(return_value=1)
    monkeypatch.setattr(
        "apps.optimization.pipeline.estimate_max_vehicles", estimate_max_vehicles
    )

    response = _client("admin").get(
        "/api/optimization/estimate/",
        {
            "dataset": str(dataset.id),
            "min_route_time_sec": "3600",
            "service_time_sec": "600",
        },
    )

    assert response.status_code == 200
    assert estimate_max_vehicles.call_args.args[2] == 3600
    assert estimate_max_vehicles.call_args.args[1] == len(trees) * 600


def test_fleet_estimate_cache_hit_returns_int(make_dataset_with_trees, monkeypatch):
    from apps.datasets.models import DistanceMatrix
    from apps.optimization.cost_matrix import OSRMCostMatrixBuilder

    dataset, trees = make_dataset_with_trees([(-70.65, -33.45), (-70.66, -33.46)])
    builder = OSRMCostMatrixBuilder()
    sorted_trees = sorted(trees, key=lambda tree: tree.id)
    DistanceMatrix.objects.create(
        dataset=dataset,
        source_hash=builder._compute_hash(sorted_trees),
        matrix_data=[[0, 5], [5, 0]],
        dimension=2,
    )
    fetch = MagicMock()
    monkeypatch.setattr(
        "apps.optimization.cost_matrix.OSRMCostMatrixBuilder._fetch_from_osrm", fetch
    )

    response = _client("admin").get(
        "/api/optimization/estimate/", {"dataset": str(dataset.id)}
    )

    assert response.status_code == 200
    assert isinstance(response.data["n_estimated"], int)
    fetch.assert_not_called()


def test_fleet_estimate_cache_miss_returns_null(make_dataset_with_trees, monkeypatch):
    dataset, _ = make_dataset_with_trees([(-70.65, -33.45), (-70.66, -33.46)])
    fetch = MagicMock()
    monkeypatch.setattr(
        "apps.optimization.cost_matrix.OSRMCostMatrixBuilder._fetch_from_osrm", fetch
    )

    response = _client("admin").get(
        "/api/optimization/estimate/", {"dataset": str(dataset.id)}
    )

    assert response.status_code == 200
    assert response.data["n_estimated"] is None
    fetch.assert_not_called()


def test_fleet_estimate_rejected_for_non_admin(make_dataset_with_trees):
    dataset, _ = make_dataset_with_trees([(-70.65, -33.45), (-70.66, -33.46)])

    response = _client("surveyor").get(
        "/api/optimization/estimate/", {"dataset": str(dataset.id)}
    )

    assert response.status_code == 403
