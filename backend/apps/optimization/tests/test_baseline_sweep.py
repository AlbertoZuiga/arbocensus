import csv
from io import StringIO

import numpy as np
import pytest
from apps.datasets.models import Dataset, Tree
from apps.optimization.management.commands.baseline_sweep import CSV_COLUMNS
from apps.optimization.models import RoutingConfig
from django.contrib.gis.geos import Point
from django.core.management import CommandError, call_command
from requests_mock import ANY

pytestmark = pytest.mark.django_db

SANTIAGO_LON = -70.65
SANTIAGO_LAT = -33.45


@pytest.fixture
def real_dataset():
    dataset = Dataset.objects.create(name="real", total_trees=6)
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


def run_sweep(tmp_path, **kwargs):
    csv_path = tmp_path / "sweep.csv"
    out = StringIO()
    call_command(
        "baseline_sweep", csv=str(csv_path), time_limit=1, stdout=out, **kwargs
    )
    with csv_path.open() as handle:
        return list(csv.DictReader(handle)), out.getvalue()


def test_real_dataset_variant_grid(tmp_path, requests_mock, real_dataset, settings):
    settings.EXPERIMENTS_DIR = tmp_path / "experiments"
    mock_osrm(requests_mock, 6)

    rows, _ = run_sweep(
        tmp_path,
        dataset=str(real_dataset.id),
        strategies="global",
        service_time="1,2",
        t_max="2,3",
        seeds=2,
    )

    assert len(rows) == 8
    assert set(rows[0]) == set(CSV_COLUMNS)
    assert {row["target"] for row in rows} == {"real"}
    assert {(row["service_time_min"], row["t_max_h"]) for row in rows} == {
        ("1.0", "2.0"),
        ("1.0", "3.0"),
        ("2.0", "2.0"),
        ("2.0", "3.0"),
    }
    assert all(float(row["pipeline_total"]) > 0 for row in rows)
    assert all(int(row["k"]) >= 1 or int(row["dropped_trees"]) == 6 for row in rows)

    config = RoutingConfig.objects.filter(service_time_sec=60).earliest("created_at")
    assert config.max_route_time_sec in (7200, 10800)
    assert config.min_route_time_sec <= config.max_route_time_sec


def test_synthetic_default_matches_previous_behavior(tmp_path, requests_mock, settings):
    settings.EXPERIMENTS_DIR = tmp_path / "experiments"
    mock_osrm(requests_mock, 5)

    rows, _ = run_sweep(tmp_path, sizes="5", seeds=2, strategies="global")

    assert len(rows) == 2
    row = rows[0]
    assert row["service_time_min"] == "5.0"
    assert row["t_max_h"] == "3.0"
    assert row["strategy"] == "global"
    assert Dataset.objects.filter(name="Sweep n5 s42").exists()
    config = RoutingConfig.objects.earliest("created_at")
    assert config.service_time_sec == RoutingConfig.DEFAULT_SERVICE_TIME_SEC
    assert config.max_route_time_sec == RoutingConfig.DEFAULT_MAX_ROUTE_TIME_SEC


def test_unknown_strategy_rejected(tmp_path):
    with pytest.raises(CommandError, match="Unknown strategy"):
        call_command("baseline_sweep", strategies="bogus", csv=str(tmp_path / "x.csv"))


def test_missing_dataset_rejected(tmp_path):
    with pytest.raises(CommandError, match="not found"):
        call_command(
            "baseline_sweep", dataset="not-a-uuid", csv=str(tmp_path / "x.csv")
        )
