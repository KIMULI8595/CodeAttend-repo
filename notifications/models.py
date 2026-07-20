from django.conf import settings
from django.db import models


class NotificationType(models.TextChoices):
    ATTENDANCE_CHECK_IN = (
        "ATTENDANCE_CHECK_IN",
        "Attendance check-in",
    )

    ATTENDANCE_CHECK_OUT = (
        "ATTENDANCE_CHECK_OUT",
        "Attendance check-out",
    )

    ATTENDANCE_LATE = (
        "ATTENDANCE_LATE",
        "Late attendance",
    )

    ATTENDANCE_ABSENT = (
        "ATTENDANCE_ABSENT",
        "Absent attendance",
    )

    ATTENDANCE_UPDATED = (
        "ATTENDANCE_UPDATED",
        "Attendance updated",
    )

    ATTENDANCE_DELETED = (
        "ATTENDANCE_DELETED",
        "Attendance deleted",
    )

    GPS_REJECTED = (
        "GPS_REJECTED",
        "GPS attendance rejected",
    )

    GENERAL = (
        "GENERAL",
        "General",
    )


class Notification(models.Model):
    recipient = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="notifications",
    )

    notification_type = models.CharField(
        max_length=40,
        choices=NotificationType.choices,
        default=NotificationType.GENERAL,
    )

    title = models.CharField(
        max_length=150,
    )

    message = models.TextField()

    is_read = models.BooleanField(
        default=False,
    )

    read_at = models.DateTimeField(
        null=True,
        blank=True,
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    updated_at = models.DateTimeField(
        auto_now=True,
    )

    class Meta:
        ordering = [
            "-created_at",
        ]

        indexes = [
            models.Index(
                fields=[
                    "recipient",
                    "is_read",
                    "created_at",
                ],
            ),
            models.Index(
                fields=[
                    "notification_type",
                    "created_at",
                ],
            ),
        ]

    def __str__(self):
        return (
            f"{self.recipient} - "
            f"{self.title}"
        )