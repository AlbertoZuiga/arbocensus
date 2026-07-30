from apps.optimization.config_presets import DEFAULT_CONFIG_PRESET
from apps.optimization.models import OptimizationJob, RoutingSolution
from django.db.models import Case, IntegerField, Q, Value, When

BALANCE_GATE = 0.60
# Two solutions whose travel times differ less than this fraction are treated as
# equivalent; the control (default×spatial_term) wins over an arbitrary id-ranked tie.
TRAVEL_TIE_PCT = 0.03

_CONTROL_PRESET = DEFAULT_CONFIG_PRESET
_CONTROL_STRATEGY = RoutingSolution.Strategy.SPATIAL_TERM.value


def order_by_criterion(queryset):
    # Strict lexicographic order: 0 drops -> 0 degenerate routes -> balance >= 0.60
    # -> less travel -> fewer routes. Unlike sweep_judgement.pick_winner (which can
    # return "no winner" for an offline experiment cell), production always has to rank
    # every candidate, so this orders them instead of gating and stopping.
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
        "total_routes",
        # Ties are common (two strategies converging on the same routes). Without a
        # total order the list endpoint and pick_recommended run two separate queries
        # that can disagree on which tied row comes first.
        "id",
    )


def build_recommendation_context(dataset_ids):
    """
    For each dataset return:
      recommended_id           — solution to show as recommended
      recommended_travel_sec   — its travel time
      sweep_config_id          — the RoutingConfig the ranking was scoped to

    Two queries regardless of how many datasets. The tie rule: if the control
    (default×spatial_term) clears the same gates as the strict-order winner and its
    travel is within TRAVEL_TIE_PCT, the control wins instead of an arbitrary
    id-ranked tiebreak between two near-identical solutions. The gate check is what
    keeps the rule from overriding the lexicographic criterion: a control that drops
    trees or leaves degenerate routes never wins on travel alone.
    """
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

    rows = list(
        order_by_criterion(
            RoutingSolution.objects.filter(
                latest_sweeps, job__status=OptimizationJob.Status.COMPLETED
            )
        ).values_list(
            "dataset_id",
            "id",
            "total_travel_time_sec",
            "job__config_preset",
            "strategy",
            "job__config_id",
            "dropped_trees",
            "degenerate_routes",
            "balance_below_gate",
        )
    )

    travel_by_id = {row[1]: row[2] for row in rows}

    # First occurrence per dataset (best by criterion) is the strict winner.
    strict_winners = {}  # dataset_id → (sol_id, travel, gates)
    controls = {}  # dataset_id → (sol_id, travel, gates)
    sweep_config_ids = {}  # dataset_id → config_id
    for (
        dataset_id,
        sol_id,
        travel,
        preset,
        strategy,
        config_id,
        drops,
        degens,
        below_gate,
    ) in rows:
        gates = (drops, degens, below_gate)
        if dataset_id not in strict_winners:
            strict_winners[dataset_id] = (sol_id, travel, gates)
            sweep_config_ids[dataset_id] = config_id
        if (
            dataset_id not in controls
            and preset == _CONTROL_PRESET
            and strategy == _CONTROL_STRATEGY
        ):
            controls[dataset_id] = (sol_id, travel, gates)

    result = {}
    for dataset_id, (winner_id, winner_travel, winner_gates) in strict_winners.items():
        ctrl = controls.get(dataset_id)
        recommended_id = winner_id
        if ctrl is not None:
            ctrl_id, ctrl_travel, ctrl_gates = ctrl
            # Within the tie margin, prefer the stable reference point over an
            # id-ordered winner that may vary between sweeps.
            if (
                ctrl_gates == winner_gates
                and ctrl_travel > 0
                and abs(winner_travel - ctrl_travel) / ctrl_travel < TRAVEL_TIE_PCT
            ):
                recommended_id = ctrl_id
        result[dataset_id] = {
            "recommended_id": recommended_id,
            "recommended_travel_sec": travel_by_id.get(recommended_id),
            "sweep_config_id": sweep_config_ids[dataset_id],
        }
    return result


def pick_recommended_bulk(dataset_ids):
    # Solutions from different RoutingConfigs (different max_route_time_sec,
    # service_time_sec, etc.) are not comparable to each other: their travel
    # time and route count differ because of the config, not the preset.
    # Rank only within the sweep launched by each dataset's most recent config.
    # Two queries regardless of how many datasets are asked for, so listing
    # solutions across datasets does not turn into a per-row lookup.
    ctx = build_recommendation_context(dataset_ids)
    return {did: c["recommended_id"] for did, c in ctx.items()}


def pick_recommended(dataset_id):
    return next(iter(pick_recommended_bulk([dataset_id]).values()), None)
