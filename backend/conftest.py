import pytest
from django.contrib.gis.geos import Point
from tests.factories import DatasetFactory, TreeFactory


@pytest.fixture(autouse=True)
def media_root(settings, tmp_path):
    # Uploads in tests must never land in the working tree: without this the photo
    # of every visit test is written to backend/media/ and left behind.
    settings.MEDIA_ROOT = tmp_path


@pytest.fixture
def make_dataset_with_trees(db):
    def _make(coords):
        dataset = DatasetFactory(total_trees=len(coords))
        trees = [
            TreeFactory(dataset=dataset, location=Point(lon, lat))
            for lon, lat in coords
        ]
        return dataset, trees

    return _make
