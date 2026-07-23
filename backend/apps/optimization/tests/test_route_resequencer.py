import pytest
from apps.optimization.route_resequencer import (
    resequence_route,
    route_travel,
    solution_two_opt_gap,
    two_opt_gap,
)


def line_matrix(n):
    return [[float(abs(a - b)) for b in range(n)] for a in range(n)]


def test_route_travel_sums_consecutive_arcs():
    assert route_travel([0, 2, 1, 3], line_matrix(4)) == 5.0
    assert route_travel([2], line_matrix(4)) == 0.0
    assert route_travel([], line_matrix(4)) == 0.0


def test_two_opt_gap_is_zero_for_an_already_optimal_sequence():
    assert two_opt_gap([0, 1, 2, 3], line_matrix(4)) == 0.0


def test_two_opt_gap_is_zero_for_routes_too_short_to_resequence():
    assert two_opt_gap([0, 1], line_matrix(4)) == 0.0
    assert two_opt_gap([1], line_matrix(4)) == 0.0


def test_two_opt_gap_measures_the_detour_of_a_swapped_sequence():
    matrix = line_matrix(4)
    detour = [0, 2, 1, 3]
    assert route_travel(detour, matrix) == 5.0
    assert route_travel(resequence_route(detour, matrix), matrix) == 3.0
    assert two_opt_gap(detour, matrix) == pytest.approx(0.4)


def test_two_opt_gap_is_zero_after_resequencing():
    matrix = line_matrix(6)
    resequenced = resequence_route([0, 3, 1, 4, 2, 5], matrix)
    assert two_opt_gap(resequenced, matrix) == 0.0


def test_solution_gap_weights_routes_by_travel():
    matrix = line_matrix(4)
    # One route wastes 2 of its 5 seconds, the other is optimal at 3.
    assert solution_two_opt_gap([[0, 2, 1, 3], [0, 1, 2, 3]], matrix) == pytest.approx(
        2 / 8
    )


def test_solution_gap_is_zero_without_travel():
    assert solution_two_opt_gap([[1], []], line_matrix(4)) == 0.0
