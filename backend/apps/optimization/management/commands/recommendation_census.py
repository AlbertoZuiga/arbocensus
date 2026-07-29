import csv
import io
from datetime import datetime

from apps.optimization.config_presets import DEFAULT_CONFIG_PRESET
from apps.optimization.models import OptimizationJob, RoutingSolution
from apps.optimization.recommendation import (
    TRAVEL_TIE_PCT,
    order_by_criterion,
    pick_recommended_bulk,
)
from django.core.management.base import BaseCommand
from django.db.models import Q


class Command(BaseCommand):
    help = (
        "Tally how often each (config_preset, strategy) cell wins the recommendation "
        "criterion over the persisted RoutingSolutions. Writes a CSV to "
        "docs/experiments/ and prints any cell that won but would be pruned by the "
        "planned fanout reduction."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--output",
            type=str,
            default=None,
            help=(
                "Output CSV path (relative to repo root). "
                "Defaults to docs/experiments/<timestamp>-recommendation-census.csv"
            ),
        )

    def handle(self, *args, **options):
        from django.conf import settings

        dataset_ids = list(
            RoutingSolution.objects.filter(job__status=OptimizationJob.Status.COMPLETED)
            .values_list("dataset_id", flat=True)
            .distinct()
        )
        if not dataset_ids:
            self.stdout.write("No completed solutions found — nothing to tally.")
            return

        # Replicate the scoping from pick_recommended_bulk: latest config per dataset.
        latest_config_per_dataset = (
            RoutingSolution.objects.filter(
                dataset_id__in=dataset_ids,
                job__status=OptimizationJob.Status.COMPLETED,
            )
            .order_by("dataset_id", "-job__config__created_at")
            .distinct("dataset_id")
            .values_list("dataset_id", "job__config_id")
        )
        latest_sweeps = Q()
        for dataset_id, config_id in latest_config_per_dataset:
            latest_sweeps |= Q(dataset_id=dataset_id, job__config_id=config_id)
        if not latest_sweeps:
            self.stdout.write("No latest sweep found — nothing to tally.")
            return

        rows = list(
            order_by_criterion(
                RoutingSolution.objects.filter(
                    latest_sweeps, job__status=OptimizationJob.Status.COMPLETED
                )
            ).values_list(
                "dataset_id",
                "id",
                "total_travel_time_sec",
                "job__config_preset",
                "strategy",
                "dropped_trees",
                "degenerate_routes",
                "balance_score",
            )
        )

        from apps.optimization.recommendation import BALANCE_GATE

        # Best travel per dataset (first row per dataset, order guaranteed by query).
        winner_travel_by_dataset = {}
        winner_id_by_dataset = {}
        for dataset_id, sol_id, travel, _preset, _strategy, *_ in rows:
            if dataset_id not in winner_travel_by_dataset:
                winner_travel_by_dataset[dataset_id] = travel
                winner_id_by_dataset[dataset_id] = sol_id

        recommended_by_dataset = pick_recommended_bulk(dataset_ids)

        # Cells to be pruned: cluster_first or any pair not in the production set.
        production_pairs = {
            (DEFAULT_CONFIG_PRESET, "global"),
            (DEFAULT_CONFIG_PRESET, "spatial_term"),
            ("temporal_span_100", "spatial_term"),
            ("arc_linear_30", "spatial_term"),
        }
        pruned_strategies = {"cluster_first"}

        # Tally per (config_preset, strategy) cell across all datasets.
        cell_stats = {}  # (preset, strategy) → {wins, near_wins, datasets}
        pruned_winners = []  # cells that would be pruned but are the winner

        for (
            dataset_id,
            sol_id,
            travel,
            preset,
            strategy,
            drops,
            degens,
            balance,
        ) in rows:
            cell = (preset, strategy)
            if cell not in cell_stats:
                cell_stats[cell] = {"wins": 0, "near_wins": 0, "datasets": 0}

            winner_travel = winner_travel_by_dataset[dataset_id]
            is_winner = sol_id == winner_id_by_dataset[dataset_id]
            is_recommended = sol_id == recommended_by_dataset.get(dataset_id)
            within_margin = (
                winner_travel > 0
                and abs(travel - winner_travel) / winner_travel <= TRAVEL_TIE_PCT
            )

            if is_winner:
                cell_stats[cell]["datasets"] += 1

            if is_recommended:
                cell_stats[cell]["wins"] += 1

            if within_margin and not is_winner:
                cell_stats[cell]["near_wins"] += 1

            pruned = strategy in pruned_strategies or cell not in production_pairs
            if is_recommended and pruned:
                if drops > 0:
                    gate = "dropped_trees"
                elif degens > 0:
                    gate = "degenerate_routes"
                elif balance < BALANCE_GATE:
                    gate = "balance_below_gate"
                else:
                    gate = "travel"
                pruned_winners.append(
                    {
                        "dataset_id": str(dataset_id),
                        "config_preset": preset,
                        "strategy": strategy,
                        "travel_sec": travel,
                        "gate": gate,
                    }
                )

        out = io.StringIO()
        writer = csv.writer(out)
        writer.writerow(
            [
                "config_preset",
                "strategy",
                "times_recommended",
                "times_near_winner_not_recommended",
                "datasets_appearing",
                "pruned_by_plan",
            ]
        )
        for (preset, strategy), stats in sorted(cell_stats.items()):
            pruned = (
                strategy in pruned_strategies
                or (preset, strategy) not in production_pairs
            )
            writer.writerow(
                [
                    preset,
                    strategy,
                    stats["wins"],
                    stats["near_wins"],
                    stats["datasets"],
                    pruned,
                ]
            )
        csv_text = out.getvalue()

        self.stdout.write(csv_text)

        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        out_rel = (
            options["output"]
            or f"docs/experiments/{timestamp}-recommendation-census.csv"
        )
        out_path = settings.BASE_DIR.parent / out_rel
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(csv_text, encoding="utf-8")
        self.stdout.write(f"CSV: {out_path}")

        if pruned_winners:
            self.stdout.write(
                self.style.ERROR(
                    "\nSTOP: the following pruned cells are the recommended winner "
                    "in at least one dataset. Do not proceed with fanout reduction:\n"
                )
            )
            for pw in pruned_winners:
                self.stdout.write(
                    self.style.ERROR(
                        f"  dataset={pw['dataset_id']}  "
                        f"preset={pw['config_preset']}  "
                        f"strategy={pw['strategy']}  "
                        f"travel={pw['travel_sec']:.0f}s  gate={pw['gate']}"
                    )
                )
            raise SystemExit(1)
        else:
            self.stdout.write(
                self.style.SUCCESS(
                    "OK: no pruned cell is the recommended winner in any dataset. "
                    "Safe to proceed with fanout reduction."
                )
            )
