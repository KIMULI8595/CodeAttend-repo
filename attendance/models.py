from django.conf import settings
from django.core.validators import (
    MaxValueValidator,
    MinValueValidator,
)
from django.db import models

from interns.models import Batch, InternProfile, Session


class AttendanceStatus(models.TextChoices):
    PRESENT = "PRESENT", "Present"
    LATE = "LATE", "Late"
    ABSENT = "ABSENT", "Absent"


class AttendanceMethod(models.TextChoices):
    GPS = "GPS", "GPS"
    QR = "QR", "QR Code"
    MANUAL = "MANUAL", "Manual"
    AUTOMATIC = "AUTOMATIC", "Automatic"


class AttendanceLocation(models.Model):
    name = models.CharField(
        max_length=150,
        unique=True,
    )

    latitude = models.DecimalField(
        max_digits=10,
        decimal_places=6,
        validators=[
            MinValueValidator(-90),
            MaxValueValidator(90),
        ],
    )

    longitude = models.DecimalField(
        max_digits=10,
        decimal_places=6,
        validators=[
            MinValueValidator(-180),
            MaxValueValidator(180),
        ],
    )

    radius_metres = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=100,
        validators=[
            MinValueValidator(1),
        ],
        help_text=(
            "Maximum permitted distance from this location, "
            "measured in metres."
        ),
    )

    maximum_accuracy_metres = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=50,
        validators=[
            MinValueValidator(1),
        ],
        help_text=(
            "Maximum acceptable browser GPS accuracy, "
            "measured in metres."
        ),
    )

    is_active = models.BooleanField(
        default=True,
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    updated_at = models.DateTimeField(
        auto_now=True,
    )

    class Meta:
        ordering = [
            "name",
        ]

    def __str__(self):
        return self.name


class Attendance(models.Model):
    intern = models.ForeignKey(
        InternProfile,
        on_delete=models.CASCADE,
        related_name="attendance",
    )

    batch = models.ForeignKey(
        Batch,
        on_delete=models.PROTECT,
        related_name="attendance",
    )

    session = models.ForeignKey(
        Session,
        on_delete=models.PROTECT,
        related_name="attendance",
    )

    attendance_location = models.ForeignKey(
        AttendanceLocation,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="attendance_records",
    )

    attendance_date = models.DateField()

    check_in_time = models.TimeField(
        null=True,
        blank=True,
    )

    check_out_time = models.TimeField(
        null=True,
        blank=True,
    )

    check_in_latitude = models.DecimalField(
        max_digits=10,
        decimal_places=6,
        null=True,
        blank=True,
        validators=[
            MinValueValidator(-90),
            MaxValueValidator(90),
        ],
    )

    check_in_longitude = models.DecimalField(
        max_digits=10,
        decimal_places=6,
        null=True,
        blank=True,
        validators=[
            MinValueValidator(-180),
            MaxValueValidator(180),
        ],
    )

    check_in_accuracy = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[
            MinValueValidator(0),
        ],
        help_text="GPS accuracy in metres.",
    )

    check_out_latitude = models.DecimalField(
        max_digits=10,
        decimal_places=6,
        null=True,
        blank=True,
        validators=[
            MinValueValidator(-90),
            MaxValueValidator(90),
        ],
    )

    check_out_longitude = models.DecimalField(
        max_digits=10,
        decimal_places=6,
        null=True,
        blank=True,
        validators=[
            MinValueValidator(-180),
            MaxValueValidator(180),
        ],
    )

    check_out_accuracy = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[
            MinValueValidator(0),
        ],
        help_text="GPS accuracy in metres.",
    )

    attendance_method = models.CharField(
        max_length=20,
        choices=AttendanceMethod.choices,
        default=AttendanceMethod.QR,
    )

    status = models.CharField(
        max_length=20,
        choices=AttendanceStatus.choices,
        default=AttendanceStatus.PRESENT,
    )

    recorded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="recorded_attendance",
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    updated_at = models.DateTimeField(
        auto_now=True,
    )

    class Meta:
        ordering = [
            "-attendance_date",
            "-check_in_time",
        ]

        constraints = [
            models.UniqueConstraint(
                fields=[
                    "intern",
                    "session",
                    "attendance_date",
                ],
                name="unique_intern_session_attendance_date",
            ),
        ]

        indexes = [
            models.Index(
                fields=[
                    "attendance_date",
                    "status",
                ],
            ),
            models.Index(
                fields=[
                    "batch",
                    "attendance_date",
                ],
            ),
            models.Index(
                fields=[
                    "session",
                    "attendance_date",
                ],
            ),
            models.Index(
                fields=[
                    "attendance_method",
                    "attendance_date",
                ],
            ),
        ]

    def __str__(self):
        return (
            f"{self.intern} - "
            f"{self.attendance_date} - "
            f"{self.get_status_display()}"
        )

    @property
    def has_checked_in(self):
        return self.check_in_time is not None

    @property
    def has_checked_out(self):
        return self.check_out_time is not None


class AttendanceAuditAction(models.TextChoices):
    CREATED = "CREATED", "Created"
    UPDATED = "UPDATED", "Updated"
    DELETED = "DELETED", "Deleted"


class AttendanceAudit(models.Model):
    attendance = models.ForeignKey(
        Attendance,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="audit_logs",
    )

    intern = models.ForeignKey(
        InternProfile,
        on_delete=models.PROTECT,
        related_name="attendance_audits",
    )

    batch = models.ForeignKey(
        Batch,
        on_delete=models.PROTECT,
        related_name="attendance_audits",
    )

    session = models.ForeignKey(
        Session,
        on_delete=models.PROTECT,
        related_name="attendance_audits",
    )

    attendance_date = models.DateField()

    action = models.CharField(
        max_length=20,
        choices=AttendanceAuditAction.choices,
    )

    previous_status = models.CharField(
        max_length=20,
        choices=AttendanceStatus.choices,
        null=True,
        blank=True,
    )

    new_status = models.CharField(
        max_length=20,
        choices=AttendanceStatus.choices,
        null=True,
        blank=True,
    )

    previous_check_in_time = models.TimeField(
        null=True,
        blank=True,
    )

    new_check_in_time = models.TimeField(
        null=True,
        blank=True,
    )

    previous_check_out_time = models.TimeField(
        null=True,
        blank=True,
    )

    new_check_out_time = models.TimeField(
        null=True,
        blank=True,
    )

    previous_attendance_method = models.CharField(
        max_length=20,
        choices=AttendanceMethod.choices,
        null=True,
        blank=True,
    )

    new_attendance_method = models.CharField(
        max_length=20,
        choices=AttendanceMethod.choices,
        null=True,
        blank=True,
    )

    reason = models.TextField(
        blank=True,
    )

    performed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="attendance_audit_actions",
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    class Meta:
        ordering = [
            "-created_at",
        ]

        indexes = [
            models.Index(
                fields=[
                    "action",
                    "created_at",
                ],
            ),
            models.Index(
                fields=[
                    "intern",
                    "attendance_date",
                ],
            ),
        ]

    def __str__(self):
        return (
            f"{self.get_action_display()} - "
            f"{self.intern} - "
            f"{self.attendance_date}"
        )