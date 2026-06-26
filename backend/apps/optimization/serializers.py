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
        if attrs["max_route_time_sec"] < attrs["min_route_time_sec"]:
            raise serializers.ValidationError(
                "max_route_time_sec must be greater than or equal to min_route_time_sec"
            )
        return attrs


class OptimizationJobSerializer(serializers.ModelSerializer):
    solution_id = serializers.SerializerMethodField()

    class Meta:
        model = OptimizationJob
        fields = [
            "id",
            "status",
            "error_message",
            "metrics",
            "started_at",
            "completed_at",
            "solution_id",
        ]
        read_only_fields = fields

    def get_solution_id(self, obj):
        try:
            return obj.solution.id
        except RoutingSolution.DoesNotExist:
            return None


class RoutingSolutionSerializer(serializers.ModelSerializer):
    job = serializers.UUIDField(source="job.id", read_only=True)

    class Meta:
        model = RoutingSolution
        fields = [
            "id",
            "total_routes",
            "total_travel_time_sec",
            "balance_score",
            "generated_at",
            "job",
        ]
        read_only_fields = fields
