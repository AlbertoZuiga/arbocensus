import pytest
from apps.optimization import multistart
from apps.optimization.models import RoutingSolution
from apps.optimization.multistart import (
    BUDGET_PER_START,
    BUDGET_TOTAL,
    solve_multistart,
    start_seeds,
    start_time_limit_sec,
)

SPATIAL = RoutingSolution.Strategy.SPATIAL_TERM.value


class SolverStub:
    def __init__(self, objective_by_seed):
        self.objective_by_seed = objective_by_seed
        self.seeds = []

    def __call__(self, strategy, matrix, *, node_seed, **kwargs):
        self.seeds.append(node_seed)
        objective = self.objective_by_seed[node_seed]
        return _Solved(objective)


class _Solved:
    def __init__(self, objective):
        self.objective = objective

    def solve_and_debug(self, timer=None):
        if self.objective is None:
            return None
        routes = [[self.objective]]
        return routes, [], {"objective_ortools": self.objective}


def test_start_seeds_are_deterministic_and_distinct():
    assert start_seeds(1, 5) == start_seeds(1, 5)
    assert start_seeds(1, 5) != start_seeds(2, 5)
    assert len(set(start_seeds(1, 5))) == 5


def test_start_seeds_of_a_larger_set_extend_the_smaller_one():
    assert start_seeds(3, 5)[:3] == start_seeds(3, 3)


def test_total_budget_splits_the_limit_across_starts():
    assert start_time_limit_sec(120, 5, BUDGET_TOTAL) == 24
    assert start_time_limit_sec(120, 3, BUDGET_TOTAL) == 40


def test_per_start_budget_keeps_the_full_limit():
    assert start_time_limit_sec(120, 5, BUDGET_PER_START) == 120


def test_best_start_is_chosen_by_solver_objective(monkeypatch):
    stub = SolverStub({7: 500, 8: 200, 9: 900})
    monkeypatch.setattr(multistart, "build_strategy_solver", stub)

    solved = solve_multistart(SPATIAL, [[0]], node_seeds=[7, 8, 9])

    assert solved is not None
    routes, dropped = solved
    assert stub.seeds == [7, 8, 9]
    assert routes == [[200]]
    assert dropped == []


def test_infeasible_starts_are_skipped(monkeypatch):
    stub = SolverStub({7: None, 8: 300})
    monkeypatch.setattr(multistart, "build_strategy_solver", stub)

    solved = solve_multistart(SPATIAL, [[0]], node_seeds=[7, 8])

    assert solved is not None
    routes, _ = solved
    assert routes == [[300]]


def test_all_starts_infeasible_returns_none(monkeypatch):
    stub = SolverStub({7: None, 8: None})
    monkeypatch.setattr(multistart, "build_strategy_solver", stub)

    assert solve_multistart(SPATIAL, [[0]], node_seeds=[7, 8]) is None


def test_cluster_first_rejects_multistart():
    with pytest.raises(ValueError):
        solve_multistart(
            RoutingSolution.Strategy.CLUSTER_FIRST.value, [[0]], node_seeds=[1, 2]
        )
