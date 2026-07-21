from django.contrib.auth import get_user_model
from rest_framework import serializers

from .models import Route, RouteStop, TreeObservation

CustomUser = get_user_model()


class DatasetQuerySerializer(serializers.Serializer):
    dataset = serializers.UUIDField()


class RouteAssignSerializer(serializers.Serializer):
    surveyor_id = serializers.PrimaryKeyRelatedField(
        queryset=CustomUser.objects.filter(role=CustomUser.Role.SURVEYOR),
        allow_null=True,
    )


class TreeObservationInputSerializer(serializers.Serializer):
    status = serializers.ChoiceField(
        choices=TreeObservation.Status.choices, required=False
    )
    photo = serializers.ImageField(required=False, allow_null=True)
    notes = serializers.CharField(required=False, allow_blank=True)
    lat = serializers.FloatField(
        required=False, allow_null=True, min_value=-90.0, max_value=90.0
    )
    lon = serializers.FloatField(
        required=False, allow_null=True, min_value=-180.0, max_value=180.0
    )

    def validate(self, attrs):
        if (attrs.get("lat") is None) != (attrs.get("lon") is None):
            raise serializers.ValidationError("lat y lon deben enviarse juntos.")
        return attrs


class TreeObservationSerializer(serializers.ModelSerializer):
    created_by_username = serializers.SerializerMethodField()

    class Meta:
        model = TreeObservation
        fields = [
            "id",
            "tree",
            "route_stop",
            "status",
            "source",
            "photo",
            "photo_url",
            "notes",
            "created_by",
            "created_by_username",
            "observed_at",
        ]
        read_only_fields = fields

    def get_created_by_username(self, obj):
        return obj.created_by.username if obj.created_by_id else None


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
    total_service_time_sec = serializers.SerializerMethodField()
    visited_count = serializers.IntegerField(read_only=True)
    pending_count = serializers.IntegerField(read_only=True)
    skipped_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = Route
        fields = [
            "id",
            "route_number",
            "total_trees",
            "travel_time_sec",
            "total_service_time_sec",
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

    def get_total_service_time_sec(self, obj):
        return obj.total_estimated_time_sec - obj.travel_time_sec


class RouteDetailSerializer(RouteSerializer):
    stops = RouteStopSerializer(many=True, read_only=True)

    class Meta(RouteSerializer.Meta):
        fields = RouteSerializer.Meta.fields + ["stops"]
