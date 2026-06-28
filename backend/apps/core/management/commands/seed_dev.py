import random

from apps.datasets.models import Dataset
from apps.optimization.dataset_factory import create_dataset, generate_points
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand

SEED = 42


class Command(BaseCommand):
    help = "Idempotent dev bootstrap: test users and a light dataset (no solver)"

    def handle(self, *args, **options):
        user_model = get_user_model()
        password = settings.SEED_USER_PASSWORD

        created = self._ensure_users(
            user_model,
            "admin",
            settings.SEED_ADMIN_COUNT,
            user_model.Role.ADMIN,
            password,
        )
        created += self._ensure_users(
            user_model,
            "surveyor",
            settings.SEED_SURVEYOR_COUNT,
            user_model.Role.SURVEYOR,
            password,
        )
        self.stdout.write(f"Users: {created} created, password '{password}'")

        self._ensure_dataset()

    def _ensure_users(self, user_model, base, count, role, password):
        created = 0
        for i in range(1, count + 1):
            username = f"{base}{i}"
            user, was_created = user_model.objects.get_or_create(
                username=username,
                defaults={"email": f"{username}@arbocensus.cl", "role": role},
            )
            if was_created:
                user.set_password(password)
                user.save(update_fields=["password"])
                created += 1
        return created

    def _ensure_dataset(self):
        name = settings.SEED_DEV_DATASET_NAME
        if Dataset.objects.filter(name=name).exists():
            self.stdout.write(f"Dataset '{name}' already exists, skipping")
            return

        rng = random.Random(SEED)
        points = generate_points(rng, settings.SEED_DEV_TREES, "uniform", 1)
        dataset = create_dataset(name, points)
        self.stdout.write(
            self.style.SUCCESS(
                f"Dataset '{name}' created ({dataset.total_trees} trees, no solver)"
            )
        )
