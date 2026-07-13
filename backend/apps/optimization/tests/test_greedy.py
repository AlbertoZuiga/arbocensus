import csv
import math
from io import StringIO

import numpy as np
import pytest
from apps.datasets.models import Dataset, Tree
from apps.optimization.greedy import solve_greedy
from apps.optimization.management.commands.greedy_baseline import CSV_COLUMNS
from django.contrib.gis.geos import Point
from django.core.management import CommandError, call_command
from requests_mock import ANY

SANTIAGO_LON = -70.65
SANTIAGO_LAT = -33.45

SERVICE_TIME_SEC = 120
MAX_ROUTE_TIME_SEC = 10_800


def uniform_matrix(n, travel=60.0):
    m = np.full((n, n), travel)
    np.fill_diagonal(m, 0.0)
    return m


def route_estimated_time(matrix, route, service_time_sec):
    travel = sum(matrix[a][b] for a, b in zip(route[:-1], route[1:], strict=True))
    return math.ceil(travel + len(route) * service_time_sec)


def test_partitions_every_node_exactly_once():
    routes = solve_greedy(
        uniform_matrix(30),
        max_route_time_sec=MAX_ROUTE_TIME_SEC,
        service_time_sec=SERVICE_TIME_SEC,
    )

    visited = [node for route in routes for node in route]
    assert sorted(visited) == list(range(30))


def test_chains_the_nearest_unvisited_node():
    # Node 0 is closest to 3, 3 is closest to 1, 1 is closest to 2.
    matrix = np.array(
        [
            [0.0, 300.0, 900.0, 100.0],
            [300.0, 0.0, 50.0, 400.0],
            [900.0, 50.0, 0.0, 800.0],
            [100.0, 400.0, 50.0, 0.0],
        ]
    )

    routes = solve_greedy(
        matrix, max_route_time_sec=MAX_ROUTE_TIME_SEC, service_time_sec=SERVICE_TIME_SEC
    )

    assert routes == [[0, 3, 2, 1]]


def test_cuts_the_route_when_the_time_budget_is_exhausted():
    matrix = uniform_matrix(10, travel=600.0)

    routes = solve_greedy(
        matrix, max_route_time_sec=3_000, service_time_sec=SERVICE_TIME_SEC
    )

    assert len(routes) > 1
    for route in routes:
        assert route_estimated_time(matrix, route, SERVICE_TIME_SEC) <= 3_000


def test_no_balance_between_routes():
    # The last route only gets the leftovers: greedy fills each route to the brim.
    matrix = uniform_matrix(7, travel=600.0)

    routes = solve_greedy(
        matrix, max_route_time_sec=3_000, service_time_sec=SERVICE_TIME_SEC
    )

    assert [len(route) for route in routes] == [5, 2]


@pytest.mark.django_db
class TestGreedyBaselineCommand:
    @pytest.fixture
    def dataset(self):
        dataset = Dataset.objects.create(name="real", total_trees=6)
        for i in range(6):
            Tree.objects.create(
                dataset=dataset,
                location=Point(SANTIAGO_LON + i * 0.001, SANTIAGO_LAT + i * 0.001),
            )
        return dataset

    def test_writes_csv_with_metrics(self, tmp_path, requests_mock, dataset, settings):
        settings.EXPERIMENTS_DIR = tmp_path / "experiments"
        requests_mock.get(ANY, json={"durations": uniform_matrix(6).tolist()})
        csv_path = tmp_path / "greedy.csv"

        call_command(
            "greedy_baseline",
            dataset=str(dataset.id),
            service_time=2,
            t_max=3,
            csv=str(csv_path),
            stdout=StringIO(),
        )

        with csv_path.open() as handle:
            rows = list(csv.DictReader(handle))

        assert len(rows) == 1
        assert set(rows[0]) == set(CSV_COLUMNS)
        assert rows[0]["n_trees"] == "6"
        assert rows[0]["dropped_trees"] == "0"
        assert rows[0]["routes_over_t_max"] == "0"
        assert rows[0]["k"] == "1"

    def test_reports_the_per_route_breakdown(
        self, tmp_path, requests_mock, dataset, settings
    ):
        settings.EXPERIMENTS_DIR = tmp_path / "experiments"
        requests_mock.get(ANY, json={"durations": uniform_matrix(6, 600.0).tolist()})
        stdout = StringIO()

        call_command(
            "greedy_baseline",
            dataset=str(dataset.id),
            service_time=2,
            t_max=3_000 / 3600,
            csv=str(tmp_path / "greedy.csv"),
            stdout=stdout,
        )

        lines = stdout.getvalue().splitlines()
        header = lines.index("route,trees,travel_time_sec,estimated_time_sec")

        assert lines[header + 1] == "1,5,2400,3000"
        assert lines[header + 2] == "2,1,0,120"

    def test_missing_dataset_rejected(self, tmp_path):
        with pytest.raises(CommandError, match="not found"):
            call_command(
                "greedy_baseline",
                dataset="not-a-uuid",
                csv=str(tmp_path / "x.csv"),
                stdout=StringIO(),
            )
