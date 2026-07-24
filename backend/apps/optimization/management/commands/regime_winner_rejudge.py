import collections
import csv
import statistics

from apps.optimization.sweep_judgement import (
    LEXICOGRAPHIC_METRICS,
    passes_gates,
    pick_winner,
    summarize_cell,
)
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

RELLENO_TARGET_DROP = 0.30

CELL_METRIC_COLUMNS = [
    "k",
    "drops_max",
    "degenerate_routes_max",
    "balance",
    "relleno_msf_sec",
    "relleno_msf_sec_sigma",
    "crossings_road",
    "crossings_road_sigma",
    "crossings_chord",
    "crossings_chord_sigma",
    "travel_sec",
    "travel_sec_sigma",
]

CELL_COLUMNS = ["instance", "cell", "seeds", "gates_ok", *CELL_METRIC_COLUMNS]

WINNER_COLUMNS = [
    "instance",
    "n",
    "k_hat",
    "rho_pad",
    "saturation_hat",
    "density_per_km2",
    "regime",
    "winner",
    "survivors",
    "predicted_winner",
    "predicted_ok",
    "best_relleno_drop",
    "relleno_target_met",
    "h1_ok",
]


class Command(BaseCommand):
    help = (
        "Re-judge a published sweep instance by instance and confront the winners "
        "with the pre-solve regime predicate rho_pad. Applies the a priori "
        "lexicographic criterion (gates, then padding, self-crossings on roads and "
        "travel, with sigma-wide ties) to every cell, then reports the single best "
        "default and the regime guard side by side. No solver, no OSRM."
    )

    def add_arguments(self, parser):
        parser.add_argument("--features", type=str, required=True)
        parser.add_argument("--sweep", type=str, required=True)
        parser.add_argument("--control", type=str, required=True)
        parser.add_argument(
            "--regime-cell",
            type=str,
            required=True,
            help="cell the guard picks when rho_pad <= 1",
        )
        parser.add_argument("--out-prefix", type=str, required=True)

    def handle(self, *args, **options):
        root = settings.BASE_DIR.parent
        features = self._features(root / options["features"])
        grouped = self._grouped(root / options["sweep"])
        control = options["control"]
        regime_cell = options["regime_cell"]

        summaries = {
            instance: {
                cell: summarize_cell(
                    rows, metrics=(*LEXICOGRAPHIC_METRICS, "crossings_chord", "k")
                )
                for cell, rows in cells.items()
            }
            for instance, cells in grouped.items()
        }
        missing = set(summaries) - set(features)
        if missing:
            raise CommandError("features CSV lacks: " + ", ".join(sorted(missing)))

        cell_rows = []
        winner_rows = []
        exact_drops = []
        for instance in sorted(summaries, key=lambda i: features[i]["rho_pad"]):
            cells = summaries[instance]
            if control not in cells:
                raise CommandError(f"{instance}: control cell {control} absent")
            winner, survivors = pick_winner(cells, control)
            rho_pad = features[instance]["rho_pad"]
            regime = "padding-bound" if rho_pad > 1 else "floor-satisfiable"
            predicted = control if rho_pad > 1 else regime_cell
            best_drop = self._best_relleno_drop(cells, control)
            exact_drops.append(best_drop)
            target_met = best_drop >= RELLENO_TARGET_DROP
            winner_rows.append(
                {
                    "instance": instance,
                    "n": features[instance]["n"],
                    "k_hat": features[instance]["k_hat"],
                    "rho_pad": rho_pad,
                    "saturation_hat": features[instance]["saturation_hat"],
                    "density_per_km2": features[instance]["density_per_km2"],
                    "regime": regime,
                    "winner": winner or "none",
                    "survivors": " ".join(sorted(survivors)),
                    "predicted_winner": predicted,
                    "predicted_ok": winner == predicted,
                    "best_relleno_drop": round(best_drop, 3),
                    "relleno_target_met": target_met,
                    "h1_ok": target_met != (rho_pad > 1),
                }
            )
            for cell, summary in sorted(cells.items()):
                cell_rows.append(
                    {
                        "instance": instance,
                        "cell": cell,
                        "seeds": summary["seeds"],
                        "gates_ok": passes_gates(summary),
                        **{
                            column: round(summary[column], 3)
                            for column in CELL_METRIC_COLUMNS
                        },
                    }
                )

        prefix = root / options["out_prefix"]
        prefix.parent.mkdir(parents=True, exist_ok=True)
        self._write(
            prefix.with_name(prefix.name + "-cells.csv"), CELL_COLUMNS, cell_rows
        )
        self._write(
            prefix.with_name(prefix.name + "-winners.csv"), WINNER_COLUMNS, winner_rows
        )
        self._report(winner_rows, exact_drops, summaries, control, regime_cell)

    def _best_relleno_drop(self, cells, control):
        baseline = cells[control]["relleno_msf_sec"]
        if baseline <= 0:
            return 0.0
        best = min(
            summary["relleno_msf_sec"]
            for cell, summary in cells.items()
            if cell != control
        )
        return (baseline - best) / baseline

    def _report(self, winner_rows, exact_drops, summaries, control, regime_cell):
        total = len(winner_rows)
        wins = collections.Counter(row["winner"] for row in winner_rows)
        majority_cell, majority_hits = wins.most_common(1)[0]
        guard_hits = sum(1 for row in winner_rows if row["predicted_ok"])
        h1_hits = sum(1 for row in winner_rows if row["h1_ok"])

        self.stdout.write("")
        self.stdout.write(f"instances judged: {total}")
        self.stdout.write(f"winners: {dict(wins)}")
        self.stdout.write(
            f"H1 (rho_pad predicts a >={RELLENO_TARGET_DROP:.0%} relleno drop): "
            f"{h1_hits}/{total}"
        )
        self.stdout.write(f"H2 (regime guard picks the winner): {guard_hits}/{total}")
        self.stdout.write(
            f"majority-class baseline ({majority_cell}): {majority_hits}/{total}"
        )
        for feature in ("rho_pad", "saturation_hat"):
            rank_correlation = statistics.correlation(
                [row[feature] for row in winner_rows], exact_drops, method="ranked"
            )
            self.stdout.write(
                f"Spearman {feature} vs best relleno drop: {rank_correlation:+.3f}"
            )

        self.stdout.write("")
        self.stdout.write("single-default readings (aggregate over all instances):")
        for cell in sorted({c for cells in summaries.values() for c in cells}):
            self.stdout.write(
                self._aggregate_line(cell, summaries, lambda _r, c=cell: c)
            )
        self.stdout.write(
            self._aggregate_line(
                f"guard[{control}|{regime_cell}]",
                summaries,
                lambda row: control if row["rho_pad"] > 1 else regime_cell,
                winner_rows,
            )
        )

    def _aggregate_line(self, label, summaries, chooser, winner_rows=None):
        rows = winner_rows or [{"instance": i, "rho_pad": 0.0} for i in summaries]
        picked = [summaries[row["instance"]][chooser(row)] for row in rows]
        relleno = sum(s["relleno_msf_sec"] for s in picked)
        road = sum(s["crossings_road"] for s in picked)
        travel = sum(s["travel_sec"] for s in picked)
        balance = statistics.fmean(s["balance"] for s in picked)
        degenerate = sum(1 for s in picked if s["degenerate_routes_max"] > 0)
        gated = sum(1 for s in picked if not passes_gates(s))
        return (
            f"  {label:28s} relleno={relleno:9.0f} road={road:6.1f} "
            f"travel={travel:9.0f} balance={balance:.3f} "
            f"deg_instances={degenerate} gate_failures={gated}"
        )

    def _features(self, path):
        with path.open(newline="", encoding="utf-8") as handle:
            return {
                row["instance"]: {
                    "n": int(row["n"]),
                    "k_hat": int(row["k_hat"]),
                    "rho_pad": float(row["rho_pad"]),
                    "saturation_hat": float(row["saturation_hat"]),
                    "density_per_km2": float(row["density_per_km2"]),
                }
                for row in csv.DictReader(handle)
            }

    def _grouped(self, path):
        grouped = collections.defaultdict(lambda: collections.defaultdict(list))
        with path.open(newline="", encoding="utf-8") as handle:
            for row in csv.DictReader(handle):
                grouped[row["instance"]][row["cell"]].append(row)
        return grouped

    def _write(self, path, columns, rows):
        with path.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=columns)
            writer.writeheader()
            writer.writerows(rows)
        self.stdout.write(self.style.SUCCESS(f"Wrote {len(rows)} rows: {path}"))
