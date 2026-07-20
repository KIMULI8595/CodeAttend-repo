from django.db import transaction

from accounts.models import AccountStatus
from core.exceptions import InvalidApprovalError
from interns.models import ApprovalAction, ApprovalRecord
from notifications.models import NotificationType
from notifications.services import NotificationService


class ApprovalService:
    @staticmethod
    @transaction.atomic
    def approve_intern(user, performed_by, reason=""):
        if user.account_status != AccountStatus.PENDING:
            raise InvalidApprovalError("Only pending interns can be approved.")
        try:
            profile = user.intern_profile
        except AttributeError as exc:
            raise InvalidApprovalError("The selected user is not an intern.") from exc

        user.account_status = AccountStatus.ACTIVE
        user.is_active = True
        user.save(update_fields=["account_status", "is_active", "updated_at"])
        profile.ensure_qr_code()
        ApprovalRecord.objects.update_or_create(
            user=user,
            defaults={
                "action": ApprovalAction.APPROVED,
                "performed_by": performed_by,
                "reason": reason.strip(),
            },
        )
        NotificationService.create_notification(
            recipient=user,
            notification_type=NotificationType.GENERAL,
            title="Registration approved",
            message="Your CodeAttend registration has been approved. You may now sign in and record attendance.",
        )
        return user

    @staticmethod
    @transaction.atomic
    def reject_intern(user, performed_by, reason):
        reason = reason.strip()
        if user.account_status != AccountStatus.PENDING:
            raise InvalidApprovalError("Only pending interns can be rejected.")
        if not reason:
            raise InvalidApprovalError("A rejection reason is required.")

        user.account_status = AccountStatus.REJECTED
        user.is_active = False
        user.save(update_fields=["account_status", "is_active", "updated_at"])
        ApprovalRecord.objects.update_or_create(
            user=user,
            defaults={
                "action": ApprovalAction.REJECTED,
                "performed_by": performed_by,
                "reason": reason,
            },
        )
        NotificationService.create_notification(
            recipient=user,
            notification_type=NotificationType.GENERAL,
            title="Registration not approved",
            message=f"Your CodeAttend registration was not approved. Reason: {reason}",
        )
        return user
