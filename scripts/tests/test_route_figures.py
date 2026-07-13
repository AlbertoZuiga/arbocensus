import json
import math
from pathlib import Path

import pytest
from route_figures import (
    check_csv_matches_geojson,
    es_int,
    es_pct,
    legend_label,
    load_csv,
    load_geojson,
    main,
    nice_scale_length,
    project,
    route_style,
    self_crossings,
)

EXPERIMENTS = Path(__file__).resolve().parents[2] / "docs" / "experiments"

RUNS = ["r1", "r2", "r3", "r3b"]
WORST_PAIRS = [("r4-worst-pair", "r1"), ("r2-worst-pair", "r2")]


def artifacts(run, csv_run=None):
    return (
        EXPERIMENTS / f"route-audit-20260713-{run}.geojson",
        EXPERIMENTS / f"route-audit-20260713-{csv_run or run}.csv",
    )


@pytest.mark.parametrize("run", RUNS)
def test_csv_and_geojson_of_a_run_agree(run):
    geojson, csv_path = artifacts(run)
    _, props = load_geojson(geojson)
    rows, summary = load_csv(csv_path)

    check_csv_matches_geojson(rows, props)
    assert summary["n_trees"] == sum(row["n_trees"] for row in rows.values())


@pytest.mark.parametrize("run", RUNS)
def test_recomputed_crossings_reproduce_the_csv_column(run):
    """The figure marks crossings; the count it draws must be the audit's, not a new number."""
    geojson, csv_path = artifacts(run)
    routes, _ = load_geojson(geojson)
    rows, _ = load_csv(csv_path)
    lat0 = sum(lat for coords in routes.values() for _, lat in coords) / sum(
        len(coords) for coords in routes.values()
    )

    recomputed = {
        number: len(self_crossings(project(coords, lat0)))
        for number, coords in routes.items()
    }

    assert recomputed == {number: row["self_crossings"] for number, row in rows.items()}


@pytest.mark.parametrize(("pair", "run"), WORST_PAIRS)
def test_worst_pair_geojson_matches_its_parent_run_csv(pair, run):
    geojson, csv_path = artifacts(pair, csv_run=run)
    routes, props = load_geojson(geojson)
    rows, _ = load_csv(csv_path)

    assert len(routes) == 2
    check_csv_matches_geojson({n: rows[n] for n in routes}, props)


def test_csv_geojson_mismatch_is_loud():
    rows = {1: {"n_trees": 9, "duration_sec": 9396}}
    props = {1: {"n_trees": 9, "duration_sec": 9999}}

    with pytest.raises(ValueError, match="different runs"):
        check_csv_matches_geojson(rows, props)


def test_project_reads_lon_lat_not_lat_lon():
    """GeoJSON is [lon, lat]: swapping them silently mirrors every map."""
    origin, east, north = project(
        [(-70.65, -33.45), (-70.64, -33.45), (-70.65, -33.44)], -33.45
    )

    assert east[0] > origin[0] and east[1] == pytest.approx(origin[1])
    assert north[1] > origin[1] and north[0] == pytest.approx(origin[0])
    # 0.01° of latitude is ~1.11 km; the same step in longitude shrinks by cos(lat).
    assert north[1] - origin[1] == pytest.approx(1112, abs=5)
    assert east[0] - origin[0] == pytest.approx(
        1112 * math.cos(math.radians(33.45)), abs=5
    )


def test_self_crossings_counts_only_strict_crossings():
    square_with_backtrack = [(0, 0), (10, 10), (10, 0), (0, 10)]
    open_path = [(0, 0), (10, 0), (10, 10), (0, 10)]
    touching_at_a_shared_stop = [(0, 0), (10, 0), (5, 5), (10, 0), (0, 10)]

    assert len(self_crossings(square_with_backtrack)) == 1
    assert self_crossings(open_path) == []
    assert self_crossings(touching_at_a_shared_stop) == []
    assert self_crossings([(0, 0), (1, 1), (2, 2)]) == []


def test_crossing_point_lands_on_both_segments():
    ((x, y),) = self_crossings([(0, 0), (10, 10), (10, 0), (0, 10)])

    assert (x, y) == pytest.approx((5.0, 5.0))


def test_route_styles_are_unique_per_slot_for_a_full_run():
    styles = [tuple(route_style(slot).values()) for slot in range(24)]

    assert len(set(styles)) == 24


def test_scale_bar_length_is_a_round_number_under_the_span():
    assert nice_scale_length(2000) == 500
    assert nice_scale_length(300) == 100
    assert nice_scale_length(40000) == 10000


def test_spanish_number_formatting():
    assert es_int(10077) == "10.077"
    assert es_pct(0.131) == "13,1 %"
    assert (
        legend_label(
            19,
            {
                "n_trees": 73,
                "duration_sec": 10077,
                "walk_ratio": 0.131,
                "self_crossings": 13,
            },
        )
        == "Ruta 19: 73 árboles · 10.077 s · caminata 13,1 % · 13 cruces"
    )
    assert legend_label(
        15,
        {
            "n_trees": 61,
            "duration_sec": 10730,
            "walk_ratio": 0.318,
            "self_crossings": 1,
        },
    ).endswith("1 cruce")


def test_single_figure_renders_pdf_and_png(tmp_path):
    geojson, csv_path = artifacts("r3b")
    out = tmp_path / "single"

    main(
        [
            "single",
            "--geojson",
            str(geojson),
            "--csv",
            str(csv_path),
            "--highlight",
            "1",
            "--zoom-route",
            "1",
            "--crop-to-highlight",
            "--out",
            str(out),
        ]
    )

    assert out.with_suffix(".pdf").stat().st_size > 0
    assert out.with_suffix(".png").stat().st_size > 0


def test_compare_figure_is_byte_identical_across_renders(tmp_path):
    """The PDF is versioned: a re-render must not churn the diff."""
    left_geojson, left_csv = artifacts("r3b")
    right_geojson, right_csv = artifacts("r3")
    argv = [
        "compare",
        "--left-geojson",
        str(left_geojson),
        "--left-csv",
        str(left_csv),
        "--right-geojson",
        str(right_geojson),
        "--right-csv",
        str(right_csv),
        "--out",
        str(tmp_path / "compare"),
    ]

    main(argv)
    first = (tmp_path / "compare.pdf").read_bytes()
    main(argv)
    second = (tmp_path / "compare.pdf").read_bytes()

    assert first == second


def test_geojson_route_order_does_not_depend_on_feature_order(tmp_path):
    geojson, _ = artifacts("r3b")
    data = json.loads(geojson.read_text(encoding="utf-8"))
    data["features"].reverse()
    shuffled = tmp_path / "shuffled.geojson"
    shuffled.write_text(json.dumps(data), encoding="utf-8")

    assert load_geojson(shuffled)[0] == load_geojson(geojson)[0]
