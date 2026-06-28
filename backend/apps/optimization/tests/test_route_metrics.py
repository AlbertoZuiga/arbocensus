import pytest
from apps.optimization.route_metrics import (
    bbox,
    bbox_iou,
    centroid,
    haversine,
    interleave_per_route,
    point_in_bbox,
    sum_max_radius,
    summarize_route,
    total_interleave,
    worst_pair_iou,
)


def test_haversine_one_degree_longitude_at_equator():
    d = haversine((0.0, 0.0), (0.0, 1.0))
    assert d == pytest.approx(111195, rel=0.001)


def test_haversine_symmetric():
    a, b = (-33.45, -70.66), (-33.41, -70.58)
    assert haversine(a, b) == pytest.approx(haversine(b, a))


def test_centroid_and_bbox():
    points = [(0.0, 0.0), (2.0, 4.0)]
    assert centroid(points) == (1.0, 2.0)
    assert bbox(points) == (0.0, 2.0, 0.0, 4.0)


def test_bbox_iou_identical_is_one_and_disjoint_is_zero():
    box = (0.0, 1.0, 0.0, 1.0)
    assert bbox_iou(box, box) == pytest.approx(1.0)
    assert bbox_iou(box, (2.0, 3.0, 2.0, 3.0)) == 0.0


def test_point_in_bbox():
    box = (0.0, 1.0, 0.0, 1.0)
    assert point_in_bbox((0.5, 0.5), box)
    assert not point_in_bbox((2.0, 0.5), box)


def test_summarize_route_radius_ordering():
    r = summarize_route(
        [1, 2, 3], [(-33.45, -70.66), (-33.44, -70.65), (-33.43, -70.64)]
    )
    assert r["max_radius"] >= r["mean_radius"] > 0


def test_interleave_counts_foreign_points_inside_other_bbox():
    inner = summarize_route([1, 2], [(0.4, 0.4), (0.6, 0.6)])
    outer = summarize_route([1, 2], [(0.0, 0.0), (1.0, 1.0)])
    routes = [inner, outer]
    assert total_interleave(routes) == 2
    assert interleave_per_route(routes) == pytest.approx(1.0)
    assert worst_pair_iou(routes) == pytest.approx(
        bbox_iou(inner["bbox"], outer["bbox"])
    )


def test_sum_max_radius_adds_per_route():
    a = summarize_route([1, 2], [(-33.45, -70.66), (-33.44, -70.65)])
    b = summarize_route([1, 2], [(-33.40, -70.60), (-33.41, -70.61)])
    assert sum_max_radius([a, b]) == pytest.approx(a["max_radius"] + b["max_radius"])
