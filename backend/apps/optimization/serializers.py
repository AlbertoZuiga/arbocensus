from rest_framework import serializers

from .models import OptimizationJob, RoutingConfig, RoutingSolution


class RoutingConfigSerializer(serializers.ModelSerializer):
    class Meta:
        model = RoutingConfig
        fields = [
            "id",
            "dataset",
            "min_route_time_sec",
            "max_route_time_sec",
            "service_time_sec",
            "created_at",
        ]
        read_only_fields = ["id", "created_at"]

    def validate(self, attrs):
        min_time = attrs.get("min_route_time_sec")
        max_time = attrs.get("max_route_time_sec")
        if min_time is not None and max_time is not None and max_time < min_time:
            raise serializers.ValidationError(
                "max_route_time_sec must be greater than or equal to min_route_time_sec"
            )
        return attrs


class OptimizationJobSerializer(serializers.ModelSerializer):
    solution_ids = serializers.SerializerMethodField()

    class Meta:
        model = OptimizationJob
        fields = [
            "id",
            "status",
            "error_message",
            "metrics",
            "started_at",
            "completed_at",
            "solution_ids",
        ]
        read_only_fields = fields

    def get_solution_ids(self, obj):
        return {s.strategy: str(s.id) for s in obj.solutions.all()}


class RoutingSolutionSerializer(serializers.ModelSerializer):
    job = serializers.UUIDField(source="job.id", read_only=True)

    class Meta:
        model = RoutingSolution
        fields = [
            "id",
            "strategy",
            "total_routes",
            "total_travel_time_sec",
            "balance_score",
            "generated_at",
            "job",
        ]
        read_only_fields = fields
