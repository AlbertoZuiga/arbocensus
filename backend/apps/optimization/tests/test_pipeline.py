import numpy as np
import pytest
from apps.datasets.models import Dataset, Tree
from apps.optimization.models import OptimizationJob, RoutingConfig
from apps.optimization.pipeline import OptimizationPipeline
from apps.routes.models import Route, RouteStop
from django.contrib.gis.geos import Point
from requests_mock import ANY

pytestmark = pytest.mark.django_db

SANTIAGO_LON = -70.65
SANTIAGO_LAT = -33.45


def make_job(
    tree_count,
    min_route_time_sec=1800,
    max_route_time_sec=10800,
    service_time_sec=300,
    strategy=RoutingConfig.Strategy.GLOBAL,
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
        strategy=strategy,
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

    solution = job.solution
    assert solution.total_routes >= 1
    assert metrics["solution_id"] == str(solution.id)

    stops = RouteStop.objects.filter(route__solution=solution)
    assert stops.count() == tree_count
    visited_tree_ids = set(stops.values_list("tree_id", flat=True))
    assert len(visited_tree_ids) == tree_count


def test_pipeline_sequences_start_at_one_per_route(requests_mock):
    job = make_job(10)
    requests_mock.get(ANY, json=osrm_durations(10))

    OptimizationPipeline(job).run()

    for route in Route.objects.filter(solution=job.solution):
        sequences = list(
            route.stops.order_by("sequence").values_list("sequence", flat=True)
        )
        assert sequences == list(range(1, len(sequences) + 1))


def test_pipeline_cluster_first_persists_all_trees(requests_mock):
    tree_count = 20
    job = make_job(tree_count, strategy=RoutingConfig.Strategy.CLUSTER_FIRST)
    requests_mock.get(ANY, json=osrm_durations(tree_count))

    OptimizationPipeline(job).run()

    stops = RouteStop.objects.filter(route__solution=job.solution)
    assert stops.count() == tree_count
    assert len(set(stops.values_list("tree_id", flat=True))) == tree_count


def test_pipeline_raises_on_infeasible(requests_mock):
    job = make_job(
        5, min_route_time_sec=200, max_route_time_sec=200, service_time_sec=300
    )
    requests_mock.get(ANY, json=osrm_durations(5))

    with pytest.raises(ValueError, match="No feasible solution"):
        OptimizationPipeline(job).run()
