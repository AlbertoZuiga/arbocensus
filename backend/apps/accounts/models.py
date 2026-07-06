import uuid

from django.contrib.auth.models import AbstractUser
from django.db import models
from rest_framework.exceptions import ValidationError


class CustomUser(AbstractUser):
    class Role(models.TextChoices):
        ADMIN = "admin"
        SURVEYOR = "surveyor"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    role = models.CharField(max_length=20, choices=Role.choices, default=Role.SURVEYOR)

    class Meta(AbstractUser.Meta):
        ordering = ["-date_joined"]

    def assert_can_change(self, actor, *, role=None, is_active=None) -> None:
        new_role = role if role is not None else self.role
        new_active = is_active if is_active is not None else self.is_active
        losing_admin = self.role == self.Role.ADMIN and new_role != self.Role.ADMIN
        deactivating = self.is_active and new_active is False
        if not (losing_admin or deactivating):
            return
        if self == actor:
            raise ValidationError("You cannot demote or deactivate your own account.")
        active_admin_ids = list(
            CustomUser.objects.filter(role=self.Role.ADMIN, is_active=True).values_list(
                "id", flat=True
            )
        )
        if active_admin_ids == [self.id]:
            raise ValidationError("Cannot demote or deactivate the last active admin.")

    @property
    def role_display(self) -> str:
        return next(
            (str(lbl) for val, lbl in self.Role.choices if val == self.role),
            str(self.role),
        )

    def __str__(self) -> str:
        return f"{self.username} ({self.role_display})"
