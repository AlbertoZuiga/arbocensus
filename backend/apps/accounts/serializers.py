from rest_framework import serializers

from .models import CustomUser


class CustomUserSerializer(serializers.ModelSerializer):
    role_display = serializers.CharField(read_only=True)

    class Meta:
        model = CustomUser
        fields = ["id", "username", "email", "role", "role_display"]
        read_only_fields = ["id", "username", "email", "role", "role_display"]


class SurveyorSerializer(serializers.ModelSerializer):
    role_display = serializers.CharField(read_only=True)

    class Meta:
        model = CustomUser
        fields = [
            "id",
            "username",
            "first_name",
            "last_name",
            "email",
            "role",
            "role_display",
        ]
        read_only_fields = fields
