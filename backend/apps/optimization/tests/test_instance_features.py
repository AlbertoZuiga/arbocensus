import math

import numpy as np
import pytest
from apps.optimization.instance_features import (
    geometry_features,
    max_pairwise_distance,
    minimum_feasible_fleet,
    principal_extents,
    project_local,
    regime_features,
)
from apps.optimization.route_metrics import EARTH_RADIUS_M


def degrees_north(metres):
    return math.degrees(metres / EARTH_RADIUS_M)


def test_projection_recovers_a_known_north_south_offset():
    offset = degrees_north(1000)
    projected = project_local([(-33.45, -70.65), (-33.45 + offset, -70.65)])
    assert projected[1][1] - projected[0][1] == pytest.approx(1000, rel=1e-6)
    assert projected[:, 0] == pytest.approx([0.0, 0.0], abs=1e-6)


def test_diameter_of_a_square_is_its_diagonal():
    side = degrees_north(1000)
    points = [
        (-33.45, -70.65),
        (-33.45 + side, -70.65),
        (-33.45, -70.65 + side / math.cos(math.radians(-33.45))),
        (-33.45 + side, -70.65 + side / math.cos(math.radians(-33.45))),
    ]
    assert max_pairwise_distance(project_local(points)) == pytest.approx(
        1000 * math.sqrt(2), rel=1e-3
    )


def test_principal_extents_follow_the_long_axis_of_a_rotated_line():
    t = np.linspace(-500, 500, 21)
    projected = np.column_stack([t * math.cos(0.7), t * math.sin(0.7)])
    major, minor = principal_extents(projected)
    assert major == pytest.approx(1000, rel=1e-6)
    assert minor == pytest.approx(0, abs=1e-6)


def test_density_counts_trees_over_the_bounding_box():
    side = degrees_north(1000)
    east = side / math.cos(math.radians(-33.45))
    points = [
        (-33.45, -70.65),
        (-33.45 + side, -70.65),
        (-33.45, -70.65 + east),
        (-33.45 + side, -70.65 + east),
    ]
    features = geometry_features(points)
    assert features["bbox_area_km2"] == pytest.approx(1.0, rel=1e-3)
    assert features["density_per_km2"] == pytest.approx(4.0, rel=1e-3)
    assert features["elongation"] == pytest.approx(1.0, rel=1e-3)


def test_minimum_feasible_fleet_is_the_first_k_whose_work_fits_tmax():
    # 20 000 s of service needs 2 routes on capacity alone, and at k=2 the forest
    # bound leaves 1 600 s of slack, so k_hat is 2 and not 3.
    msf = {1: 5000.0, 2: 1000.0, 3: 400.0}
    assert minimum_feasible_fleet(msf, 20000, 10800) == 2


def test_minimum_feasible_fleet_rejects_a_table_that_never_fits():
    with pytest.raises(ValueError):
        minimum_feasible_fleet({1: 0.0}, 100000, 10800)


def test_rho_pad_marks_a_floor_the_work_cannot_reach():
    sparse = regime_features({1: 1000.0, 2: 400.0}, 5000, 7200, 10800)
    assert sparse["k_hat"] == 1
    assert sparse["rho_pad"] == pytest.approx(7200 / 6000)
    assert sparse["rho_pad"] > 1

    full = regime_features({1: 1000.0, 2: 400.0}, 9000, 7200, 10800)
    assert full["k_hat"] == 1
    assert full["rho_pad"] == pytest.approx(7200 / 10000)
    assert full["saturation_hat"] == pytest.approx(10000 / 10800)
