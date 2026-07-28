from rest_framework import serializers

from .config_presets import CONFIG_PRESETS
from .models import OptimizationJob, RoutingConfig, RoutingSolution
from .recommendation import BALANCE_GATE, pick_recommended


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
            "config",
            "strategy",
            "config_preset",
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
    config = serializers.UUIDField(source="job.config_id", read_only=True)
    total_service_time_sec = serializers.SerializerMethodField()
    total_time_sec = serializers.SerializerMethodField()
    config_preset = serializers.SerializerMethodField()
    config_preset_label = serializers.SerializerMethodField()
    balance_below_gate = serializers.SerializerMethodField()
    recommended = serializers.SerializerMethodField()

    class Meta:
        model = RoutingSolution
        fields = [
            "id",
            "strategy",
            "config_preset",
            "config_preset_label",
            "total_routes",
            "total_travel_time_sec",
            "total_service_time_sec",
            "total_time_sec",
            "balance_score",
            "balance_below_gate",
            "dropped_trees",
            "degenerate_routes",
            "sum_max_radius_m",
            "interleave_total",
            "interleave_per_route",
            "worst_pair_iou",
            "timing",
            "generated_at",
            "published_at",
            "recommended",
            "job",
            "dataset",
            "config",
        ]
        read_only_fields = fields

    def get_total_service_time_sec(self, obj):
        total_trees = sum(route.total_trees for route in obj.routes.all())
        return total_trees * obj.job.config.service_time_sec

    def get_total_time_sec(self, obj):
        return obj.total_travel_time_sec + self.get_total_service_time_sec(obj)

    def get_config_preset(self, obj):
        return obj.job.config_preset

    def get_config_preset_label(self, obj):
        return CONFIG_PRESETS[obj.job.config_preset]["label"]

    def get_balance_below_gate(self, obj):
        return obj.balance_score < BALANCE_GATE

    def get_recommended(self, obj):
        if "recommended_solution_id" in self.context:
            return self.context["recommended_solution_id"] == obj.id
        if "recommended_by_dataset" in self.context:
            return self.context["recommended_by_dataset"].get(obj.dataset_id) == obj.id
        return pick_recommended(obj.dataset_id) == obj.id
