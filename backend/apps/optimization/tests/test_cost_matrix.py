from types import SimpleNamespace
from urllib.parse import unquote

import numpy as np
import pytest
from apps.datasets.models import DistanceMatrix
from apps.optimization.cost_matrix import (
    OSRM_MAX_MATRIX_DIMENSION,
    OSRM_MAX_TREES_PER_REQUEST,
    UNREACHABLE_PENALTY,
    OSRMCostMatrixBuilder,
)
from requests_mock import ANY


def _fake_trees(count):
    return [
        SimpleNamespace(location=SimpleNamespace(x=-70.65 - i * 0.0001, y=-33.45))
        for i in range(count)
    ]


def _request_coord_str(request):
    return unquote(request.url.split("/table/v1/foot/")[1].split("?")[0])


def _mock_osrm_table(requests_mock, trees, ground_truth):
    index_by_coord = {
        f"{tree.location.x},{tree.location.y}": i for i, tree in enumerate(trees)
    }

    def respond(request, context):
        coord_str = _request_coord_str(request)
        subset = [index_by_coord[pair] for pair in coord_str.split(";")]
        query = request.qs
        if "sources" in query:
            rows = [subset[int(k)] for k in unquote(query["sources"][0]).split(";")]
            cols = [
                subset[int(k)] for k in unquote(query["destinations"][0]).split(";")
            ]
        else:
            rows, cols = subset, subset
        return {"durations": ground_truth[np.ix_(rows, cols)].tolist()}

    return requests_mock.get(ANY, json=respond)


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


def test_fetch_rejects_dataset_over_matrix_dimension():
    trees = _fake_trees(OSRM_MAX_MATRIX_DIMENSION + 1)

    with pytest.raises(ValueError, match="dimensión máxima de matriz OSRM"):
        OSRMCostMatrixBuilder()._fetch_from_osrm(trees)


def test_fetch_at_single_request_limit_uses_one_request(requests_mock):
    n = OSRM_MAX_TREES_PER_REQUEST
    trees = _fake_trees(n)
    rng = np.random.default_rng(1)
    adapter = _mock_osrm_table(requests_mock, trees, rng.uniform(0, 100, (n, n)))

    matrix = OSRMCostMatrixBuilder()._fetch_from_osrm(trees)

    assert matrix.shape == (n, n)
    assert adapter.call_count == 1


def test_chunked_matches_single_request(requests_mock):
    n = 30
    trees = _fake_trees(n)
    rng = np.random.default_rng(2)
    ground_truth = rng.uniform(0, 100, (n, n))
    _mock_osrm_table(requests_mock, trees, ground_truth)
    builder = OSRMCostMatrixBuilder()
    coords = [(tree.location.x, tree.location.y) for tree in trees]

    single = builder._request_table(coords)
    chunked = builder._fetch_chunked(coords, chunk_size=10)

    np.testing.assert_array_equal(chunked, single)
    np.testing.assert_array_equal(chunked, ground_truth)


def test_fetch_chunks_above_single_request_limit(requests_mock):
    n = 400
    trees = _fake_trees(n)
    rng = np.random.default_rng(3)
    ground_truth = rng.uniform(0, 100, (n, n))
    adapter = _mock_osrm_table(requests_mock, trees, ground_truth)

    matrix = OSRMCostMatrixBuilder()._fetch_from_osrm(trees)

    np.testing.assert_array_equal(matrix, ground_truth)
    assert adapter.call_count == 9
    for request in adapter.request_history:
        coord_str = _request_coord_str(request)
        assert len(coord_str.split(";")) <= OSRM_MAX_TREES_PER_REQUEST


def test_chunked_null_durations_become_penalty(requests_mock):
    n = 400
    trees = _fake_trees(n)
    ground_truth = np.zeros((n, n))
    ground_truth[0][399] = np.nan
    _mock_osrm_table(requests_mock, trees, ground_truth)

    matrix = OSRMCostMatrixBuilder()._fetch_from_osrm(trees)

    assert matrix[0][399] == UNREACHABLE_PENALTY


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
