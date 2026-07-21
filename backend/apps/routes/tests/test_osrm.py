import time

import pytest
from apps.routes import osrm


def test_fetch_route_paths_returns_empty_without_input():
    assert osrm.fetch_route_paths([]) == []


def test_fetch_route_paths_keeps_input_order(monkeypatch):
    monkeypatch.setattr(osrm, "fetch_route_path", lambda coordinates: coordinates[0])

    assert osrm.fetch_route_paths([["a"], ["b"], ["c"]]) == ["a", "b", "c"]


def test_fetch_route_paths_stops_early_when_a_call_fails(monkeypatch):
    monkeypatch.setattr(osrm, "MAX_PARALLEL_ROUTE_REQUESTS", 1)
    started = []

    def fetch(coordinates):
        started.append(coordinates)
        if len(started) == 1:
            raise RuntimeError("osrm down")
        time.sleep(0.05)
        return coordinates

    monkeypatch.setattr(osrm, "fetch_route_path", fetch)

    with pytest.raises(RuntimeError):
        osrm.fetch_route_paths([[[0, 0], [1, 1]]] * 20)

    assert len(started) < 20
