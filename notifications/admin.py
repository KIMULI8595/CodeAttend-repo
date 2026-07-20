from django.contrib import admin
from django.utils.html import format_html

from .models import Notification, NotificationType


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = (
        "title",
        "recipient",
        "notification_type_badge",
        "read_status_badge",
        "created_at",
    )

    list_filter = (
        "notification_type",
        "is_read",
        "created_at",
    )

    search_fields = (
        "title",
        "message",
        "recipient__email",
        "recipient__first_name",
        "recipient__last_name",
    )

    readonly_fields = (
        "created_at",
        "updated_at",
        "read_at",
    )

    autocomplete_fields = (
        "recipient",
    )

    ordering = (
        "-created_at",
    )

    date_hierarchy = "created_at"

    list_select_related = (
        "recipient",
    )

    fieldsets = (
        (
            "Recipient",
            {
                "fields": (
                    "recipient",
                ),
            },
        ),
        (
            "Notification",
            {
                "fields": (
                    "notification_type",
                    "title",
                    "message",
                ),
            },
        ),
        (
            "Status",
            {
                "fields": (
                    "is_read",
                    "read_at",
                ),
            },
        ),
        (
            "System information",
            {
                "fields": (
                    "created_at",
                    "updated_at",
                ),
            },
        ),
    )

    @admin.display(
        description="Type",
        ordering="notification_type",
    )
    def notification_type_badge(self, obj):
        badge_styles = {
            NotificationType.ATTENDANCE_CHECK_IN: (
                "background:#dcfce7;color:#166534;"
            ),
            NotificationType.ATTENDANCE_CHECK_OUT: (
                "background:#dbeafe;color:#1e40af;"
            ),
            NotificationType.ATTENDANCE_LATE: (
                "background:#fef3c7;color:#92400e;"
            ),
            NotificationType.ATTENDANCE_ABSENT: (
                "background:#fee2e2;color:#991b1b;"
            ),
            NotificationType.ATTENDANCE_UPDATED: (
                "background:#ede9fe;color:#5b21b6;"
            ),
            NotificationType.ATTENDANCE_DELETED: (
                "background:#fee2e2;color:#991b1b;"
            ),
            NotificationType.GPS_REJECTED: (
                "background:#ffedd5;color:#9a3412;"
            ),
            NotificationType.GENERAL: (
                "background:#e5e7eb;color:#374151;"
            ),
        }

        style = badge_styles.get(
            obj.notification_type,
            "background:#e5e7eb;color:#374151;",
        )

        return format_html(
            '<span style="{}padding:4px 10px;'
            'border-radius:999px;font-weight:600;">{}</span>',
            style,
            obj.get_notification_type_display(),
        )

    @admin.display(
        description="Read status",
        ordering="is_read",
    )
    def read_status_badge(self, obj):
        if obj.is_read:
            style = (
                "background:#e5e7eb;color:#374151;"
            )

            label = "Read"
        else:
            style = (
                "background:#dbeafe;color:#1e40af;"
            )

            label = "Unread"

        return format_html(
            '<span style="{}padding:4px 10px;'
            'border-radius:999px;font-weight:600;">{}</span>',
            style,
            label,
        )