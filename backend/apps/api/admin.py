"""Django admin registration for all arbocensus API models."""

from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

from .models import (
    Answer,
    Area,
    Campaign,
    Institution,
    Participant,
    Sample,
    Sponsor,
    Step,
    Team,
    User,
)


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    """Admin configuration for the custom User model."""

    fieldsets = (
        (None, {"fields": ("username", "password")}),
        ("Personal info", {"fields": ("email",)}),
        (
            "Permissions",
            {
                "fields": (
                    "is_active",
                    "is_verified",
                    "is_superuser",
                    "groups",
                    "user_permissions",
                )
            },
        ),
        ("Important dates", {"fields": ("last_login",)}),
    )
    add_fieldsets = (
        (
            None,
            {
                "classes": ("wide",),
                "fields": ("username", "email", "password1", "password2"),
            },
        ),
    )
    list_display = ("username", "email", "is_verified", "is_active", "is_superuser")
    list_filter = ("is_active", "is_verified", "is_superuser")
    search_fields = ("username", "email")
    ordering = ("username",)


@admin.register(Institution)
class InstitutionAdmin(admin.ModelAdmin):
    """Admin configuration for Institution."""

    list_display = ("id", "name")
    search_fields = ("name",)


@admin.register(Sponsor)
class SponsorAdmin(admin.ModelAdmin):
    """Admin configuration for Sponsor."""

    list_display = ("id", "name", "main_color")
    search_fields = ("name",)


@admin.register(Campaign)
class CampaignAdmin(admin.ModelAdmin):
    """Admin configuration for Campaign."""

    list_display = ("id", "name", "start_date", "end_date", "sponsor")
    list_filter = ("sponsor",)
    search_fields = ("name",)


@admin.register(Area)
class AreaAdmin(admin.ModelAdmin):
    """Admin configuration for Area."""

    list_display = ("id", "name", "campaign", "points_per_sample")
    list_filter = ("campaign",)
    search_fields = ("name",)


@admin.register(Team)
class TeamAdmin(admin.ModelAdmin):
    """Admin configuration for Team."""

    list_display = ("id", "name", "campaign", "institution", "is_public")
    list_filter = ("campaign", "institution", "is_public")
    search_fields = ("name",)


@admin.register(Participant)
class ParticipantAdmin(admin.ModelAdmin):
    """Admin configuration for Participant."""

    list_display = ("id", "user", "team", "is_leader", "accepted", "application_date")
    list_filter = ("is_leader", "accepted")


@admin.register(Step)
class StepAdmin(admin.ModelAdmin):
    """Admin configuration for Step."""

    list_display = ("id", "title", "campaign", "type", "order", "optional")
    list_filter = ("campaign", "type")
    search_fields = ("title",)


@admin.register(Sample)
class SampleAdmin(admin.ModelAdmin):
    """Admin configuration for Sample."""

    list_display = ("id", "tree_id", "participant", "area", "completed", "date")
    list_filter = ("completed", "area")
    search_fields = ("tree_id",)


@admin.register(Answer)
class AnswerAdmin(admin.ModelAdmin):
    """Admin configuration for Answer."""

    list_display = ("id", "sample", "step", "date")
    list_filter = ("step",)
