import json

# The sweep rolls its transaction back, so a solution survives only as an
# aggregate CSV row. Any metric that depends on the stop sequence — self
# crossings among them — then costs a full re-solve to correct. Persisting the
# sequence turns a metric correction into a re-judgement.
SEQUENCE_KEY_COLUMNS = [
    "instance",
    "cell",
    "strategy",
    "balance_arm",
    "soft_lower_penalty",
    "soft_upper_target",
    "span_coef",
    "time_global_span_coef",
    "post_resequence",
    "arc_lambda",
    "cluster_neighbors",
    "warm_start",
    "spatial_span_coef",
    "stops_floor_penalty",
    "max_vehicles_forced",
    "seed",
    "starts",
    "budget_mode",
]


def sequences_path(csv_path):
    return csv_path.with_suffix(".sequences.jsonl")


def sequence_record(row, routes):
    record = {column: row[column] for column in SEQUENCE_KEY_COLUMNS}
    record["routes"] = [[str(tree_id) for tree_id in route] for route in routes]
    return record


def append_sequences(csv_path, row, routes):
    path = sequences_path(csv_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(sequence_record(row, routes)) + "\n")


def load_sequences(csv_path):
    path = sequences_path(csv_path)
    if not path.exists():
        return []
    with path.open(encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]
