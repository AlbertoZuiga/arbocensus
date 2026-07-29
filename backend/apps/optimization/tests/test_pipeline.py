import numpy as np
import pytest
from apps.datasets.models import Dataset, Tree
from apps.optimization import pipeline
from apps.optimization.models import OptimizationJob, RoutingConfig, RoutingSolution
from apps.optimization.pipeline import OptimizationPipeline
from apps.optimization.solver import PenaltyConfig
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
    config_preset="default",
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
    return OptimizationJob.objects.create(config=config, config_preset=config_preset)


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


def capture_penalties(monkeypatch):
    captured = []
    real_solve = pipeline.solve_by_strategy

    def spy(strategy, matrix, **kwargs):
        captured.append(kwargs["penalties"])
        return real_solve(strategy, matrix, **kwargs)

    monkeypatch.setattr(pipeline, "solve_by_strategy", spy)
    return captured


def test_pipeline_defaults_to_production_penalties(requests_mock, monkeypatch):
    job = make_job(10)
    requests_mock.get(ANY, json=osrm_durations(10))
    captured = capture_penalties(monkeypatch)

    OptimizationPipeline(job).run(strategy="global", time_limit_sec=2)

    assert captured == [PenaltyConfig()]


def test_pipeline_forwards_penalty_overrides(requests_mock, monkeypatch):
    job = make_job(10)
    requests_mock.get(ANY, json=osrm_durations(10))
    captured = capture_penalties(monkeypatch)
    penalties = PenaltyConfig(soft_lower_penalty=0, soft_upper_target="tmax")

    OptimizationPipeline(job).run(
        strategy="global", time_limit_sec=2, penalties=penalties
    )

    assert captured == [penalties]


def test_pipeline_applies_2opt_resequencing(requests_mock, monkeypatch):
    tree_count = 10
    job = make_job(tree_count)
    requests_mock.get(ANY, json=osrm_durations(tree_count))

    called = []
    original_resequence = pipeline.resequence_routes

    def spy_resequence(routes, matrix):
        called.append(True)
        return original_resequence(routes, matrix)

    monkeypatch.setattr(pipeline, "resequence_routes", spy_resequence)

    OptimizationPipeline(job).run(strategy="global", time_limit_sec=2)

    assert len(called) == 1


def test_pipeline_resequencing_preserves_stops_per_route(requests_mock):
    tree_count = 15
    job = make_job(tree_count)
    requests_mock.get(ANY, json=osrm_durations(tree_count))

    OptimizationPipeline(job).run(strategy="global", time_limit_sec=2)

    solution = job.solutions.get(strategy=RoutingSolution.Strategy.GLOBAL)
    total_stops = 0
    for route in Route.objects.filter(solution=solution):
        stops = list(route.stops.order_by("sequence").values_list("tree_id", flat=True))
        total_stops += len(stops)
        assert len(stops) > 0
        assert len(set(stops)) == len(stops)

    assert total_stops == tree_count


def capture_arc_kwargs(monkeypatch):
    captured = []
    real_solve = pipeline.solve_by_strategy

    def spy(strategy, matrix, **kwargs):
        captured.append(
            {"time_span_coef": kwargs["time_span_coef"], "arc_coef": kwargs["arc_coef"]}
        )
        return real_solve(strategy, matrix, **kwargs)

    monkeypatch.setattr(pipeline, "solve_by_strategy", spy)
    return captured


def test_pipeline_applies_default_config_preset(requests_mock, monkeypatch):
    job = make_job(10, config_preset="default")
    requests_mock.get(ANY, json=osrm_durations(10))
    captured = capture_arc_kwargs(monkeypatch)

    OptimizationPipeline(job).run(strategy="global", time_limit_sec=2)

    assert captured == [{"time_span_coef": 0, "arc_coef": 1}]


def test_pipeline_applies_named_config_preset(requests_mock, monkeypatch):
    job = make_job(10, config_preset="arc_linear_30")
    requests_mock.get(ANY, json=osrm_durations(10))
    captured = capture_arc_kwargs(monkeypatch)

    OptimizationPipeline(job).run(strategy="global", time_limit_sec=2)

    assert captured == [{"time_span_coef": 0, "arc_coef": 30}]


def test_pipeline_explicit_kwarg_overrides_config_preset(requests_mock, monkeypatch):
    job = make_job(10, config_preset="arc_linear_30")
    requests_mock.get(ANY, json=osrm_durations(10))
    captured = capture_arc_kwargs(monkeypatch)

    OptimizationPipeline(job).run(strategy="global", time_limit_sec=2, arc_coef=1)

    assert captured == [{"time_span_coef": 0, "arc_coef": 1}]


def test_pipeline_persists_dropped_trees_per_solution(requests_mock):
    tree_count = 8
    job = make_job(tree_count)
    durations = osrm_durations(tree_count)
    unreachable_index = 3
    for i in range(tree_count):
        durations["durations"][i][unreachable_index] = 9_999_999.0
        durations["durations"][unreachable_index][i] = 9_999_999.0
    durations["durations"][unreachable_index][unreachable_index] = 0.0
    requests_mock.get(ANY, json=durations)

    OptimizationPipeline(job).run(strategy="global")

    solution = job.solutions.get(strategy=RoutingSolution.Strategy.GLOBAL)
    assert solution.dropped_trees == 1


def test_pipeline_persists_degenerate_routes(requests_mock):
    tree_count = 2
    job = make_job(
        tree_count,
        min_route_time_sec=20,
        max_route_time_sec=100,
        service_time_sec=1,
    )
    requests_mock.get(ANY, json=osrm_durations(tree_count, travel=1.0))

    OptimizationPipeline(job).run(strategy="global")

    solution = job.solutions.get(strategy=RoutingSolution.Strategy.GLOBAL)
    assert solution.total_routes >= 1
    assert solution.degenerate_routes == solution.total_routes


def test_degenerate_threshold_scales_with_the_configured_minimum(requests_mock):
    # The same handful of seconds of work is a stub under an 8 h shift and a full
    # route under a 4 s one: the threshold is a fraction of min_route_time_sec,
    # not a fixed 30 minutes.
    tree_count = 2
    job = make_job(
        tree_count,
        min_route_time_sec=4,
        max_route_time_sec=100,
        service_time_sec=1,
    )
    requests_mock.get(ANY, json=osrm_durations(tree_count, travel=1.0))

    OptimizationPipeline(job).run(strategy="global")

    solution = job.solutions.get(strategy=RoutingSolution.Strategy.GLOBAL)
    assert solution.total_routes >= 1
    assert solution.degenerate_routes == 0
