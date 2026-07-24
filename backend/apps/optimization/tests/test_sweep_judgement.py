from apps.optimization.sweep_judgement import passes_gates, pick_winner, summarize_cell


def rows(relleno, road, travel, balance=0.85, drops=0, degenerate=0):
    return [
        {
            "relleno_msf_sec": value,
            "crossings_road": road,
            "travel_sec": travel,
            "balance": balance,
            "drops": drops,
            "degenerate_routes": degenerate,
        }
        for value in relleno
    ]


def summarize(**cells):
    return {label: summarize_cell(value) for label, value in cells.items()}


def test_summary_reports_mean_sigma_and_worst_seed():
    summary = summarize_cell(rows([100, 200, 300], 5, 1000, degenerate=1))
    assert summary["relleno_msf_sec"] == 200
    assert summary["relleno_msf_sec_sigma"] > 0
    assert summary["degenerate_routes_max"] == 1
    assert summary["seeds"] == 3


def test_gates_reject_drops_degeneracy_and_thin_balance():
    assert passes_gates(summarize_cell(rows([100] * 3, 5, 1000)))
    assert not passes_gates(summarize_cell(rows([100] * 3, 5, 1000, drops=1)))
    assert not passes_gates(summarize_cell(rows([100] * 3, 5, 1000, degenerate=1)))
    assert not passes_gates(summarize_cell(rows([100] * 3, 5, 1000, balance=0.59)))


def test_a_clear_padding_drop_wins_the_instance():
    winner, survivors = pick_winner(
        summarize(
            control=rows([1000, 1000, 1000], 10, 50000),
            arm=rows([100, 100, 100], 10, 50000),
        ),
        "control",
    )
    assert winner == "arm"
    assert survivors == ["arm"]


def test_a_gap_inside_the_seed_sigma_is_not_a_difference():
    winner, _ = pick_winner(
        summarize(
            control=rows([900, 1000, 1100], 10, 50000),
            arm=rows([880, 980, 1080], 10, 50000),
        ),
        "control",
    )
    assert winner == "control"


def test_road_crossings_break_a_padding_tie_before_travel():
    winner, _ = pick_winner(
        summarize(
            control=rows([1000] * 3, 10, 50000),
            arm=rows([1000] * 3, 4, 60000),
        ),
        "control",
    )
    assert winner == "arm"


def test_a_gated_out_cell_never_wins_however_good_its_metrics():
    winner, survivors = pick_winner(
        summarize(
            control=rows([1000] * 3, 10, 50000),
            arm=rows([0] * 3, 1, 40000, degenerate=1),
        ),
        "control",
    )
    assert winner == "control"
    assert survivors == ["control"]


def test_no_cell_passing_the_gates_leaves_the_instance_without_a_winner():
    winner, survivors = pick_winner(
        summarize(control=rows([1000] * 3, 10, 50000, drops=2)), "control"
    )
    assert winner is None
    assert survivors == []
