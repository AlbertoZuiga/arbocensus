import numpy as np
import pytest
from apps.optimization.solver import (
    BALANCE_ARM_ACTUAL,
    BALANCE_ARM_NO_FLOOR,
    BALANCE_ARM_NO_FLOOR_LOWFLOOR3600,
    BALANCE_ARM_NO_FLOOR_LOWFLOOR5400,
    BALANCE_ARM_NO_FLOOR_STOPS5,
    BALANCE_ARM_NO_FLOOR_STOPS10,
    BALANCE_ARM_NO_FLOOR_STOPS15,
    BALANCE_ARM_SERVICE_FLOOR,
    BALANCE_ARM_TMIN_SCALED,
    BALANCE_ARM_TMIN_SCALED_EXEMPT_LAST,
    BALANCE_ARM_UPPER_TMAX_TMIN9000,
    SOFT_LOWER_PENALTY,
    SOFT_UPPER_PENALTY,
    STOPS_FLOOR_PENALTY,
    TIGHT_TMIN_SEC,
    ArbocensusVRPSolver,
    PenaltyConfig,
)

TRAVEL_SEC = 60
SERVICE_SEC = 300

BOUNDS_KW = dict(
    min_route_time_sec=7200,
    max_route_time_sec=10800,
    total_service_sec=6000,
    max_vehicles=4,
)


def uniform_matrix(n, travel=60.0):
    m = np.full((n, n), travel)
    np.fill_diagonal(m, 0.0)
    return m


def test_actual_arm_matches_production_bounds():
    lower, upper = PenaltyConfig().vehicle_bounds(is_last=False, **BOUNDS_KW)
    assert lower == (7200, SOFT_LOWER_PENALTY)
    assert upper == (9000, SOFT_UPPER_PENALTY)


def test_upper_tmax_arm_anchors_tmin_and_tmax():
    config = PenaltyConfig(balance_arm=BALANCE_ARM_UPPER_TMAX_TMIN9000)
    lower, upper = config.vehicle_bounds(is_last=False, **BOUNDS_KW)
    assert lower == (TIGHT_TMIN_SEC, SOFT_LOWER_PENALTY)
    assert upper == (10800, SOFT_UPPER_PENALTY)


def test_tmin_scaled_arm_lowers_floor_to_available_service():
    config = PenaltyConfig(balance_arm=BALANCE_ARM_TMIN_SCALED)
    lower, upper = config.vehicle_bounds(is_last=False, **BOUNDS_KW)
    # total_service 6000 / 4 vehicles = 1500 < T_min, so the floor scales down.
    assert lower == (1500, SOFT_LOWER_PENALTY)
    assert upper == ((1500 + 10800) // 2, SOFT_UPPER_PENALTY)


def test_tmin_scaled_arm_never_raises_floor_above_tmin():
    config = PenaltyConfig(balance_arm=BALANCE_ARM_TMIN_SCALED)
    lower, _ = config.vehicle_bounds(
        is_last=False,
        min_route_time_sec=7200,
        max_route_time_sec=10800,
        total_service_sec=999_999,
        max_vehicles=1,
    )
    assert lower == (7200, SOFT_LOWER_PENALTY)


def test_service_floor_arm_drops_lower_bound():
    config = PenaltyConfig(balance_arm=BALANCE_ARM_SERVICE_FLOOR)
    lower, upper = config.vehicle_bounds(is_last=False, **BOUNDS_KW)
    assert lower is None
    assert upper == (9000, SOFT_UPPER_PENALTY)


def test_no_floor_arm_drops_lower_and_pins_upper_at_tmax():
    config = PenaltyConfig(balance_arm=BALANCE_ARM_NO_FLOOR)
    lower, upper = config.vehicle_bounds(is_last=False, **BOUNDS_KW)
    assert lower is None
    assert upper == (10800, SOFT_UPPER_PENALTY)


@pytest.mark.parametrize(
    ("arm", "expected_stops"),
    [
        (BALANCE_ARM_NO_FLOOR_STOPS5, 5),
        (BALANCE_ARM_NO_FLOOR_STOPS10, 10),
        (BALANCE_ARM_NO_FLOOR_STOPS15, 15),
    ],
)
def test_stops_arms_declare_a_stop_floor_and_no_time_floor(arm, expected_stops):
    config = PenaltyConfig(balance_arm=arm)
    lower, upper = config.vehicle_bounds(is_last=False, **BOUNDS_KW)
    assert config.min_stops() == expected_stops
    assert lower is None
    assert upper == (10800, SOFT_UPPER_PENALTY)


@pytest.mark.parametrize(
    ("arm", "expected_floor"),
    [
        (BALANCE_ARM_NO_FLOOR_LOWFLOOR3600, 3600),
        (BALANCE_ARM_NO_FLOOR_LOWFLOOR5400, 5400),
    ],
)
def test_lowfloor_arms_use_an_absolute_time_floor(arm, expected_floor):
    config = PenaltyConfig(balance_arm=arm)
    lower, upper = config.vehicle_bounds(is_last=False, **BOUNDS_KW)
    assert config.min_stops() is None
    assert lower == (expected_floor, SOFT_LOWER_PENALTY)
    assert upper == (10800, SOFT_UPPER_PENALTY)


def test_arms_without_stop_floor_declare_no_min_stops():
    assert PenaltyConfig().min_stops() is None
    assert PenaltyConfig(balance_arm=BALANCE_ARM_NO_FLOOR).min_stops() is None


def test_exempt_last_arm_only_exempts_residual_vehicle():
    config = PenaltyConfig(balance_arm=BALANCE_ARM_TMIN_SCALED_EXEMPT_LAST)
    non_last_lower, _ = config.vehicle_bounds(is_last=False, **BOUNDS_KW)
    last_lower, _ = config.vehicle_bounds(is_last=True, **BOUNDS_KW)
    assert non_last_lower == (1500, SOFT_LOWER_PENALTY)
    assert last_lower is None


def test_invalid_arm_rejected():
    with pytest.raises(ValueError, match="balance_arm"):
        PenaltyConfig(balance_arm="nonsense")


def test_default_arm_is_actual():
    assert PenaltyConfig().balance_arm == BALANCE_ARM_ACTUAL


def test_solver_runs_under_alternate_arm_and_time_span():
    solver = ArbocensusVRPSolver(
        uniform_matrix(8),
        min_route_time_sec=600,
        max_route_time_sec=100_000,
        service_time_sec=300,
        max_vehicles=5,
        time_limit_sec=5,
        time_span_coef=1,
        penalties=PenaltyConfig(balance_arm=BALANCE_ARM_TMIN_SCALED),
    )
    result = solver.solve()
    assert result is not None
    routes, dropped = result
    assert dropped == []
    visited = sorted(node for route in routes for node in route)
    assert visited == list(range(8))


def solve_no_floor(time_global_span_coef):
    solver = ArbocensusVRPSolver(
        uniform_matrix(8, travel=TRAVEL_SEC),
        min_route_time_sec=600,
        max_route_time_sec=100_000,
        service_time_sec=SERVICE_SEC,
        max_vehicles=5,
        time_limit_sec=5,
        time_global_span_coef=time_global_span_coef,
        penalties=PenaltyConfig(balance_arm=BALANCE_ARM_NO_FLOOR),
    )
    result = solver.solve()
    assert result is not None
    return result


def longest_route_duration(routes):
    return max(
        TRAVEL_SEC * (len(route) - 1) + SERVICE_SEC * len(route) for route in routes
    )


def test_solver_runs_under_no_floor_arm_with_time_global_span():
    routes, dropped = solve_no_floor(10)
    assert dropped == []
    visited = sorted(node for route in routes for node in route)
    assert visited == list(range(8))


def solve_arm(arm, time_global_span_coef=0, node_count=12):
    solver = ArbocensusVRPSolver(
        uniform_matrix(node_count, travel=TRAVEL_SEC),
        min_route_time_sec=600,
        max_route_time_sec=100_000,
        service_time_sec=SERVICE_SEC,
        max_vehicles=5,
        time_limit_sec=5,
        time_global_span_coef=time_global_span_coef,
        penalties=PenaltyConfig(balance_arm=arm),
    )
    result = solver.solve_and_debug()
    assert result is not None
    return result


def test_stops_dimension_counts_visited_nodes_and_spares_empty_vehicles():
    routes, dropped, debug = solve_arm(
        BALANCE_ARM_NO_FLOOR_STOPS5, time_global_span_coef=500
    )
    assert dropped == []
    assert sorted(node for route in routes for node in route) == list(range(12))
    cumuls = debug["stops_end_cumuls"]
    assert sorted(c for c in cumuls if c) == sorted(len(r) for r in routes)
    assert cumuls.count(0) == len(cumuls) - len(routes)

    # An unused vehicle sits at cumul 0 yet must not be charged for the shortfall:
    # the objective gap is exactly the shortfall of the ACTIVE routes.
    unfloored_routes, _, unfloored = solve_arm(
        BALANCE_ARM_NO_FLOOR, time_global_span_coef=500
    )
    assert sorted(len(r) for r in unfloored_routes) == sorted(len(r) for r in routes)
    shortfall = sum(max(0, 5 - len(route)) for route in routes)
    gap = debug["objective_ortools"] - unfloored["objective_ortools"]
    assert gap == shortfall * STOPS_FLOOR_PENALTY


def test_stops_floor_lifts_the_smallest_route_under_span_pressure():
    # The global span cost makes splitting into many tiny routes attractive; the
    # stop floor is what pushes the smallest route back up.
    stub_routes, _, _ = solve_arm(BALANCE_ARM_NO_FLOOR, time_global_span_coef=500)
    floored_routes, _, _ = solve_arm(
        BALANCE_ARM_NO_FLOOR_STOPS10, time_global_span_coef=500
    )
    assert min(len(route) for route in floored_routes) > min(
        len(route) for route in stub_routes
    )


def test_time_global_span_shortens_the_longest_route():
    # Without a floor and without the span term, one route carrying everything is
    # cheapest. The global span cost is what makes the longest route expensive.
    unpenalized, _ = solve_no_floor(0)
    penalized, _ = solve_no_floor(1000)
    assert longest_route_duration(penalized) < longest_route_duration(unpenalized)
