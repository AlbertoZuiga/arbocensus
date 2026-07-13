import csv
import json
from io import StringIO

import numpy as np
import pytest
from apps.datasets.models import Dataset, Tree
from apps.optimization.pipeline import OptimizationPipeline
from apps.optimization.route_audit import (
    AUDIT_COLUMNS,
    SUMMARY_LABEL,
    audit_route,
    routes_geojson,
    self_crossings,
    summarize_audit,
    tmin_gap_coverage,
    worst_overlap_pair,
)
from apps.optimization.solver import PenaltyConfig
from django.contrib.gis.geos import Point
from django.core.management import CommandError, call_command
from requests_mock import ANY

pytestmark = pytest.mark.django_db

SANTIAGO_LON = -70.65
SANTIAGO_LAT = -33.45


@pytest.fixture
def real_dataset():
    dataset = Dataset.objects.create(name="audit", total_trees=6)
    for i in range(6):
        Tree.objects.create(
            dataset=dataset,
            location=Point(SANTIAGO_LON + i * 0.001, SANTIAGO_LAT + i * 0.001),
        )
    return dataset


def mock_osrm(requests_mock, n):
    matrix = np.full((n, n), 60.0)
    np.fill_diagonal(matrix, 0.0)
    requests_mock.get(ANY, json={"durations": matrix.tolist()})


def run_audit(tmp_path, dataset, **kwargs):
    csv_path = tmp_path / "audit.csv"
    geojson_path = tmp_path / "audit.geojson"
    out = StringIO()
    call_command(
        "route_audit",
        dataset=str(dataset.id),
        service_time=300,
        t_min=600,
        t_max=900,
        time_limit=1,
        csv=str(csv_path),
        geojson=str(geojson_path),
        stdout=out,
        **kwargs,
    )
    with csv_path.open() as handle:
        rows = list(csv.DictReader(handle))
    return rows, json.loads(geojson_path.read_text()), out.getvalue()


def test_audit_route_metrics():
    points = [(SANTIAGO_LAT, SANTIAGO_LON)] * 4
    row = audit_route(
        1,
        points,
        duration_sec=4800,
        travel_sec=1200,
        min_route_time_sec=7200,
        max_route_time_sec=10800,
    )

    assert row["n_trees"] == 4
    assert row["service_total_sec"] == 3600
    assert row["travel_sec"] == 1200
    assert row["walk_ratio"] == pytest.approx(0.25)
    assert row["shortfall_sec"] == 2400
    assert row["saturation"] == pytest.approx(0.444, abs=0.001)


def test_audit_route_without_shortfall_when_over_t_min():
    row = audit_route(
        1,
        [(SANTIAGO_LAT, SANTIAGO_LON)] * 2,
        duration_sec=8000,
        travel_sec=800,
        min_route_time_sec=7200,
        max_route_time_sec=10800,
    )

    assert row["shortfall_sec"] == 0
    assert row["saturation"] == pytest.approx(0.741, abs=0.001)


def test_self_crossings_detects_bowtie_and_ignores_monotone_path():
    bowtie = [
        (-33.450, -70.650),
        (-33.440, -70.640),
        (-33.450, -70.640),
        (-33.440, -70.650),
    ]
    monotone = [
        (-33.450, -70.650),
        (-33.449, -70.649),
        (-33.448, -70.648),
        (-33.447, -70.647),
    ]

    assert self_crossings(bowtie) == 1
    assert self_crossings(monotone) == 0
    assert self_crossings(bowtie[:3]) == 0


def test_self_crossings_ignores_segments_touching_at_a_shared_stop():
    revisited_stop = [
        (-33.450, -70.650),
        (-33.450, -70.640),
        (-33.445, -70.645),
        (-33.450, -70.650),
        (-33.455, -70.655),
    ]

    assert self_crossings(revisited_stop) == 0


def test_routes_geojson_skips_linestring_for_single_stop_route():
    audited = [
        {
            "row": {"route": 1, "n_trees": 1},
            "points": [(SANTIAGO_LAT, SANTIAGO_LON)],
            "stops": [{"sequence": 1, "tree_id": "t1"}],
        }
    ]

    collection = routes_geojson(audited)

    geometries = [f["geometry"]["type"] for f in collection["features"]]
    assert geometries == ["Point"]


def test_summarize_audit_sums_times_and_means_saturation():
    audited = [
        {
            "row": {
                "route": 1,
                "n_trees": 2,
                "duration_sec": 6000,
                "service_total_sec": 3000,
                "travel_sec": 3000,
                "walk_ratio": 0.5,
                "shortfall_sec": 1200,
                "saturation": 0.556,
                "self_crossings": 1,
            }
        },
        {
            "row": {
                "route": 2,
                "n_trees": 4,
                "duration_sec": 10000,
                "service_total_sec": 9000,
                "travel_sec": 1000,
                "walk_ratio": 0.1,
                "shortfall_sec": 0,
                "saturation": 0.926,
                "self_crossings": 0,
            }
        },
    ]

    summary = summarize_audit(audited)

    assert summary["route"] == SUMMARY_LABEL
    assert summary["n_trees"] == 6
    assert summary["duration_sec"] == 16000
    assert summary["service_total_sec"] == 12000
    assert summary["travel_sec"] == 4000
    assert summary["walk_ratio"] == pytest.approx(0.25)
    assert summary["shortfall_sec"] == 1200
    assert summary["saturation"] == pytest.approx(0.741, abs=0.001)
    assert summary["self_crossings"] == 1


def test_worst_overlap_pair_picks_highest_bbox_iou():
    def entry(route, points):
        return {"row": {"route": route}, "points": points}

    a = entry(1, [(0.0, 0.0), (1.0, 1.0)])
    b = entry(2, [(0.0, 0.0), (0.9, 0.9)])
    c = entry(3, [(5.0, 5.0), (6.0, 6.0)])

    pair = worst_overlap_pair([a, b, c])

    assert pair is not None
    first, second, iou = pair
    assert {first["row"]["route"], second["row"]["route"]} == {1, 2}
    assert iou == pytest.approx(0.81, abs=0.01)
    assert worst_overlap_pair([a]) is None


def test_route_audit_writes_per_route_csv_and_geojson(
    tmp_path, requests_mock, real_dataset, settings
):
    settings.EXPERIMENTS_DIR = tmp_path / "experiments"
    mock_osrm(requests_mock, 6)
    worst_pair_path = tmp_path / "worst-pair.geojson"

    rows, geojson, output = run_audit(
        tmp_path,
        real_dataset,
        strategy="spatial_term",
        worst_pair_geojson=str(worst_pair_path),
    )

    assert set(rows[0]) == set(AUDIT_COLUMNS)
    assert rows[-1]["route"] == SUMMARY_LABEL

    route_rows = rows[:-1]
    assert len(route_rows) >= 2
    assert sum(int(row["n_trees"]) for row in route_rows) == 6
    for row in rows:
        assert 0.0 <= float(row["walk_ratio"]) <= 1.0
        assert int(row["duration_sec"]) == int(row["service_total_sec"]) + int(
            row["travel_sec"]
        )

    lines = [f for f in geojson["features"] if f["geometry"]["type"] == "LineString"]
    stops = [f for f in geojson["features"] if f["geometry"]["type"] == "Point"]
    assert geojson["type"] == "FeatureCollection"
    assert len(lines) == len(route_rows)
    assert len(stops) == 6
    assert {stop["properties"]["sequence"] for stop in stops} >= {1}
    lon, lat = stops[0]["geometry"]["coordinates"]
    assert lon == pytest.approx(SANTIAGO_LON, abs=0.01)
    assert lat == pytest.approx(SANTIAGO_LAT, abs=0.01)

    worst_pair = json.loads(worst_pair_path.read_text())
    worst_lines = [
        f for f in worst_pair["features"] if f["geometry"]["type"] == "LineString"
    ]
    assert len(worst_lines) == 2
    assert "walk_ratio aggregate" in output


def test_route_audit_rejects_t_min_over_t_max(tmp_path, real_dataset):
    with pytest.raises(CommandError, match="--t-min must not exceed --t-max"):
        call_command(
            "route_audit",
            dataset=str(real_dataset.id),
            t_min=10800,
            t_max=7200,
            csv=str(tmp_path / "x.csv"),
        )


def test_route_audit_rejects_missing_dataset(tmp_path):
    with pytest.raises(CommandError, match="not found"):
        call_command("route_audit", dataset="not-a-uuid", csv=str(tmp_path / "x.csv"))


def test_tmin_gap_coverage_only_counts_routes_short_on_service():
    rows = [
        {"service_total_sec": 2_100, "travel_sec": 5_215},
        {"service_total_sec": 8_000, "travel_sec": 1_000},
    ]

    assert tmin_gap_coverage(rows, min_route_time_sec=7_200) == [1.023]


def capture_penalties(monkeypatch):
    captured = []
    real_run = OptimizationPipeline.run

    def spy(self, **kwargs):
        captured.append(kwargs["penalties"])
        return real_run(self, **kwargs)

    monkeypatch.setattr(OptimizationPipeline, "run", spy)
    return captured


def test_route_audit_defaults_keep_the_production_penalties(
    tmp_path, real_dataset, requests_mock, monkeypatch
):
    mock_osrm(requests_mock, 6)
    captured = capture_penalties(monkeypatch)

    _, _, output = run_audit(tmp_path, real_dataset)

    assert captured == [PenaltyConfig()]
    assert "soft_lower_penalty=10000" in output
    assert "soft_upper_target=midpoint" in output


def test_route_audit_forwards_penalty_overrides(
    tmp_path, real_dataset, requests_mock, monkeypatch
):
    mock_osrm(requests_mock, 6)
    captured = capture_penalties(monkeypatch)

    run_audit(
        tmp_path,
        real_dataset,
        soft_lower_penalty=100,
        soft_upper_target="tmax",
        soft_upper_penalty=0,
    )

    assert captured == [
        PenaltyConfig(
            soft_lower_penalty=100, soft_upper_penalty=0, soft_upper_target="tmax"
        )
    ]
