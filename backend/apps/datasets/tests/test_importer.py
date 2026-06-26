import io
import json

import pytest
from apps.datasets.importers import import_file
from apps.datasets.models import Dataset, Tree

pytestmark = pytest.mark.django_db


def make_dataset():
    return Dataset.objects.create(name="Import target")


def test_csv_import_detects_lat_lon_columns():
    dataset = make_dataset()
    csv_file = io.StringIO("latitude,longitude\n-33.45,-70.65\n-33.46,-70.66\n")

    count = import_file(csv_file, dataset, "trees.csv")

    assert count == 2
    assert Tree.objects.filter(dataset=dataset).count() == 2


def test_csv_import_persists_point_in_lon_lat_order():
    dataset = make_dataset()
    csv_file = io.StringIO("lat,lon\n-33.45,-70.65\n")

    import_file(csv_file, dataset, "trees.csv")

    tree = Tree.objects.get(dataset=dataset)
    assert tree.location.x == pytest.approx(-70.65)
    assert tree.location.y == pytest.approx(-33.45)


def test_csv_import_skips_rows_with_missing_coordinates():
    dataset = make_dataset()
    csv_file = io.StringIO("lat,lon\n-33.45,-70.65\n,-70.66\n-33.47,\n")

    count = import_file(csv_file, dataset, "trees.csv")

    assert count == 1


def test_csv_import_without_lat_column_raises():
    dataset = make_dataset()
    csv_file = io.StringIO("foo,lon\n1,2\n")

    with pytest.raises(ValueError, match="No lat column"):
        import_file(csv_file, dataset, "trees.csv")


def test_json_import_detects_keys_and_counts():
    dataset = make_dataset()
    payload = json.dumps(
        {
            "trees": [
                {"lat": -33.45, "lon": -70.65},
                {"lat": -33.46, "lon": -70.66},
            ]
        }
    )
    json_file = io.StringIO(payload)

    count = import_file(json_file, dataset, "trees.json")

    assert count == 2
    tree = Tree.objects.filter(dataset=dataset).first()
    assert tree.location.x == pytest.approx(-70.65) or tree.location.x == pytest.approx(
        -70.66
    )


def test_json_import_skips_null_coordinates():
    dataset = make_dataset()
    payload = json.dumps(
        {
            "trees": [
                {"lat": -33.45, "lon": -70.65},
                {"lat": None, "lon": -70.66},
            ]
        }
    )
    json_file = io.StringIO(payload)

    count = import_file(json_file, dataset, "trees.json")

    assert count == 1


def test_json_import_without_trees_array_raises():
    dataset = make_dataset()
    json_file = io.StringIO(json.dumps({"items": []}))

    with pytest.raises(ValueError, match="top-level 'trees' array"):
        import_file(json_file, dataset, "trees.json")


def test_unsupported_extension_raises():
    dataset = make_dataset()
    with pytest.raises(ValueError, match="Unsupported format"):
        import_file(io.StringIO(""), dataset, "trees.txt")


def test_import_updates_dataset_total_trees():
    dataset = make_dataset()
    csv_file = io.StringIO("lat,lon\n-33.45,-70.65\n-33.46,-70.66\n")

    import_file(csv_file, dataset, "trees.csv")

    dataset.refresh_from_db()
    assert dataset.total_trees == 2


def test_csv_import_detects_uppercase_columns():
    dataset = make_dataset()
    csv_file = io.StringIO("LAT,LON\n-33.45,-70.65\n")

    count = import_file(csv_file, dataset, "trees.csv")

    assert count == 1
    tree = Tree.objects.get(dataset=dataset)
    assert tree.location.x == pytest.approx(-70.65)
    assert tree.location.y == pytest.approx(-33.45)


def test_csv_import_detects_lng_and_spanish_aliases():
    dataset = make_dataset()
    csv_file = io.StringIO("latitud,lng\n-33.45,-70.65\n")

    count = import_file(csv_file, dataset, "trees.csv")

    assert count == 1
    tree = Tree.objects.get(dataset=dataset)
    assert tree.location.x == pytest.approx(-70.65)
    assert tree.location.y == pytest.approx(-33.45)


def test_csv_import_with_semicolon_delimiter():
    dataset = make_dataset()
    csv_file = io.StringIO("lat;lon\n-33.45;-70.65\n-33.46;-70.66\n")

    count = import_file(csv_file, dataset, "trees.csv")

    assert count == 2


def test_csv_import_parses_decimal_comma():
    dataset = make_dataset()
    csv_file = io.StringIO('lat;lon\n"-33,45";"-70,65"\n')

    import_file(csv_file, dataset, "trees.csv")

    tree = Tree.objects.get(dataset=dataset)
    assert tree.location.x == pytest.approx(-70.65)
    assert tree.location.y == pytest.approx(-33.45)


def test_csv_import_without_lon_column_raises():
    dataset = make_dataset()
    csv_file = io.StringIO("lat,foo\n1,2\n")

    with pytest.raises(ValueError, match="No lon column"):
        import_file(csv_file, dataset, "trees.csv")
