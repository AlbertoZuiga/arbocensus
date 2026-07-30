import csv
import io

from apps.optimization.models import OptimizationJob, RoutingSolution
from apps.optimization.recommendation import (
    BALANCE_GATE,
    CONTROL_PRESET,
    CONTROL_STRATEGY,
    TRAVEL_TIE_PCT,
    order_by_criterion,
    pick_recommended_bulk,
)
from apps.optimization.strategies import PRODUCTION_JOB_PAIRS
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db.models import Q
from django.utils import timezone


class Command(BaseCommand):
    help = (
        "Tally how often each (config_preset, strategy) cell wins the recommendation "
        "criterion over the persisted RoutingSolutions. Writes a CSV to "
        "docs/experiments/ and prints any cell that won but would be pruned by the "
        "current PRODUCTION_JOB_PAIRS fanout."
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
        dataset_ids = list(
            RoutingSolution.objects.filter(job__status=OptimizationJob.Status.COMPLETED)
            # order_by() is required: the model Meta ordering would be carried into the
            # SELECT and defeat the distinct, yielding one "dataset" per solution row.
            .order_by()
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

        # Best by criterion per dataset (first row per dataset, order from the query).
        winner_travel_by_dataset = {}
        winner_id_by_dataset = {}
        for dataset_id, sol_id, travel, _preset, _strategy, *_ in rows:
            if dataset_id not in winner_travel_by_dataset:
                winner_travel_by_dataset[dataset_id] = travel
                winner_id_by_dataset[dataset_id] = sol_id

        recommended_by_dataset = pick_recommended_bulk(dataset_ids)

        # Win rate is measured on a travel-dominated criterion, so a preset that buys
        # route evenness by paying travel cannot win by construction. These deltas
        # against the control are what says whether such a cell earns its CPU.
        control_by_dataset = {}  # dataset_id → (travel, balance)
        for row in rows:
            dataset_id, _sol_id, travel, preset, strategy = row[:5]
            if (
                dataset_id not in control_by_dataset
                and preset == CONTROL_PRESET
                and strategy == CONTROL_STRATEGY
            ):
                control_by_dataset[dataset_id] = (travel, row[7])

        production_pairs = {
            (preset, str(strategy)) for preset, strategy in PRODUCTION_JOB_PAIRS
        }

        cell_stats = {}
        pruned_winners = []  # cells outside the fanout that are the recommended winner

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
                cell_stats[cell] = {
                    "recommended": 0,
                    "strict_winner": 0,
                    "near_winner": 0,
                    "datasets": 0,
                    "travel_deltas": [],
                    "balance_deltas": [],
                }
            stats = cell_stats[cell]

            control = control_by_dataset.get(dataset_id)
            if control is not None and cell != (CONTROL_PRESET, CONTROL_STRATEGY):
                ctrl_travel, ctrl_balance = control
                if ctrl_travel > 0:
                    stats["travel_deltas"].append(
                        (travel - ctrl_travel) / ctrl_travel * 100
                    )
                stats["balance_deltas"].append(balance - ctrl_balance)

            winner_travel = winner_travel_by_dataset[dataset_id]
            is_winner = sol_id == winner_id_by_dataset[dataset_id]
            is_recommended = sol_id == recommended_by_dataset.get(dataset_id)
            within_margin = (
                winner_travel > 0
                and abs(travel - winner_travel) / winner_travel <= TRAVEL_TIE_PCT
            )

            stats["datasets"] += 1
            if is_winner:
                stats["strict_winner"] += 1
            if is_recommended:
                stats["recommended"] += 1
            if within_margin and not is_winner:
                stats["near_winner"] += 1

            if is_recommended and cell not in production_pairs:
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
                "times_strict_winner",
                "times_near_winner_not_winner",
                "datasets_appearing",
                "mean_travel_delta_pct_vs_control",
                "mean_balance_delta_vs_control",
                "in_production_fanout",
            ]
        )
        for cell, stats in sorted(cell_stats.items()):
            travel_deltas = stats["travel_deltas"]
            balance_deltas = stats["balance_deltas"]
            writer.writerow(
                [
                    cell[0],
                    cell[1],
                    stats["recommended"],
                    stats["strict_winner"],
                    stats["near_winner"],
                    stats["datasets"],
                    round(sum(travel_deltas) / len(travel_deltas), 2)
                    if travel_deltas
                    else "",
                    round(sum(balance_deltas) / len(balance_deltas), 3)
                    if balance_deltas
                    else "",
                    cell in production_pairs,
                ]
            )
        csv_text = out.getvalue()

        self.stdout.write(csv_text)

        timestamp = timezone.localtime().strftime("%Y%m%d-%H%M%S")
        out_rel = (
            options["output"]
            or f"docs/experiments/{timestamp}-recommendation-census.csv"
        )
        out_path = settings.BASE_DIR.parent / out_rel
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(csv_text, encoding="utf-8")
        self.stdout.write(f"CSV: {out_path}")

        if pruned_winners:
            for pw in pruned_winners:
                self.stdout.write(
                    self.style.ERROR(
                        f"  dataset={pw['dataset_id']}  "
                        f"preset={pw['config_preset']}  "
                        f"strategy={pw['strategy']}  "
                        f"travel={pw['travel_sec']:.0f}s  gate={pw['gate']}"
                    )
                )
            raise CommandError(
                "Cells outside PRODUCTION_JOB_PAIRS are the recommended winner in the "
                "datasets listed above. Do not prune them."
            )

        self.stdout.write(
            self.style.SUCCESS(
                "OK: every recommended winner is inside PRODUCTION_JOB_PAIRS."
            )
        )
