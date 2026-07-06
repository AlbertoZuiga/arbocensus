from django.contrib.auth.password_validation import validate_password
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


class UserAdminSerializer(serializers.ModelSerializer):
    role_display = serializers.CharField(read_only=True)
    password = serializers.CharField(
        write_only=True, required=False, validators=[validate_password]
    )

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
            "is_active",
            "password",
        ]
        read_only_fields = ["id", "role_display"]

    def create(self, validated_data):
        password = validated_data.pop("password")
        return CustomUser.objects.create_user(password=password, **validated_data)

    def update(self, instance, validated_data):
        password = validated_data.pop("password", None)
        user = super().update(instance, validated_data)
        if password:
            user.set_password(password)
            user.save(update_fields=["password"])
        return user

    def validate(self, attrs):
        if not self.instance and not attrs.get("password"):
            raise serializers.ValidationError(
                {"password": "This field is required on create."}
            )
        return attrs
