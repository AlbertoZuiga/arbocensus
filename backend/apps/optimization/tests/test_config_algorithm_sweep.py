from apps.optimization.management.commands.config_algorithm_sweep import (
    ALGO_AXIS,
    CONFIG_AXIS,
    Command,
)


def route_row(n_trees, duration_sec):
    return {"n_trees": n_trees, "duration_sec": duration_sec}


def test_cell_labels_are_unique():
    labels = [cell.label for cell in CONFIG_AXIS + ALGO_AXIS]
    assert len(labels) == len(set(labels))


def test_degenerate_count_is_zero_without_routes():
    assert Command()._degenerate_count([]) == 0


def test_degenerate_count_flags_short_stub_route():
    rows = [route_row(40, 9000), route_row(38, 8600), route_row(1, 120)]
    assert Command()._degenerate_count(rows) == 1


def test_degenerate_count_flags_route_under_stop_threshold():
    # 8000s is well above a quarter of the median, so only the stop count catches it.
    rows = [route_row(40, 9000), route_row(38, 8600), route_row(4, 8000)]
    assert Command()._degenerate_count(rows) == 1


def test_degenerate_count_ignores_uniformly_small_solution():
    # The duration threshold is relative to the solution's own median, so a fully
    # fragmented solution reads as non-degenerate. Documented limitation, not a bug.
    rows = [route_row(7, 960) for _ in range(6)]
    assert Command()._degenerate_count(rows) == 0
