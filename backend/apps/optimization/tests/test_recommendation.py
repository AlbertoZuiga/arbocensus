import pytest
from apps.optimization.models import OptimizationJob, RoutingConfig, RoutingSolution
from apps.optimization.recommendation import pick_recommended
from tests.factories import DatasetFactory

pytestmark = pytest.mark.django_db


def make_solution(
    dataset,
    dropped_trees=0,
    degenerate_routes=0,
    balance_score=0.9,
    total_travel_time_sec=1000.0,
    status=OptimizationJob.Status.COMPLETED,
):
    config = RoutingConfig.objects.create(dataset=dataset)
    job = OptimizationJob.objects.create(config=config, status=status)
    return RoutingSolution.objects.create(
        job=job,
        dataset=dataset,
        strategy="global",
        total_routes=1,
        total_travel_time_sec=total_travel_time_sec,
        balance_score=balance_score,
        dropped_trees=dropped_trees,
        degenerate_routes=degenerate_routes,
    )


def test_no_candidates_returns_none():
    dataset = DatasetFactory()
    assert pick_recommended(dataset.id) is None


def test_prefers_zero_drops_over_lower_travel():
    dataset = DatasetFactory()
    with_drops = make_solution(dataset, dropped_trees=1, total_travel_time_sec=100.0)
    no_drops = make_solution(dataset, dropped_trees=0, total_travel_time_sec=500.0)

    assert pick_recommended(dataset.id) == no_drops.id
    assert pick_recommended(dataset.id) != with_drops.id


def test_prefers_zero_degenerate_routes_over_lower_travel():
    dataset = DatasetFactory()
    degenerate = make_solution(
        dataset, degenerate_routes=1, total_travel_time_sec=100.0
    )
    clean = make_solution(dataset, degenerate_routes=0, total_travel_time_sec=500.0)

    assert pick_recommended(dataset.id) == clean.id
    assert pick_recommended(dataset.id) != degenerate.id


def test_prefers_balance_gate_over_lower_travel():
    dataset = DatasetFactory()
    unbalanced = make_solution(dataset, balance_score=0.3, total_travel_time_sec=100.0)
    balanced = make_solution(dataset, balance_score=0.9, total_travel_time_sec=500.0)

    assert pick_recommended(dataset.id) == balanced.id
    assert pick_recommended(dataset.id) != unbalanced.id


def test_picks_least_travel_among_equally_ranked():
    dataset = DatasetFactory()
    make_solution(dataset, total_travel_time_sec=900.0)
    fastest = make_solution(dataset, total_travel_time_sec=100.0)

    assert pick_recommended(dataset.id) == fastest.id


def test_ignores_solutions_from_non_completed_jobs():
    dataset = DatasetFactory()
    make_solution(
        dataset,
        total_travel_time_sec=1.0,
        status=OptimizationJob.Status.RUNNING,
    )
    completed = make_solution(dataset, total_travel_time_sec=1000.0)

    assert pick_recommended(dataset.id) == completed.id
