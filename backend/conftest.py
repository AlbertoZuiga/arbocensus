import pytest
from django.contrib.gis.geos import Point
from tests.factories import DatasetFactory, TreeFactory


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
