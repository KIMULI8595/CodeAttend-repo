from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import User


@admin.register(User)
class CustomUserAdmin(UserAdmin):

    model = User

    list_display = (
        "email",
        "first_name",
        "last_name",
        "account_status",
        "is_staff",
        "is_active",
    )

    ordering = (
        "email",
    )

    readonly_fields = (
        "created_at",
        "updated_at",
        "last_login",
    )

    fieldsets = (
        (
            "Login Information",
            {
                "fields": (
                    "email",
                    "password",
                )
            }
        ),

        (
            "Personal Information",
            {
                "fields": (
                    "first_name",
                    "last_name",
                    "phone_number",
                    "profile_photo",
                )
            }
        ),

        (
            "Account Status",
            {
                "fields": (
                    "account_status",
                    "is_active",
                    "is_staff",
                    "is_superuser",
                )
            }
        ),

        (
            "Permissions",
            {
                "fields": (
                    "groups",
                    "user_permissions",
                )
            }
        ),

        (
            "Important Dates",
            {
                "fields": (
                    "last_login",
                    "created_at",
                    "updated_at",
                )
            }
        ),
    )

    add_fieldsets = (
        (
            "Create User",
            {
                "classes": (
                    "wide",
                ),
                "fields": (
                    "email",
                    "first_name",
                    "last_name",
                    "phone_number",
                    "password1",
                    "password2",
                ),
            }
        ),
    )