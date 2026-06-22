from rest_framework import serializers

from .models import Route, RouteStop


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
            "visited",
            "visited_at",
            "notes",
        ]
        read_only_fields = fields


class RouteSerializer(serializers.ModelSerializer):
    class Meta:
        model = Route
        fields = [
            "id",
            "route_number",
            "total_trees",
            "travel_time_sec",
            "total_estimated_time_sec",
            "surveyor",
        ]
        read_only_fields = fields


class RouteDetailSerializer(RouteSerializer):
    stops = RouteStopSerializer(many=True, read_only=True)

    class Meta(RouteSerializer.Meta):
        fields = RouteSerializer.Meta.fields + ["stops"]
