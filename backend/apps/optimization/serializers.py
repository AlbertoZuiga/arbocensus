from rest_framework import serializers

from .models import OptimizationJob, RoutingConfig, RoutingSolution


class RoutingConfigSerializer(serializers.ModelSerializer):
    strategy = serializers.ChoiceField(
        choices=OptimizationJob.Strategy.choices,
        default=OptimizationJob.Strategy.SPATIAL_TERM,
    )

    class Meta:
        model = RoutingConfig
        fields = [
            "id",
            "dataset",
            "min_route_time_sec",
            "max_route_time_sec",
            "service_time_sec",
            "strategy",
            "created_at",
        ]
        read_only_fields = ["id", "created_at"]

    def create(self, validated_data):
        validated_data.pop("strategy", None)
        return super().create(validated_data)

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
            "strategy",
            "status",
            "error_message",
            "metrics",
            "created_at",
            "started_at",
            "completed_at",
            "solution_ids",
        ]
        read_only_fields = fields

    def get_solution_ids(self, obj):
        return {s.strategy: str(s.id) for s in obj.solutions.all()}


class RoutingSolutionSerializer(serializers.ModelSerializer):
    job = serializers.UUIDField(source="job.id", read_only=True)
    dataset = serializers.UUIDField(source="dataset.id", read_only=True)
    total_service_time_sec = serializers.SerializerMethodField()
    total_time_sec = serializers.SerializerMethodField()

    class Meta:
        model = RoutingSolution
        fields = [
            "id",
            "strategy",
            "total_routes",
            "total_travel_time_sec",
            "total_service_time_sec",
            "total_time_sec",
            "balance_score",
            "sum_max_radius_m",
            "interleave_total",
            "interleave_per_route",
            "worst_pair_iou",
            "timing",
            "generated_at",
            "published_at",
            "job",
            "dataset",
        ]
        read_only_fields = fields

    def get_total_service_time_sec(self, obj):
        total_trees = sum(route.total_trees for route in obj.routes.all())
        return total_trees * obj.job.config.service_time_sec

    def get_total_time_sec(self, obj):
        return obj.total_travel_time_sec + self.get_total_service_time_sec(obj)
