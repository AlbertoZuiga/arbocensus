from pathlib import Path

from apps.datasets.instances import instances_dir, load_instance
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = "Load frozen instance CSV files into datasets with deterministic UUIDs"

    def add_arguments(self, parser):
        parser.add_argument("files", nargs="*", type=str)

    def handle(self, *args, **options):
        paths = (
            [Path(name) for name in options["files"]]
            if options["files"]
            else sorted(instances_dir().glob("*.csv"))
        )
        if not paths:
            raise CommandError("No instance CSV files found")

        for path in paths:
            if not path.exists():
                raise CommandError(f"{path} does not exist")

        for path in paths:
            dataset = load_instance(path)
            self.stdout.write(
                f"{dataset.name}: {dataset.total_trees} trees ({dataset.id})"
            )

        self.stdout.write(self.style.SUCCESS(f"Loaded {len(paths)} instances"))
