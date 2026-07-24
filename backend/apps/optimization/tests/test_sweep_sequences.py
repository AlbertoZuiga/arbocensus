import uuid

import pytest
from apps.optimization.sweep_sequences import (
    SEQUENCE_KEY_COLUMNS,
    append_sequences,
    load_sequences,
    sequence_record,
    sequences_path,
)


def sweep_row(**overrides):
    row = {
        "instance": "area-27-n72",
        "cell": "actual",
        "strategy": "spatial_term",
        "balance_arm": "actual",
        "soft_lower_penalty": 10000,
        "soft_upper_target": 9000,
        "span_coef": 0,
        "time_global_span_coef": 0,
        "post_resequence": False,
        "arc_lambda": 0.0,
        "cluster_neighbors": "",
        "warm_start": "",
        "spatial_span_coef": 3,
        "stops_floor_penalty": 10000,
        "max_vehicles_forced": "",
        "seed": 1,
        "starts": 1,
        "budget_mode": "per-start",
        "k": 2,
        "travel_sec": 4200,
    }
    return {**row, **overrides}


def test_sequences_file_sits_next_to_the_csv(tmp_path):
    assert sequences_path(tmp_path / "sweep.csv") == tmp_path / "sweep.sequences.jsonl"


def test_record_carries_every_key_column_and_no_metric():
    record = sequence_record(sweep_row(), [[uuid.uuid4()]])
    assert set(record) == set(SEQUENCE_KEY_COLUMNS) | {"routes"}


def test_record_stringifies_tree_ids():
    tree_id = uuid.uuid4()
    record = sequence_record(sweep_row(), [[tree_id, tree_id]])
    assert record["routes"] == [[str(tree_id), str(tree_id)]]


def test_record_keeps_route_and_stop_order():
    ids = [uuid.uuid4() for _ in range(4)]
    record = sequence_record(sweep_row(), [[ids[2], ids[0]], [ids[3], ids[1]]])
    assert record["routes"] == [
        [str(ids[2]), str(ids[0])],
        [str(ids[3]), str(ids[1])],
    ]


def test_record_fails_loudly_on_a_row_missing_a_key_column():
    row = sweep_row()
    del row["seed"]
    with pytest.raises(KeyError):
        sequence_record(row, [])


def test_appending_accumulates_one_line_per_cell(tmp_path):
    csv_path = tmp_path / "nested" / "sweep.csv"
    first = [[uuid.uuid4(), uuid.uuid4()]]
    second = [[uuid.uuid4()]]
    append_sequences(csv_path, sweep_row(seed=1), first)
    append_sequences(csv_path, sweep_row(seed=2), second)

    records = load_sequences(csv_path)
    assert [record["seed"] for record in records] == [1, 2]
    assert records[0]["routes"] == [[str(tree_id) for tree_id in first[0]]]
    assert records[1]["routes"] == [[str(second[0][0])]]


def test_loading_a_sweep_that_never_ran_returns_nothing(tmp_path):
    assert load_sequences(tmp_path / "sweep.csv") == []
