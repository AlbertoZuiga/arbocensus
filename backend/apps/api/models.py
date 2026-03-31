"""Django models for the arbocensus API, mirroring the existing database schema."""

from django.contrib.auth.models import (
    AbstractBaseUser,
    BaseUserManager,
    PermissionsMixin,
)
from django.contrib.postgres.fields import ArrayField
from django.db import models


class UserManager(BaseUserManager):
    """Manager for the custom User model."""

    def create_user(self, username, email, password=None, **extra_fields):
        """Create and return a regular user."""
        if not username:
            raise ValueError("Username is required.")
        if not email:
            raise ValueError("Email is required.")

        email = self.normalize_email(email)
        user = self.model(username=username, email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, username, email, password=None, **extra_fields):
        """Create and return a superuser."""
        extra_fields.setdefault("is_superuser", True)
        extra_fields.setdefault("is_active", True)
        extra_fields.setdefault("is_verified", True)
        if extra_fields.get("is_superuser") is not True:
            raise ValueError("Superuser must have is_superuser=True.")
        if extra_fields.get("is_active") is not True:
            raise ValueError("Superuser must have is_active=True.")

        return self.create_user(username, email, password, **extra_fields)


class User(AbstractBaseUser, PermissionsMixin):
    """Custom user model matching arbocensus_api_app_user table.

    Extends AbstractBaseUser and PermissionsMixin to support Django's
    built-in permission system while using a custom schema.
    """

    username = models.CharField(max_length=255, unique=True)
    email = models.EmailField(max_length=255)
    is_verified = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)

    objects = UserManager()

    USERNAME_FIELD = "username"
    REQUIRED_FIELDS = ["email"]

    # Required by Django admin
    @property
    def is_staff(self):
        """Return True for superusers to grant admin access."""
        return self.is_superuser

    def __str__(self):
        return self.username

    class Meta:
        db_table = "arbocensus_api_app_user"


class Institution(models.Model):
    """Represents an institution that sponsors or participates in campaigns."""

    name = models.TextField()
    logo_url = models.TextField()

    def __str__(self):
        return self.name

    class Meta:
        db_table = "arbocensus_api_app_institution"


class Sponsor(models.Model):
    """Represents a campaign sponsor with branding information."""

    name = models.TextField()
    main_color = models.TextField()
    logo_url = models.TextField()

    def __str__(self):
        return self.name

    class Meta:
        db_table = "arbocensus_api_app_sponsor"


class Campaign(models.Model):
    """Represents a tree census campaign with a defined time window and configuration."""

    name = models.TextField()
    description = models.TextField()
    start_date = models.DateTimeField()
    end_date = models.DateTimeField()
    qr_step_enabled = models.BooleanField(default=False)
    image_resolution = models.IntegerField()
    sponsor = models.ForeignKey(
        Sponsor,
        on_delete=models.PROTECT,
        related_name="campaigns",
    )

    def __str__(self):
        return self.name

    class Meta:
        db_table = "arbocensus_api_app_campaign"


class Area(models.Model):
    """Represents a geographic area assigned to a campaign."""

    name = models.TextField()
    points_per_sample = models.IntegerField()
    coordinates = ArrayField(models.FloatField())
    campaign = models.ForeignKey(
        Campaign,
        on_delete=models.CASCADE,
        related_name="areas",
    )

    def __str__(self):
        return self.name

    class Meta:
        db_table = "arbocensus_api_app_area"


class Team(models.Model):
    """Represents a group of participants within a campaign."""

    name = models.TextField()
    is_public = models.BooleanField(default=True)
    campaign = models.ForeignKey(
        Campaign,
        on_delete=models.CASCADE,
        related_name="teams",
    )
    institution = models.ForeignKey(
        Institution,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="teams",
    )
    avatar = models.CharField(max_length=255, blank=True)
    color = models.TextField()

    def __str__(self):
        return self.name

    class Meta:
        db_table = "arbocensus_api_app_team"


class Participant(models.Model):
    """Represents a user's membership in a team, including leadership and acceptance state."""

    is_leader = models.BooleanField(default=False)
    application_date = models.DateField()
    resolution_date = models.DateField(null=True, blank=True)
    accepted = models.BooleanField(null=True, blank=True)
    team = models.ForeignKey(
        Team,
        on_delete=models.CASCADE,
        related_name="participants",
    )
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="participations",
    )

    def __str__(self):
        return f"{self.user} @ {self.team}"

    class Meta:
        db_table = "arbocensus_api_app_participant"


class Step(models.Model):
    """Represents a single step within a campaign's data collection workflow."""

    type = models.CharField(max_length=1)
    order = models.IntegerField()
    optional = models.BooleanField(default=False)
    title = models.TextField()
    description = models.TextField()
    alternatives = models.CharField(max_length=200, blank=True)
    example_image_url = models.TextField(blank=True)
    campaign = models.ForeignKey(
        Campaign,
        on_delete=models.CASCADE,
        related_name="steps",
    )
    drawable_description = models.TextField(blank=True)
    is_image_drawable = models.BooleanField(default=False)
    is_image_croppable = models.BooleanField(default=False)
    mask_url = models.TextField(blank=True)
    data_type = models.CharField(max_length=30, blank=True)
    suffix = models.TextField(blank=True)

    def __str__(self):
        return f"{self.order}. {self.title}"

    class Meta:
        db_table = "arbocensus_api_app_step"


class Sample(models.Model):
    """Represents a single field observation of a tree by a participant."""

    date = models.DateTimeField()
    tree_id = models.TextField()
    tree_latitude = models.FloatField()
    tree_longitude = models.FloatField()
    completed = models.BooleanField(default=False)
    score = models.IntegerField(null=True, blank=True)
    area = models.ForeignKey(
        Area,
        on_delete=models.PROTECT,
        related_name="samples",
    )
    participant = models.ForeignKey(
        Participant,
        on_delete=models.PROTECT,
        related_name="samples",
    )
    user_latitude = models.FloatField(null=True, blank=True)
    user_longitude = models.FloatField(null=True, blank=True)

    def __str__(self):
        return self.tree_id

    class Meta:
        db_table = "arbocensus_api_app_sample"


class Answer(models.Model):
    """Represents a participant's response to a single step within a sample."""

    date = models.DateTimeField()
    answer_text = models.TextField(blank=True)
    answer_url = models.CharField(max_length=300, blank=True)
    sample = models.ForeignKey(
        Sample,
        on_delete=models.CASCADE,
        related_name="answers",
    )
    step = models.ForeignKey(
        Step,
        on_delete=models.PROTECT,
        related_name="answers",
    )
    answer_mark = models.TextField(blank=True)
    crop_url = models.CharField(max_length=300, blank=True)
    current_latitude = models.FloatField(null=True, blank=True)
    current_longitude = models.FloatField(null=True, blank=True)
    device = models.TextField(blank=True)

    def __str__(self):
        return f"Answer #{self.pk}"

    class Meta:
        db_table = "arbocensus_api_app_answer"


class PipelineRun(models.Model):
    """Tracks a complete execution of the tree census pipeline."""

    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        RUNNING = "running", "Running"
        COMPLETED = "completed", "Completed"
        FAILED = "failed", "Failed"

    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.PENDING
    )

    # Bounding box input
    bbox_north = models.FloatField()
    bbox_south = models.FloatField()
    bbox_east = models.FloatField()
    bbox_west = models.FloatField()

    # Pipeline parameters
    expected_duration_min = models.FloatField(default=150.0)
    time_per_tree_min = models.FloatField(default=2.0)

    # Metadata
    tree_count = models.IntegerField(null=True, blank=True)
    route_count = models.IntegerField(null=True, blank=True)
    error_message = models.TextField(blank=True)

    # Results stored as JSON
    routes_geojson = models.JSONField(null=True, blank=True)
    clusters_geojson = models.JSONField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"PipelineRun #{self.pk} ({self.status})"

    class Meta:
        ordering = ["-created_at"]
