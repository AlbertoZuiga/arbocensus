from apps.optimization.models import OptimizationJob, RoutingSolution

BALANCE_GATE = 0.60


def _sort_key(solution):
    # Strict lexicographic order: 0 drops -> 0 degenerate routes -> balance >= 0.60
    # -> less travel. Unlike sweep_judgement.pick_winner (which can return "no
    # winner" for an offline experiment cell), production always has to point at
    # one row, so this orders every candidate instead of gating and stopping.
    return (
        solution.dropped_trees,
        solution.degenerate_routes,
        0 if solution.balance_score >= BALANCE_GATE else 1,
        solution.total_travel_time_sec,
    )


def pick_recommended(dataset_id):
    candidates = list(
        RoutingSolution.objects.filter(
            dataset_id=dataset_id,
            job__status=OptimizationJob.Status.COMPLETED,
        )
    )
    if not candidates:
        return None
    return min(candidates, key=_sort_key).id
