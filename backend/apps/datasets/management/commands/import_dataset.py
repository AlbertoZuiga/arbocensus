from pathlib import Path

from apps.datasets.importers import import_file
from apps.datasets.models import Dataset
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction


class Command(BaseCommand):
    help = "Import trees from a CSV or JSON file into a new dataset"

    def add_arguments(self, parser):
        parser.add_argument("file", type=str)
        parser.add_argument("--name", type=str, default=None)
        parser.add_argument("--description", type=str, default="")

    def handle(self, *args, **options):
        file_path = Path(options["file"])
        name = options["name"] or file_path.stem

        try:
            with transaction.atomic():
                dataset = Dataset.objects.create(
                    name=name,
                    description=options["description"],
                )
                with open(file_path, "rb") as f:
                    count = import_file(f, dataset, file_path.name)
        except (ValueError, OSError) as exc:
            raise CommandError(str(exc)) from exc

        self.stdout.write(
            self.style.SUCCESS(
                f"Imported {count} trees into dataset '{name}' ({dataset.id})"
            )
        )
