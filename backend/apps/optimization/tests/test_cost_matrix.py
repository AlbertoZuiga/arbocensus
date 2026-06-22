import numpy as np
import pytest
from apps.datasets.models import DistanceMatrix
from apps.optimization.cost_matrix import UNREACHABLE_PENALTY, OSRMCostMatrixBuilder
from requests_mock import ANY

pytestmark = pytest.mark.django_db


def test_build_returns_n_by_n_shape(requests_mock, make_dataset_with_trees):
    dataset, trees = make_dataset_with_trees(
        [(-70.65, -33.45), (-70.66, -33.46), (-70.67, -33.47)]
    )
    requests_mock.get(
        ANY,
        json={"durations": [[0, 10, 20], [10, 0, 15], [20, 15, 0]]},
    )

    matrix = OSRMCostMatrixBuilder().build(trees)

    assert matrix.shape == (3, 3)


def test_null_durations_become_penalty(requests_mock, make_dataset_with_trees):
    dataset, trees = make_dataset_with_trees([(-70.65, -33.45), (-70.66, -33.46)])
    requests_mock.get(
        ANY,
        json={"durations": [[0, None], [None, 0]]},
    )

    matrix = OSRMCostMatrixBuilder().build(trees)

    assert matrix[0][1] == UNREACHABLE_PENALTY
    assert matrix[1][0] == UNREACHABLE_PENALTY


def test_cache_hit_skips_osrm(requests_mock, make_dataset_with_trees):
    dataset, trees = make_dataset_with_trees([(-70.65, -33.45), (-70.66, -33.46)])
    builder = OSRMCostMatrixBuilder()
    sorted_trees = sorted(trees, key=lambda tree: tree.id)
    DistanceMatrix.objects.create(
        dataset=dataset,
        source_hash=builder._compute_hash(sorted_trees),
        matrix_data=[[0, 5], [5, 0]],
        dimension=2,
    )
    adapter = requests_mock.get(ANY, json={"durations": [[0, 5], [5, 0]]})

    matrix = builder.build(trees)

    assert adapter.call_count == 0
    np.testing.assert_array_equal(matrix, np.array([[0, 5], [5, 0]], dtype=float))


def test_matrix_order_deterministic_by_tree_id(requests_mock, make_dataset_with_trees):
    dataset, trees = make_dataset_with_trees(
        [(-70.65, -33.45), (-70.66, -33.46), (-70.67, -33.47)]
    )
    adapter = requests_mock.get(
        ANY,
        json={"durations": [[0, 1, 2], [1, 0, 3], [2, 3, 0]]},
    )
    builder = OSRMCostMatrixBuilder()

    assert builder._compute_hash(trees) == builder._compute_hash(list(reversed(trees)))

    builder.build(list(reversed(trees)))

    ordered = sorted(trees, key=lambda tree: tree.id)
    expected_coords = ";".join(
        f"{tree.location.x},{tree.location.y}" for tree in ordered
    )
    assert expected_coords in adapter.last_request.url
