import uuid

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models


class BatchStatus(models.TextChoices):
    UPCOMING = "UPCOMING", "Upcoming"
    ACTIVE = "ACTIVE", "Active"
    COMPLETED = "COMPLETED", "Completed"
    CANCELLED = "CANCELLED", "Cancelled"


class Batch(models.Model):
    name = models.CharField(max_length=100, unique=True)
    start_date = models.DateField()
    end_date = models.DateField()
    status = models.CharField(
        max_length=20,
        choices=BatchStatus.choices,
        default=BatchStatus.UPCOMING,
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-start_date"]

    def clean(self):
        super().clean()
        if self.start_date and self.end_date and self.end_date < self.start_date:
            raise ValidationError({"end_date": "End date cannot be before start date."})

    def __str__(self):
        return self.name


class Session(models.Model):
    name = models.CharField(max_length=50, unique=True)
    start_time = models.TimeField()
    end_time = models.TimeField()
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["start_time"]

    def clean(self):
        super().clean()
        if self.start_time and self.end_time and self.end_time <= self.start_time:
            raise ValidationError({"end_time": "End time must be later than start time."})

    def __str__(self):
        return self.name


class InternProfile(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="intern_profile",
    )
    student_number = models.CharField(max_length=50, unique=True)
    university = models.CharField(max_length=150)
    course = models.CharField(max_length=150)
    batch = models.ForeignKey(Batch, on_delete=models.PROTECT, null=True, blank=True)
    session = models.ForeignKey(Session, on_delete=models.PROTECT, null=True, blank=True)
    qr_code = models.UUIDField(unique=True, editable=False, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["student_number"]

    @property
    def is_assigned(self):
        return self.batch_id is not None and self.session_id is not None

    @property
    def is_approved(self):
        return self.user.is_active and self.user.account_status == "ACTIVE"

    def ensure_qr_code(self):
        if not self.qr_code:
            self.qr_code = uuid.uuid4()
            self.save(update_fields=["qr_code"])
        return self.qr_code

    def clean(self):
        super().clean()
        self.student_number = self.student_number.strip().upper()
        if self.batch_id and self.batch.status == BatchStatus.CANCELLED:
            raise ValidationError({"batch": "An intern cannot be assigned to a cancelled batch."})
        if self.session_id and not self.session.is_active:
            raise ValidationError({"session": "An intern cannot be assigned to an inactive session."})

    def __str__(self):
        return self.user.full_name or self.user.email


class ApprovalAction(models.TextChoices):
    APPROVED = "APPROVED", "Approved"
    REJECTED = "REJECTED", "Rejected"


class ApprovalRecord(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="approval_record",
    )
    action = models.CharField(max_length=20, choices=ApprovalAction.choices)
    performed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="approval_actions",
    )
    reason = models.TextField(blank=True)
    performed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-performed_at"]

    def clean(self):
        super().clean()
        if self.action == ApprovalAction.REJECTED and not self.reason.strip():
            raise ValidationError({"reason": "A rejection reason is required."})

    def __str__(self):
        return f"{self.user.full_name or self.user.email} - {self.get_action_display()}"
