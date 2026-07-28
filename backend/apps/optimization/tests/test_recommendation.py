import pytest
from apps.optimization.models import OptimizationJob, RoutingConfig, RoutingSolution
from apps.optimization.recommendation import (
    order_by_criterion,
    pick_recommended,
    pick_recommended_bulk,
)
from tests.factories import DatasetFactory

pytestmark = pytest.mark.django_db


def make_solution(
    dataset,
    config=None,
    dropped_trees=0,
    degenerate_routes=0,
    balance_score=0.9,
    total_travel_time_sec=1000.0,
    status=OptimizationJob.Status.COMPLETED,
):
    config = config or RoutingConfig.objects.create(dataset=dataset)
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
    config = RoutingConfig.objects.create(dataset=dataset)
    with_drops = make_solution(
        dataset, config=config, dropped_trees=1, total_travel_time_sec=100.0
    )
    no_drops = make_solution(
        dataset, config=config, dropped_trees=0, total_travel_time_sec=500.0
    )

    assert pick_recommended(dataset.id) == no_drops.id
    assert pick_recommended(dataset.id) != with_drops.id


def test_prefers_zero_degenerate_routes_over_lower_travel():
    dataset = DatasetFactory()
    config = RoutingConfig.objects.create(dataset=dataset)
    degenerate = make_solution(
        dataset, config=config, degenerate_routes=1, total_travel_time_sec=100.0
    )
    clean = make_solution(
        dataset, config=config, degenerate_routes=0, total_travel_time_sec=500.0
    )

    assert pick_recommended(dataset.id) == clean.id
    assert pick_recommended(dataset.id) != degenerate.id


def test_prefers_balance_gate_over_lower_travel():
    dataset = DatasetFactory()
    config = RoutingConfig.objects.create(dataset=dataset)
    unbalanced = make_solution(
        dataset, config=config, balance_score=0.3, total_travel_time_sec=100.0
    )
    balanced = make_solution(
        dataset, config=config, balance_score=0.9, total_travel_time_sec=500.0
    )

    assert pick_recommended(dataset.id) == balanced.id
    assert pick_recommended(dataset.id) != unbalanced.id


def test_picks_least_travel_among_equally_ranked():
    dataset = DatasetFactory()
    config = RoutingConfig.objects.create(dataset=dataset)
    make_solution(dataset, config=config, total_travel_time_sec=900.0)
    fastest = make_solution(dataset, config=config, total_travel_time_sec=100.0)

    assert pick_recommended(dataset.id) == fastest.id


def test_ties_resolve_to_the_same_solution_as_the_ordered_list():
    # Two strategies converging on the same routes tie on every criterion. The list
    # endpoint and pick_recommended are separate queries, so without a total order
    # they can flag a row that isn't the one listed first.
    dataset = DatasetFactory()
    config = RoutingConfig.objects.create(dataset=dataset)
    make_solution(dataset, config=config)
    make_solution(dataset, config=config)

    first_listed = (
        order_by_criterion(RoutingSolution.objects.filter(dataset=dataset))
        .values_list("id", flat=True)
        .first()
    )
    assert pick_recommended(dataset.id) == first_listed


def test_ignores_solutions_from_non_completed_jobs():
    dataset = DatasetFactory()
    config = RoutingConfig.objects.create(dataset=dataset)
    make_solution(
        dataset,
        config=config,
        total_travel_time_sec=1.0,
        status=OptimizationJob.Status.RUNNING,
    )
    completed = make_solution(dataset, config=config, total_travel_time_sec=1000.0)

    assert pick_recommended(dataset.id) == completed.id


def test_bulk_scopes_each_dataset_to_its_own_latest_config():
    first = DatasetFactory()
    second = DatasetFactory()
    make_solution(first, total_travel_time_sec=1.0)
    first_current = make_solution(first, total_travel_time_sec=900.0)
    second_best = make_solution(second, total_travel_time_sec=50.0)

    assert pick_recommended_bulk([first.id, second.id]) == {
        first.id: first_current.id,
        second.id: second_best.id,
    }


def test_bulk_with_no_datasets_hits_no_query(django_assert_num_queries):
    with django_assert_num_queries(0):
        assert pick_recommended_bulk([]) == {}


def test_bulk_cost_does_not_grow_with_the_number_of_datasets(
    django_assert_num_queries,
):
    datasets = [DatasetFactory() for _ in range(4)]
    for dataset in datasets:
        make_solution(dataset)

    with django_assert_num_queries(2):
        assert len(pick_recommended_bulk([d.id for d in datasets])) == 4


def test_ignores_faster_solution_from_an_older_routing_config():
    # A different RoutingConfig (different max_route_time_sec, service_time_sec,
    # etc.) is not comparable: less travel there doesn't mean a better plan
    # under the config the admin is actually using now.
    dataset = DatasetFactory()
    older_config = RoutingConfig.objects.create(dataset=dataset)
    old_fast = make_solution(dataset, config=older_config, total_travel_time_sec=1.0)

    newer_config = RoutingConfig.objects.create(dataset=dataset)
    current_best = make_solution(
        dataset, config=newer_config, total_travel_time_sec=900.0
    )

    assert pick_recommended(dataset.id) == current_best.id
    assert pick_recommended(dataset.id) != old_fast.id
