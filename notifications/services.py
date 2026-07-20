from django.db import transaction
from django.utils import timezone

from .models import Notification, NotificationType


class NotificationError(Exception):
    """
    Raised when a notification operation cannot be completed.
    """


class NotificationService:
    @classmethod
    def _validate_recipient(cls, recipient):
        if recipient is None:
            raise NotificationError(
                "A notification recipient is required."
            )

        if recipient.pk is None:
            raise NotificationError(
                "The notification recipient must be saved."
            )

    @classmethod
    def _validate_text(cls, value, field_name):
        value = str(value or "").strip()

        if not value:
            raise NotificationError(
                f"{field_name} is required."
            )

        return value

    @classmethod
    def _validate_notification_type(
        cls,
        notification_type,
    ):
        valid_types = {
            choice[0]
            for choice in NotificationType.choices
        }

        if notification_type not in valid_types:
            raise NotificationError(
                "The selected notification type is invalid."
            )

    @classmethod
    @transaction.atomic
    def create_notification(
        cls,
        *,
        recipient,
        title,
        message,
        notification_type=NotificationType.GENERAL,
    ):
        cls._validate_recipient(
            recipient,
        )

        title = cls._validate_text(
            title,
            "Notification title",
        )

        message = cls._validate_text(
            message,
            "Notification message",
        )

        cls._validate_notification_type(
            notification_type,
        )

        return Notification.objects.create(
            recipient=recipient,
            title=title,
            message=message,
            notification_type=notification_type,
        )

    @classmethod
    def notify_attendance_check_in(
        cls,
        *,
        attendance,
    ):
        if attendance.status == "LATE":
            notification_type = (
                NotificationType.ATTENDANCE_LATE
            )

            title = "Late attendance recorded"

            message = (
                f"Your attendance for "
                f"{attendance.attendance_date:%d %B %Y} "
                f"was recorded as late at "
                f"{attendance.check_in_time:%H:%M}."
            )
        else:
            notification_type = (
                NotificationType.ATTENDANCE_CHECK_IN
            )

            title = "Check-in successful"

            message = (
                f"You successfully checked in on "
                f"{attendance.attendance_date:%d %B %Y} "
                f"at {attendance.check_in_time:%H:%M}."
            )

        if attendance.attendance_location is not None:
            message += (
                f" Location: "
                f"{attendance.attendance_location.name}."
            )

        return cls.create_notification(
            recipient=attendance.intern.user,
            notification_type=notification_type,
            title=title,
            message=message,
        )

    @classmethod
    def notify_attendance_check_out(
        cls,
        *,
        attendance,
    ):
        message = (
            f"You successfully checked out on "
            f"{attendance.attendance_date:%d %B %Y}"
        )

        if attendance.check_out_time is not None:
            message += (
                f" at "
                f"{attendance.check_out_time:%H:%M}"
            )

        message += "."

        if attendance.attendance_location is not None:
            message += (
                f" Location: "
                f"{attendance.attendance_location.name}."
            )

        return cls.create_notification(
            recipient=attendance.intern.user,
            notification_type=(
                NotificationType.ATTENDANCE_CHECK_OUT
            ),
            title="Check-out successful",
            message=message,
        )

    @classmethod
    def notify_attendance_absent(
        cls,
        *,
        attendance,
    ):
        return cls.create_notification(
            recipient=attendance.intern.user,
            notification_type=(
                NotificationType.ATTENDANCE_ABSENT
            ),
            title="Marked absent",
            message=(
                f"You were marked absent for "
                f"{attendance.attendance_date:%d %B %Y} "
                f"in the {attendance.session.name} session."
            ),
        )

    @classmethod
    def notify_attendance_updated(
        cls,
        *,
        attendance,
        reason="",
    ):
        reason = str(reason or "").strip()

        message = (
            f"Your attendance for "
            f"{attendance.attendance_date:%d %B %Y} "
            f"was updated to "
            f"{attendance.get_status_display()}."
        )

        if reason:
            message += (
                f" Reason: {reason}"
            )

        return cls.create_notification(
            recipient=attendance.intern.user,
            notification_type=(
                NotificationType.ATTENDANCE_UPDATED
            ),
            title="Attendance updated",
            message=message,
        )

    @classmethod
    def notify_attendance_deleted(
        cls,
        *,
        recipient,
        attendance_date,
        session_name,
        reason="",
    ):
        reason = str(reason or "").strip()

        message = (
            f"Your attendance record for "
            f"{attendance_date:%d %B %Y} "
            f"in the {session_name} session was deleted."
        )

        if reason:
            message += (
                f" Reason: {reason}"
            )

        return cls.create_notification(
            recipient=recipient,
            notification_type=(
                NotificationType.ATTENDANCE_DELETED
            ),
            title="Attendance record deleted",
            message=message,
        )

    @classmethod
    def notify_gps_rejected(
        cls,
        *,
        recipient,
        reason,
    ):
        reason = cls._validate_text(
            reason,
            "GPS rejection reason",
        )

        return cls.create_notification(
            recipient=recipient,
            notification_type=(
                NotificationType.GPS_REJECTED
            ),
            title="GPS attendance unsuccessful",
            message=reason,
        )

    @classmethod
    @transaction.atomic
    def mark_as_read(
        cls,
        *,
        notification,
        user,
    ):
        if notification.recipient_id != user.pk:
            raise NotificationError(
                "You cannot modify this notification."
            )

        if notification.is_read:
            return notification

        notification.is_read = True
        notification.read_at = timezone.now()

        notification.save(
            update_fields=[
                "is_read",
                "read_at",
                "updated_at",
            ],
        )

        return notification

    @classmethod
    @transaction.atomic
    def mark_as_unread(
        cls,
        *,
        notification,
        user,
    ):
        if notification.recipient_id != user.pk:
            raise NotificationError(
                "You cannot modify this notification."
            )

        notification.is_read = False
        notification.read_at = None

        notification.save(
            update_fields=[
                "is_read",
                "read_at",
                "updated_at",
            ],
        )

        return notification

    @classmethod
    @transaction.atomic
    def mark_all_as_read(
        cls,
        *,
        user,
    ):
        return Notification.objects.filter(
            recipient=user,
            is_read=False,
        ).update(
            is_read=True,
            read_at=timezone.now(),
        )