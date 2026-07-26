from apps.optimization.management.commands.config_algorithm_sweep import (
    ALGO_AXIS,
    CONFIG_AXIS,
    EXEMPTION_AXIS,
    FACTORIAL_AXIS,
    Command,
)
from apps.optimization.solver import (
    BALANCE_ARM_ACTUAL,
    EXEMPT_LOWER_VEHICLE,
    EXEMPT_UPPER_VEHICLE,
    PenaltyConfig,
)


def route_row(n_trees, duration_sec):
    return {"n_trees": n_trees, "duration_sec": duration_sec}


def test_cell_labels_are_unique():
    labels = [cell.label for cell in CONFIG_AXIS + ALGO_AXIS + FACTORIAL_AXIS]
    assert len(labels) == len(set(labels))


def test_exemption_axis_labels_are_unique_and_control_is_the_production_arm():
    labels = [cell.label for cell in EXEMPTION_AXIS]
    assert len(labels) == len(set(labels))
    control = next(cell for cell in EXEMPTION_AXIS if cell.label == "control")
    assert control.balance_arm == BALANCE_ARM_ACTUAL
    assert control.soft_lower_penalty == PenaltyConfig().soft_lower_penalty
    assert control.soft_upper_target == PenaltyConfig().soft_upper_target
    assert control.arc_coef == 1
    assert control.post_resequence is False


def test_exemption_axis_cells_target_the_declared_vehicles():
    targets = {
        cell.label: PenaltyConfig(balance_arm=cell.balance_arm).exempt_vehicles(36)
        for cell in EXEMPTION_AXIS
    }
    assert targets["control"] == (None, None)
    assert targets["exempt-none"] == (None, None)
    assert targets["exempt-lower"] == (EXEMPT_LOWER_VEHICLE, None)
    assert targets["exempt-upper"] == (None, EXEMPT_UPPER_VEHICLE)
    assert targets["exempt-both"] == (EXEMPT_LOWER_VEHICLE, EXEMPT_UPPER_VEHICLE)
    assert targets["exempt-lower-last"] == (35, None)


def test_exemption_diagnostics_count_exemptions_on_idle_vehicles():
    debug = {
        "exempt_lower_vehicle": 1,
        "exempt_upper_vehicle": 0,
        "active_vehicles": [1, 2, 3],
    }
    assert Command()._exemption_diagnostics([debug]) == {
        "exempt_lower_vehicle": "1",
        "exempt_upper_vehicle": "0",
        "exempt_vehicles_inactive": 1,
    }


def test_exemption_diagnostics_are_blank_without_a_solver_debug():
    assert Command()._exemption_diagnostics([]) == {
        "exempt_lower_vehicle": "",
        "exempt_upper_vehicle": "",
        "exempt_vehicles_inactive": 0,
    }


def test_balance_excluding_shortest_drops_only_the_residual_route():
    assert Command()._balance_excluding_shortest([9000, 8000, 1000]) == 0.889
    assert Command()._balance_excluding_shortest([9000, 8000]) == 1.0


def test_factorial_axis_carries_both_factors_into_the_penalty_config():
    for cell in FACTORIAL_AXIS:
        penalties = PenaltyConfig(
            balance_arm=cell.balance_arm,
            soft_lower_penalty=cell.soft_lower_penalty,
            soft_upper_target=cell.soft_upper_target,
        )
        assert penalties.soft_lower_penalty == cell.soft_lower_penalty
        assert penalties.soft_upper_bound(7200, 10800) == (
            10800 if cell.soft_upper_target == "tmax" else 9000
        )


def test_degenerate_count_is_zero_without_routes():
    assert Command()._degenerate_count([]) == 0


def test_degenerate_count_flags_short_stub_route():
    rows = [route_row(40, 9000), route_row(38, 8600), route_row(1, 120)]
    assert Command()._degenerate_count(rows) == 1


def test_degenerate_count_ignores_stop_count():
    # 8000s is a full-length route: the stop-count condition was dropped, so a route
    # with few stops but a full day of work is not degenerate.
    rows = [route_row(40, 9000), route_row(38, 8600), route_row(4, 8000)]
    assert Command()._degenerate_count(rows) == 0


def test_degenerate_count_flags_uniformly_fragmented_solution():
    # The threshold is absolute, so a solution whose routes are ALL tiny is flagged
    # in full — a threshold relative to its own median would see nothing.
    rows = [route_row(7, 960) for _ in range(6)]
    assert Command()._degenerate_count(rows) == 6
