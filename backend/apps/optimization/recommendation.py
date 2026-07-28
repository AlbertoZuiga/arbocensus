from apps.optimization.models import OptimizationJob, RoutingSolution
from django.db.models import Case, IntegerField, Q, Value, When

BALANCE_GATE = 0.60


def order_by_criterion(queryset):
    # Strict lexicographic order: 0 drops -> 0 degenerate routes -> balance >= 0.60
    # -> less travel. Unlike sweep_judgement.pick_winner (which can return "no
    # winner" for an offline experiment cell), production always has to rank every
    # candidate, so this orders them instead of gating and stopping.
    return queryset.annotate(
        balance_below_gate=Case(
            When(balance_score__gte=BALANCE_GATE, then=Value(0)),
            default=Value(1),
            output_field=IntegerField(),
        )
    ).order_by(
        "dropped_trees",
        "degenerate_routes",
        "balance_below_gate",
        "total_travel_time_sec",
        # Ties are common (two strategies converging on the same routes). Without a
        # total order the list endpoint and pick_recommended run two separate queries
        # that can disagree on which tied row comes first.
        "id",
    )


def pick_recommended_bulk(dataset_ids):
    # Solutions from different RoutingConfigs (different max_route_time_sec,
    # service_time_sec, etc.) are not comparable to each other: their travel
    # time and route count differ because of the config, not the preset.
    # Rank only within the sweep launched by each dataset's most recent config.
    # Two queries regardless of how many datasets are asked for, so listing
    # solutions across datasets does not turn into a per-row lookup.
    dataset_ids = list(dataset_ids)
    if not dataset_ids:
        return {}
    latest_config_per_dataset = (
        RoutingSolution.objects.filter(
            dataset_id__in=dataset_ids,
            job__status=OptimizationJob.Status.COMPLETED,
        )
        .order_by("dataset_id", "-job__config__created_at")
        .distinct("dataset_id")
        .values_list("dataset_id", "job__config_id")
    )
    latest_sweeps = Q()
    for dataset_id, config_id in latest_config_per_dataset:
        latest_sweeps |= Q(dataset_id=dataset_id, job__config_id=config_id)
    if not latest_sweeps:
        return {}
    recommended = {}
    ranked = order_by_criterion(
        RoutingSolution.objects.filter(
            latest_sweeps, job__status=OptimizationJob.Status.COMPLETED
        )
    ).values_list("dataset_id", "id")
    for dataset_id, solution_id in ranked:
        recommended.setdefault(dataset_id, solution_id)
    return recommended


def pick_recommended(dataset_id):
    return next(iter(pick_recommended_bulk([dataset_id]).values()), None)
