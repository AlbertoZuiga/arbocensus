import time
from itertools import combinations

import numpy as np
import pytest
from apps.optimization.route_audit import road_self_crossings, self_crossings
from apps.optimization.strategies import project_equirectangular

SANTIAGO_LON = -70.65
SANTIAGO_LAT = -33.45


def _reference_orientation(a, b, c):
    return (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])


def _reference_segments_cross(first, second):
    p1, p2 = first
    p3, p4 = second
    d1 = _reference_orientation(p3, p4, p1)
    d2 = _reference_orientation(p3, p4, p2)
    d3 = _reference_orientation(p1, p2, p3)
    d4 = _reference_orientation(p1, p2, p4)
    if 0.0 in (d1, d2, d3, d4):
        return False
    return (d1 > 0) != (d2 > 0) and (d3 > 0) != (d4 > 0)


def reference_self_crossings(points):
    """Pre-vectorisation implementation, kept as the equivalence oracle."""
    if len(points) < 4:
        return 0
    projected = [tuple(p) for p in project_equirectangular(points)]
    segments = list(zip(projected[:-1], projected[1:], strict=True))
    return sum(
        1
        for i, j in combinations(range(len(segments)), 2)
        if j > i + 1 and _reference_segments_cross(segments[i], segments[j])
    )


def grid_walk(rng, n, step):
    """Points snapped to a coarse grid, so collinear and repeated stops occur."""
    offsets = rng.integers(-4, 5, size=(n, 2)) * step
    return [
        (SANTIAGO_LAT + float(dlat), SANTIAGO_LON + float(dlon))
        for dlat, dlon in offsets
    ]


@pytest.mark.parametrize("n", [4, 5, 7, 12, 25, 60])
def test_matches_reference_on_random_walks(n):
    rng = np.random.default_rng(n)
    for _ in range(20):
        points = [
            (SANTIAGO_LAT + float(dlat), SANTIAGO_LON + float(dlon))
            for dlat, dlon in rng.normal(0, 0.01, size=(n, 2))
        ]
        assert self_crossings(points) == reference_self_crossings(points)


@pytest.mark.parametrize("n", [4, 6, 10, 20, 40])
def test_matches_reference_on_degenerate_grid_walks(n):
    rng = np.random.default_rng(1000 + n)
    for _ in range(20):
        points = grid_walk(rng, n, 0.002)
        assert self_crossings(points) == reference_self_crossings(points)


def test_matches_reference_on_routes_too_short_to_cross():
    points = [(SANTIAGO_LAT, SANTIAGO_LON), (SANTIAGO_LAT + 0.01, SANTIAGO_LON + 0.01)]
    for size in range(4):
        assert self_crossings(points[:size]) == reference_self_crossings(points[:size])


def test_matches_reference_when_every_stop_is_the_same_point():
    points = [(SANTIAGO_LAT, SANTIAGO_LON)] * 8
    assert self_crossings(points) == reference_self_crossings(points) == 0


def test_matches_reference_on_a_path_that_revisits_a_stop():
    points = [
        (SANTIAGO_LAT, SANTIAGO_LON),
        (SANTIAGO_LAT + 0.01, SANTIAGO_LON),
        (SANTIAGO_LAT + 0.01, SANTIAGO_LON + 0.01),
        (SANTIAGO_LAT, SANTIAGO_LON),
        (SANTIAGO_LAT - 0.01, SANTIAGO_LON + 0.01),
    ]
    assert self_crossings(points) == reference_self_crossings(points) == 0


def test_matches_reference_on_a_collinear_path():
    points = [(SANTIAGO_LAT + 0.001 * i, SANTIAGO_LON) for i in range(10)]
    assert self_crossings(points) == reference_self_crossings(points) == 0


def test_counts_a_bowtie():
    bowtie = [
        (SANTIAGO_LAT, SANTIAGO_LON),
        (SANTIAGO_LAT + 0.01, SANTIAGO_LON + 0.01),
        (SANTIAGO_LAT + 0.01, SANTIAGO_LON),
        (SANTIAGO_LAT, SANTIAGO_LON + 0.01),
    ]
    assert self_crossings(bowtie) == 1


def test_road_crossings_equal_chord_metric_when_the_polyline_is_the_chords():
    # An OSRM polyline of a route with no intermediate street vertices IS the
    # straight chords, expressed [lon, lat]. Fed that degenerate polyline, the road
    # counter must reproduce the chord metric exactly — the equivalence that anchors
    # crossings_road to the existing crossings_chord.
    rng = np.random.default_rng(42)
    for _ in range(30):
        stops = [
            (SANTIAGO_LAT + float(dlat), SANTIAGO_LON + float(dlon))
            for dlat, dlon in rng.normal(0, 0.01, size=(12, 2))
        ]
        polyline = [(lon, lat) for lat, lon in stops]
        assert road_self_crossings(polyline) == self_crossings(stops)


def test_road_crossings_counts_a_bowtie_polyline():
    # Same bowtie as the chord test, but as an OSRM-shaped [lon, lat] polyline.
    bowtie = [
        (SANTIAGO_LON, SANTIAGO_LAT),
        (SANTIAGO_LON + 0.01, SANTIAGO_LAT + 0.01),
        (SANTIAGO_LON, SANTIAGO_LAT + 0.01),
        (SANTIAGO_LON + 0.01, SANTIAGO_LAT),
    ]
    assert road_self_crossings(bowtie) == 1


def test_road_crossings_sees_a_crossing_that_the_chords_hide():
    # Two stops whose straight chord does not cross the route, but whose real street
    # path detours through a loop that does. This is exactly the chord/road mismatch
    # the cycle exists to measure: chords miss it, the polyline catches it.
    stops = [
        (SANTIAGO_LAT, SANTIAGO_LON),
        (SANTIAGO_LAT + 0.02, SANTIAGO_LON + 0.02),
        (SANTIAGO_LAT + 0.02, SANTIAGO_LON),
        (SANTIAGO_LAT + 0.04, SANTIAGO_LON + 0.02),
    ]
    chords = [(lon, lat) for lat, lon in stops]
    assert road_self_crossings(chords) == self_crossings(stops) == 0
    detoured = [
        (SANTIAGO_LON, SANTIAGO_LAT),
        (SANTIAGO_LON + 0.03, SANTIAGO_LAT + 0.01),
        (SANTIAGO_LON + 0.02, SANTIAGO_LAT + 0.02),
        (SANTIAGO_LON, SANTIAGO_LAT + 0.02),
        (SANTIAGO_LON + 0.01, SANTIAGO_LAT + 0.005),
        (SANTIAGO_LON + 0.04, SANTIAGO_LAT + 0.02),
    ]
    assert road_self_crossings(detoured) == 1


def test_road_crossings_zero_on_routes_too_short_to_cross():
    polyline = [(SANTIAGO_LON, SANTIAGO_LAT), (SANTIAGO_LON + 0.01, SANTIAGO_LAT)]
    for size in range(4):
        assert road_self_crossings(polyline[:size]) == 0


def test_handles_a_road_polyline_sized_input():
    # A real street polyline is ~3000 segments per route; the pairwise Python
    # loop this replaced needed hours at that size.
    rng = np.random.default_rng(7)
    steps = rng.normal(0, 0.0004, size=(3001, 2)).cumsum(axis=0)
    points = [
        (SANTIAGO_LAT + float(dlat), SANTIAGO_LON + float(dlon)) for dlat, dlon in steps
    ]
    started = time.perf_counter()
    count = self_crossings(points)
    elapsed = time.perf_counter() - started
    assert count > 0
    assert elapsed < 10.0
