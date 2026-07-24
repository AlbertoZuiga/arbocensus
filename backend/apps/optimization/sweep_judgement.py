import statistics

GATE_BALANCE_MIN = 0.60
LEXICOGRAPHIC_METRICS = ("relleno_msf_sec", "crossings_road", "travel_sec")


def summarize_cell(rows, metrics=LEXICOGRAPHIC_METRICS):
    summary = {"seeds": len(rows)}
    for metric in (*metrics, "balance", "drops", "degenerate_routes"):
        values = [float(row[metric]) for row in rows]
        summary[metric] = statistics.fmean(values)
        summary[f"{metric}_sigma"] = statistics.pstdev(values)
        summary[f"{metric}_max"] = max(values)
    return summary


def passes_gates(summary):
    return (
        summary["drops_max"] == 0
        and summary["degenerate_routes_max"] == 0
        and summary["balance"] >= GATE_BALANCE_MIN
    )


def _not_worse_than_best(summaries, labels, metric):
    best = min(labels, key=lambda label: summaries[label][metric])
    best_mean = summaries[best][metric]
    best_sigma = summaries[best][f"{metric}_sigma"]
    return [
        label
        for label in labels
        if summaries[label][metric] - best_mean
        <= max(summaries[label][f"{metric}_sigma"], best_sigma)
    ]


def pick_winner(summaries, control, metrics=LEXICOGRAPHIC_METRICS):
    # A difference smaller than the seed sigma is not a difference, so each metric
    # narrows the field to everything indistinguishable from its best instead of
    # ordering the cells outright. A field that never narrows to one means no cell
    # separates itself from the control, and the control keeps the instance.
    survivors = [label for label, s in summaries.items() if passes_gates(s)]
    if not survivors:
        return None, []
    for metric in metrics:
        survivors = _not_worse_than_best(summaries, survivors, metric)
        if len(survivors) == 1:
            return survivors[0], survivors
    if control in survivors:
        return control, survivors
    return min(survivors, key=lambda label: summaries[label][metrics[0]]), survivors
