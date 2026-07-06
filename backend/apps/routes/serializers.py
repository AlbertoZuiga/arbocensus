from django.contrib.auth import get_user_model
from rest_framework import serializers

from .models import Route, RouteStop

CustomUser = get_user_model()


class RouteAssignSerializer(serializers.Serializer):
    surveyor_id = serializers.PrimaryKeyRelatedField(
        queryset=CustomUser.objects.filter(role=CustomUser.Role.SURVEYOR),
        allow_null=True,
    )


class RouteStopSerializer(serializers.ModelSerializer):
    tree_id = serializers.UUIDField(source="tree.id", read_only=True)
    lon = serializers.FloatField(source="tree.location.x", read_only=True)
    lat = serializers.FloatField(source="tree.location.y", read_only=True)

    class Meta:
        model = RouteStop
        fields = [
            "id",
            "sequence",
            "tree_id",
            "lon",
            "lat",
            "status",
            "visited",
            "visited_at",
            "skip_reason",
            "notes",
        ]
        read_only_fields = fields


class RouteSerializer(serializers.ModelSerializer):
    surveyor_name = serializers.SerializerMethodField()
    visited_count = serializers.SerializerMethodField()
    pending_count = serializers.SerializerMethodField()
    skipped_count = serializers.SerializerMethodField()

    class Meta:
        model = Route
        fields = [
            "id",
            "route_number",
            "total_trees",
            "travel_time_sec",
            "total_estimated_time_sec",
            "surveyor",
            "surveyor_name",
            "visited_count",
            "pending_count",
            "skipped_count",
        ]
        read_only_fields = fields

    def get_surveyor_name(self, obj):
        return obj.surveyor.username if obj.surveyor_id else None

    def get_visited_count(self, obj):
        return sum(1 for stop in obj.stops.all() if stop.visited)

    def get_pending_count(self, obj):
        return sum(
            1 for stop in obj.stops.all() if stop.status == RouteStop.Status.PENDING
        )

    def get_skipped_count(self, obj):
        return sum(
            1 for stop in obj.stops.all() if stop.status == RouteStop.Status.SKIPPED
        )


class RouteDetailSerializer(RouteSerializer):
    stops = RouteStopSerializer(many=True, read_only=True)

    class Meta(RouteSerializer.Meta):
        fields = RouteSerializer.Meta.fields + ["stops"]
