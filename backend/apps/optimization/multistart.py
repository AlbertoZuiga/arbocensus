import random

from apps.optimization.models import RoutingSolution
from apps.optimization.strategies import build_strategy_solver

BUDGET_PER_START = "per-start"
BUDGET_TOTAL = "total"
BUDGET_MODES = (BUDGET_PER_START, BUDGET_TOTAL)


def start_seeds(seed, starts):
    # The external seed sows the whole SET of starts, so replicates measure the
    # variance of the policy rather than the variance of one start inside it.
    rng = random.Random(seed)
    return [rng.randrange(1, 2**31) for _ in range(starts)]


def start_time_limit_sec(time_limit_sec, starts, budget):
    if budget == BUDGET_TOTAL:
        return max(1, time_limit_sec // starts)
    return time_limit_sec


def solve_multistart(strategy, matrix, *, node_seeds, timer=None, **solver_kwargs):
    if strategy == RoutingSolution.Strategy.CLUSTER_FIRST.value:
        raise ValueError(
            "multistart is undefined for cluster_first: it solves one model per cluster"
        )
    best = None
    for node_seed in node_seeds:
        solver = build_strategy_solver(
            strategy, matrix, node_seed=node_seed, **solver_kwargs
        )
        result = solver.solve_and_debug(timer=timer)
        if result is None:
            continue
        routes, dropped, debug = result
        # Selection is by the solver's own objective, never by a metric under
        # judgement: picking the run with fewest crossings or best balance would
        # select on the acceptance criterion and contaminate the verdict.
        objective = debug["objective_ortools"]
        if best is None or objective < best[0]:
            best = (objective, routes, dropped)
    if best is None:
        return None
    return best[1], best[2]
