import hashlib

import numpy as np
import pytest
from apps.datasets.models import DistanceMatrix
from apps.optimization.feasibility import check_config
from django.contrib.gis.geos import Point
from rest_framework.test import APIClient
from tests.factories import CustomUserFactory, DatasetFactory, TreeFactory

pytestmark = pytest.mark.django_db


def _seed_matrix(dataset, trees, matrix_data):
    ordered = sorted(trees, key=lambda t: t.id)
    payload = ",".join(sorted(str(t.id) for t in ordered))
    source_hash = hashlib.sha256(payload.encode()).hexdigest()
    DistanceMatrix.objects.create(
        dataset=dataset,
        source_hash=source_hash,
        matrix_data=matrix_data,
        dimension=len(trees),
    )


def _close_matrix(n, travel=10.0):
    """n×n matrix with uniform small travel times."""
    m = np.full((n, n), travel)
    np.fill_diagonal(m, 0.0)
    return m.tolist()


def _far_matrix(n, travel=1000.0):
    """n×n matrix with large travel times so routes need lots of travel time."""
    m = np.full((n, n), travel)
    np.fill_diagonal(m, 0.0)
    return m.tolist()


def _make_trees(n, lon=-70.65, lat=-33.45):
    dataset = DatasetFactory(total_trees=n)
    trees = [TreeFactory(dataset=dataset, location=Point(lon, lat)) for _ in range(n)]
    return dataset, trees


# --- Blocking: service > T_max ---


def test_service_exceeds_tmax():
    dataset, _ = _make_trees(3)
    result = check_config(
        dataset, min_route_time_sec=3600, max_route_time_sec=60, service_time_sec=120
    )
    codes = [b["code"] for b in result["blocking"]]
    assert "service_exceeds_tmax" in codes
    assert result["diagnostics"]["matrix_cached"] is False


# --- Blocking: too few trees ---


def test_too_few_trees_zero():
    dataset = DatasetFactory()
    result = check_config(
        dataset, min_route_time_sec=3600, max_route_time_sec=7200, service_time_sec=120
    )
    codes = [b["code"] for b in result["blocking"]]
    assert "too_few_trees" in codes


def test_too_few_trees_one():
    dataset, _ = _make_trees(1)
    result = check_config(
        dataset, min_route_time_sec=3600, max_route_time_sec=7200, service_time_sec=120
    )
    codes = [b["code"] for b in result["blocking"]]
    assert "too_few_trees" in codes


# --- Warning: drop_all_risk (6 close trees, T_min=7200, service=180) ---


def test_drop_all_risk_close_trees():
    """
    6 trees, all co-located (travel ≈ 10 s each pair).
    W_max = 6*180 + 2*MST_total ≈ 1080 + 2*50 = 1180 << 7200 - 590 = 6610.
    """
    n = 6
    dataset, trees = _make_trees(n)
    _seed_matrix(dataset, trees, _close_matrix(n, travel=10.0))

    result = check_config(
        dataset,
        min_route_time_sec=7200,
        max_route_time_sec=10800,
        service_time_sec=180,
    )
    codes = [w["code"] for w in result["warnings"]]
    assert "drop_all_risk" in codes
    assert not result["blocking"]


def test_drop_all_risk_detail_tracks_min_route_time():
    n = 6
    dataset, trees = _make_trees(n)
    _seed_matrix(dataset, trees, _close_matrix(n, travel=10.0))

    details = {}
    for min_route_time_sec in (7200, 3600):
        result = check_config(
            dataset,
            min_route_time_sec=min_route_time_sec,
            max_route_time_sec=10800,
            service_time_sec=180,
        )
        details[min_route_time_sec] = result["warnings"][0]["detail"]

    assert "120 min por ruta" in details[7200]
    assert "60 min por ruta" in details[3600]
    assert details[7200] != details[3600]


def test_messages_avoid_solver_internals():
    n = 6
    dataset, trees = _make_trees(n)
    _seed_matrix(dataset, trees, _close_matrix(n, travel=10.0))

    result = check_config(
        dataset,
        min_route_time_sec=7200,
        max_route_time_sec=10800,
        service_time_sec=180,
    )
    detail = result["warnings"][0]["detail"]
    for jargon in ("solver", "ρ", "1,000,000", "1.000.000", " s "):
        assert jargon not in detail


# --- Not blocking: same 6 trees but very dispersed (false-positive guard) ---


def test_no_false_positive_dispersed_trees():
    """
    6 trees, travel = 700 s per pair.
    MST of 5 edges × 700 = 3500 s → W_max = 1080 + 7000 = 8080 > 6610.
    Must NOT block.
    """
    n = 6
    dataset, trees = _make_trees(n)
    _seed_matrix(dataset, trees, _far_matrix(n, travel=700.0))

    result = check_config(
        dataset,
        min_route_time_sec=7200,
        max_route_time_sec=10800,
        service_time_sec=180,
    )
    warning_codes = [w["code"] for w in result["warnings"]]
    blocking_codes = [b["code"] for b in result["blocking"]]
    assert "drop_all_risk" not in warning_codes
    assert "service_exceeds_tmax" not in blocking_codes
    assert "too_few_trees" not in blocking_codes


# --- No matrix → no drop_all_risk, only possible level-1 warning ---


def test_no_matrix_never_warns_drop_all_risk():
    n = 6
    dataset, _ = _make_trees(n)
    # No DistanceMatrix created — cache miss.
    result = check_config(
        dataset,
        min_route_time_sec=7200,
        max_route_time_sec=10800,
        service_time_sec=180,
    )
    warning_codes = [w["code"] for w in result["warnings"]]
    assert "drop_all_risk" not in warning_codes
    assert result["diagnostics"]["matrix_cached"] is False


def test_no_matrix_warns_drop_all_likely_when_service_very_low():
    """n*s < T_min - 100*n → warn drop_all_likely."""
    n = 6
    dataset, _ = _make_trees(n)
    # n*s = 6*180 = 1080, T_min - 100*n = 7200 - 600 = 6600 → 1080 < 6600
    result = check_config(
        dataset,
        min_route_time_sec=7200,
        max_route_time_sec=10800,
        service_time_sec=180,
    )
    warning_codes = [w["code"] for w in result["warnings"]]
    assert "drop_all_likely" in warning_codes


# --- Warning: padding_regime (rho_pad > 1) ---


def test_padding_regime_warning():
    """
    4 trees, T_min = 600, T_max = 1000, service = 100, travel = 10 s.
    drop_threshold = 600 - (4*1_000_000 - 100_000)/10_000 = 600 - 390 = 210.
    work_ub = 4*100 + 2*30 = 460 >= 210 → NOT blocked.
    k_hat = 1 (400+30=430 <= 1*1000), rho_pad = 1*600/430 ≈ 1.4 > 1 → warn.
    """
    n = 4
    dataset, trees = _make_trees(n)
    _seed_matrix(dataset, trees, _close_matrix(n, travel=10.0))

    result = check_config(
        dataset,
        min_route_time_sec=600,
        max_route_time_sec=1000,
        service_time_sec=100,
    )
    warning_codes = [w["code"] for w in result["warnings"]]
    assert "padding_regime" in warning_codes
    assert not result["blocking"]


# --- POST /optimization/jobs/ integration tests ---


def _admin_client():
    client = APIClient()
    client.force_authenticate(user=CustomUserFactory(role="admin"))
    return client


def _post_job(dataset, service_time_sec=180, min_time=7200, max_time=10800):
    return _admin_client().post(
        "/api/optimization/jobs/",
        {
            "dataset": str(dataset.id),
            "min_route_time_sec": min_time,
            "max_route_time_sec": max_time,
            "service_time_sec": service_time_sec,
        },
        format="json",
    )


def test_post_returns_400_on_service_exceeds_tmax():
    dataset, _ = _make_trees(3)
    response = _post_job(dataset, service_time_sec=120, min_time=60, max_time=100)
    assert response.status_code == 400


def test_post_succeeds_when_drop_all_risk(monkeypatch):
    n = 6
    dataset, trees = _make_trees(n)
    _seed_matrix(dataset, trees, _close_matrix(n, travel=10.0))
    monkeypatch.setattr(
        "apps.optimization.views.run_optimization.delay", lambda *a: None
    )

    response = _post_job(dataset, service_time_sec=180, min_time=7200, max_time=10800)
    assert response.status_code == 201


def test_post_succeeds_when_dispersed_trees(monkeypatch):
    n = 6
    dataset, trees = _make_trees(n)
    _seed_matrix(dataset, trees, _far_matrix(n, travel=700.0))
    monkeypatch.setattr(
        "apps.optimization.views.run_optimization.delay", lambda *a: None
    )

    response = _post_job(dataset, service_time_sec=180, min_time=7200, max_time=10800)
    assert response.status_code == 201
