from rest_framework.permissions import BasePermission

from .models import CustomUser


class IsAdminRole(BasePermission):
    def has_permission(self, request, view):
        return (
            request.user.is_authenticated and request.user.role == CustomUser.Role.ADMIN
        )


class IsSurveyorRole(BasePermission):
    def has_permission(self, request, view):
        return (
            request.user.is_authenticated
            and request.user.role == CustomUser.Role.SURVEYOR
        )
