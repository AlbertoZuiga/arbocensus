from pathlib import Path

from apps.datasets.instances import dump_legacy_instances, instances_dir
from apps.datasets.legacy import LegacyDatabaseNotConfiguredError
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = "Dump the legacy experiment instances to versioned CSV files"

    def add_arguments(self, parser):
        parser.add_argument("--output", type=str, default=None)

    def handle(self, *args, **options):
        output_dir = Path(options["output"]) if options["output"] else instances_dir()

        try:
            written = dump_legacy_instances(output_dir)
        except LegacyDatabaseNotConfiguredError as exc:
            raise CommandError(str(exc)) from exc

        for path, count in written:
            self.stdout.write(f"{path.name}: {count} trees")
        self.stdout.write(
            self.style.SUCCESS(f"Wrote {len(written)} instances to {output_dir}")
        )
