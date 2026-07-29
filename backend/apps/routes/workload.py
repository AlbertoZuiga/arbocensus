from collections import defaultdict

from .models import Route


def route_utilization(route):
    return route.total_estimated_time_sec / route.solution.job.config.max_route_time_sec


def surveyor_workload():
    routes = (
        Route.objects.filter(
            solution__published_at__isnull=False,
            surveyor__isnull=False,
        )
        .select_related("solution__job__config", "surveyor")
        .order_by("solution_id")
    )

    by_solution: dict = defaultdict(list)
    for route in routes:
        by_solution[route.solution.id].append(route)

    accum = {}

    for solution_routes in by_solution.values():
        util_by_surveyor = defaultdict(float)
        surveyor_obj = {}
        for route in solution_routes:
            util = route_utilization(route)
            util_by_surveyor[route.surveyor_id] += util
            surveyor_obj[route.surveyor_id] = route.surveyor

        total_util = sum(util_by_surveyor.values())
        n = len(util_by_surveyor)
        fair_share = total_util / n if n else 0.0

        for sid, util in util_by_surveyor.items():
            if sid not in accum:
                accum[sid] = {
                    "surveyor": surveyor_obj[sid],
                    "total_utilization": 0.0,
                    "census_count": 0,
                    "cumulative_deficit": 0.0,
                }
            accum[sid]["total_utilization"] += util
            accum[sid]["census_count"] += 1
            accum[sid]["cumulative_deficit"] += fair_share - util

    return sorted(
        [
            {
                "surveyor_id": str(sid),
                "username": data["surveyor"].username,
                "total_utilization": round(data["total_utilization"], 4),
                "census_count": data["census_count"],
                "cumulative_deficit": round(data["cumulative_deficit"], 4),
            }
            for sid, data in accum.items()
        ],
        key=lambda x: x["username"],
    )


def suggest_assignment(solution_id, surveyor_ids):
    """
    Greedy: routes by utilization desc, each assigned to candidate with highest
    (cumulative_deficit - already_assigned_in_this_batch). Does not persist.
    Returns (assignments, balance) where assignments is a list of dicts and
    balance maps surveyor_id -> remaining deficit after proposal.
    """
    workload = {
        entry["surveyor_id"]: entry["cumulative_deficit"]
        for entry in surveyor_workload()
    }

    candidate_ids = [str(sid) for sid in surveyor_ids]
    base_deficit: dict[str, float] = {
        sid: float(workload.get(sid, 0.0)) for sid in candidate_ids
    }
    assigned_util: dict[str, float] = defaultdict(float)

    routes = (
        Route.objects.filter(solution_id=solution_id)
        .select_related("solution__job__config")
        .order_by("-total_estimated_time_sec")
    )

    assignments = []
    for route in routes:
        util = route_utilization(route)
        best = max(
            candidate_ids,
            key=lambda sid: base_deficit[sid] - assigned_util[sid],
        )
        assignments.append(
            {
                "route_id": str(route.id),
                "route_number": route.route_number,
                "surveyor_id": best,
                "utilization": round(util, 4),
            }
        )
        assigned_util[best] += util

    balance = {
        sid: round(base_deficit[sid] - assigned_util[sid], 4) for sid in candidate_ids
    }

    return assignments, balance
