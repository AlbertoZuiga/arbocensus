import numpy as np
import pytest
from apps.datasets.models import Dataset, Tree
from apps.optimization.models import OptimizationJob, RoutingConfig, RoutingSolution
from apps.optimization.pipeline import OptimizationPipeline
from apps.optimization.profiling import PHASE_SCHEMA
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


def make_job(tree_count):
    dataset = Dataset.objects.create(name="santiago", total_trees=tree_count)
    for i in range(tree_count):
        Tree.objects.create(
            dataset=dataset,
            location=Point(SANTIAGO_LON + i * 0.001, SANTIAGO_LAT + i * 0.001),
        )
    config = RoutingConfig.objects.create(dataset=dataset)
    return OptimizationJob.objects.create(config=config)


def osrm_durations(n, travel=60.0):
    matrix = np.full((n, n), travel)
    np.fill_diagonal(matrix, 0.0)
    return {"durations": matrix.tolist()}


def timing_key_shape(timing):
    return {
        group: sorted(values) if isinstance(values, dict) else None
        for group, values in timing.items()
    }


def test_timing_has_all_phase_keys_and_sums_to_pipeline_total(requests_mock):
    tree_count = 15
    job = make_job(tree_count)
    requests_mock.get(ANY, json=osrm_durations(tree_count))

    OptimizationPipeline(job).run(strategy="global")

    solution = job.solutions.get(strategy=RoutingSolution.Strategy.GLOBAL)
    timing = solution.timing

    assert set(timing) == set(PHASE_SCHEMA) | {"pipeline_total"}
    for group, keys in PHASE_SCHEMA.items():
        assert set(timing[group]) == set(keys)

    phase_sum = sum(timing[group]["total"] for group in PHASE_SCHEMA)
    assert timing["pipeline_total"] == pytest.approx(phase_sum)


def test_timing_keys_stable_across_runs_with_same_input(requests_mock):
    tree_count = 12

    def run_once():
        job = make_job(tree_count)
        requests_mock.get(ANY, json=osrm_durations(tree_count))
        OptimizationPipeline(job).run(strategy="global")
        return job.solutions.get(strategy=RoutingSolution.Strategy.GLOBAL).timing

    first = run_once()
    second = run_once()

    assert timing_key_shape(first) == timing_key_shape(second)


def test_cost_matrix_timing_shared_across_strategies(requests_mock):
    tree_count = 12
    job = make_job(tree_count)
    requests_mock.get(ANY, json=osrm_durations(tree_count))

    OptimizationPipeline(job).run()

    solutions = list(job.solutions.all())
    assert len(solutions) == 3
    cost_timings = [solution.timing["cost_matrix"] for solution in solutions]
    assert cost_timings[0] == cost_timings[1] == cost_timings[2]
    assert cost_timings[0]["osrm_fetch"] > 0
    assert cost_timings[0]["cache_lookup"] >= 0
