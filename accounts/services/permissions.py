from django.core.exceptions import PermissionDenied


class PermissionService:

    @staticmethod
    def require_admin(user):
        if not user.is_superuser:
            raise PermissionDenied(
                "Administrator privileges required."
            )

    @staticmethod
    def require_staff(user):
        if not user.is_staff:
            raise PermissionDenied(
                "Staff privileges required."
            )

    @staticmethod
    def require_authenticated(user):
        if not user.is_authenticated:
            raise PermissionDenied(
                "Authentication required."
            )