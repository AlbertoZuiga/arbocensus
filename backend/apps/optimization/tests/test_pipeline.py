import numpy as np
import pytest
from apps.datasets.models import Dataset, Tree
from apps.optimization.models import OptimizationJob, RoutingConfig, RoutingSolution
from apps.optimization.pipeline import OptimizationPipeline
from apps.routes.models import Route, RouteStop
from django.contrib.gis.geos import Point
from requests_mock import ANY

pytestmark = pytest.mark.django_db

SANTIAGO_LON = -70.65
SANTIAGO_LAT = -33.45


@pytest.fixture(autouse=True)
def fast_solver(monkeypatch):
    monkeypatch.setattr(
        "apps.optimization.pipeline.SOLVER_TIME_LIMIT_SEC", 5, raising=False
    )


def make_job(
    tree_count,
    min_route_time_sec=1800,
    max_route_time_sec=10800,
    service_time_sec=300,
):
    dataset = Dataset.objects.create(name="santiago", total_trees=tree_count)
    for i in range(tree_count):
        Tree.objects.create(
            dataset=dataset,
            location=Point(SANTIAGO_LON + i * 0.001, SANTIAGO_LAT + i * 0.001),
        )
    config = RoutingConfig.objects.create(
        dataset=dataset,
        min_route_time_sec=min_route_time_sec,
        max_route_time_sec=max_route_time_sec,
        service_time_sec=service_time_sec,
    )
    return OptimizationJob.objects.create(config=config)


def osrm_durations(n, travel=60.0):
    matrix = np.full((n, n), travel)
    np.fill_diagonal(matrix, 0.0)
    return {"durations": matrix.tolist()}


def test_pipeline_persists_solution_with_all_trees(requests_mock):
    tree_count = 20
    job = make_job(tree_count)
    requests_mock.get(ANY, json=osrm_durations(tree_count))

    metrics = OptimizationPipeline(job).run()

    solution = job.solutions.get(strategy=RoutingSolution.Strategy.GLOBAL)
    assert solution.total_routes >= 1
    assert metrics["solutions"]["global"]["solution_id"] == str(solution.id)

    stops = RouteStop.objects.filter(route__solution=solution)
    assert stops.count() == tree_count
    visited_tree_ids = set(stops.values_list("tree_id", flat=True))
    assert len(visited_tree_ids) == tree_count


def test_pipeline_single_strategy_persists_one_solution(requests_mock):
    tree_count = 20
    job = make_job(tree_count)
    requests_mock.get(ANY, json=osrm_durations(tree_count))

    OptimizationPipeline(job).run(strategy="global")

    assert job.solutions.count() == 1
    assert job.solutions.get().strategy == RoutingSolution.Strategy.GLOBAL


def test_pipeline_compare_persists_three_solutions(requests_mock):
    tree_count = 20
    job = make_job(tree_count)
    requests_mock.get(ANY, json=osrm_durations(tree_count))

    OptimizationPipeline(job).run()

    assert job.solutions.count() == 3
    assert set(job.solutions.values_list("strategy", flat=True)) == {
        s.value for s in RoutingSolution.Strategy
    }


def test_pipeline_sequences_start_at_one_per_route(requests_mock):
    job = make_job(10)
    requests_mock.get(ANY, json=osrm_durations(10))

    OptimizationPipeline(job).run()

    solution = job.solutions.get(strategy=RoutingSolution.Strategy.GLOBAL)
    for route in Route.objects.filter(solution=solution):
        sequences = list(
            route.stops.order_by("sequence").values_list("sequence", flat=True)
        )
        assert sequences == list(range(1, len(sequences) + 1))


def test_pipeline_cluster_first_persists_all_trees(requests_mock):
    tree_count = 20
    job = make_job(tree_count)
    requests_mock.get(ANY, json=osrm_durations(tree_count))

    OptimizationPipeline(job).run()

    solution = job.solutions.get(strategy=RoutingSolution.Strategy.CLUSTER_FIRST)
    stops = RouteStop.objects.filter(route__solution=solution)
    assert stops.count() == tree_count
    assert len(set(stops.values_list("tree_id", flat=True))) == tree_count


def test_pipeline_persists_spatial_metrics(requests_mock):
    from apps.optimization.route_metrics import aggregate_metrics, routes_from_solution

    tree_count = 20
    job = make_job(tree_count)
    requests_mock.get(ANY, json=osrm_durations(tree_count))

    metrics = OptimizationPipeline(job).run()

    solution = job.solutions.get(strategy=RoutingSolution.Strategy.GLOBAL)
    expected = aggregate_metrics(routes_from_solution(solution))
    assert solution.sum_max_radius_m == expected["sum_max_radius_m"]
    assert solution.interleave_total == expected["interleave_total"]
    assert solution.interleave_per_route == expected["interleave_per_route"]
    assert solution.worst_pair_iou == expected["worst_pair_iou"]

    global_metrics = metrics["solutions"]["global"]
    assert global_metrics["sum_max_radius_m"] == expected["sum_max_radius_m"]
    assert global_metrics["worst_pair_iou"] == expected["worst_pair_iou"]


def test_pipeline_reports_no_dropped_trees_when_all_reachable(requests_mock):
    job = make_job(20)
    requests_mock.get(ANY, json=osrm_durations(20))

    metrics = OptimizationPipeline(job).run()

    assert metrics["dropped_trees"] == []


def test_pipeline_drops_unreachable_tree(requests_mock):
    tree_count = 8
    job = make_job(tree_count)
    durations = osrm_durations(tree_count)
    trees = sorted(Tree.objects.filter(dataset=job.config.dataset), key=lambda t: t.id)
    unreachable_index = 3
    for i in range(tree_count):
        durations["durations"][i][unreachable_index] = 9_999_999.0
        durations["durations"][unreachable_index][i] = 9_999_999.0
    durations["durations"][unreachable_index][unreachable_index] = 0.0
    requests_mock.get(ANY, json=durations)

    metrics = OptimizationPipeline(job).run()

    assert metrics["dropped_trees"] == [str(trees[unreachable_index].id)]

    solution = job.solutions.get(strategy=RoutingSolution.Strategy.GLOBAL)
    stops = RouteStop.objects.filter(route__solution=solution)
    assert stops.count() == tree_count - 1
    assert str(trees[unreachable_index].id) not in {
        str(tid) for tid in stops.values_list("tree_id", flat=True)
    }


def test_pipeline_drops_all_when_time_budget_too_tight(requests_mock):
    tree_count = 5
    job = make_job(
        tree_count,
        min_route_time_sec=200,
        max_route_time_sec=200,
        service_time_sec=300,
    )
    requests_mock.get(ANY, json=osrm_durations(tree_count))

    metrics = OptimizationPipeline(job).run()

    assert len(metrics["dropped_trees"]) == tree_count
