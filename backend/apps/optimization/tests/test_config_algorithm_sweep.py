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
    # 8000s is a full-length route, so only the stop count catches this one.
    rows = [route_row(40, 9000), route_row(38, 8600), route_row(4, 8000)]
    assert Command()._degenerate_count(rows) == 1


def test_degenerate_count_flags_uniformly_fragmented_solution():
    # Both thresholds are absolute, so a solution whose routes are ALL tiny is
    # flagged in full — a threshold relative to its own median would see nothing.
    rows = [route_row(7, 960) for _ in range(6)]
    assert Command()._degenerate_count(rows) == 6
