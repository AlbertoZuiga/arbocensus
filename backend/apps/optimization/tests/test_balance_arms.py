import numpy as np
import pytest
from apps.optimization.solver import (
    BALANCE_ARM_ACTUAL,
    BALANCE_ARM_SERVICE_FLOOR,
    BALANCE_ARM_TMIN_SCALED,
    BALANCE_ARM_TMIN_SCALED_EXEMPT_LAST,
    BALANCE_ARM_UPPER_TMAX_TMIN9000,
    SOFT_LOWER_PENALTY,
    SOFT_UPPER_PENALTY,
    TIGHT_TMIN_SEC,
    ArbocensusVRPSolver,
    PenaltyConfig,
)

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
