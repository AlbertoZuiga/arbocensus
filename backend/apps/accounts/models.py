import uuid

from django.contrib.auth.models import AbstractUser
from django.db import models


class CustomUser(AbstractUser):
    class Role(models.TextChoices):
        ADMIN = "admin"
        SURVEYOR = "surveyor"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    role = models.CharField(max_length=20, choices=Role.choices, default=Role.SURVEYOR)

    class Meta(AbstractUser.Meta):
        ordering = ["-date_joined"]

    @property
    def role_display(self) -> str:
        return next(
            (str(lbl) for val, lbl in self.Role.choices if val == self.role),
            str(self.role),
        )

    def __str__(self) -> str:
        return f"{self.username} ({self.role_display})"
