from datetime import datetime, timedelta

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from accounts.models import AccountStatus
from interns.models import InternProfile
from notifications.services import NotificationService

from attendance.models import (
    Attendance,
    AttendanceAudit,
    AttendanceAuditAction,
    AttendanceLocation,
    AttendanceMethod,
    AttendanceStatus,
)
from attendance.utils.geofence import (
    is_within_geofence,
    validate_location_accuracy,
)


class AttendanceError(Exception):
    """Raised when an attendance business rule is violated."""


class AttendancePermissionError(AttendanceError):
    """Raised when a user cannot perform an attendance operation."""


class AttendanceService:
    """
    Handles QR, GPS, manual, and automatic attendance operations.

    All attendance mutations are performed through this service so that
    validation, audit logging, and notifications remain consistent.
    """

    LATE_GRACE_PERIOD_MINUTES = 15

    @classmethod
    def _get_current_local_datetime(cls):
        return timezone.localtime()

    @classmethod
    def _normalise_datetime(cls, value):
        """
        Ensure a datetime is timezone-aware and represented locally.
        """
        if value is None:
            value = cls._get_current_local_datetime()

        if timezone.is_naive(value):
            value = timezone.make_aware(
                value,
                timezone.get_current_timezone(),
            )

        return timezone.localtime(value)

    @classmethod
    def _build_session_datetime(
        cls,
        attendance_date,
        session_time,
    ):
        session_datetime = datetime.combine(
            attendance_date,
            session_time,
        )

        if timezone.is_naive(session_datetime):
            session_datetime = timezone.make_aware(
                session_datetime,
                timezone.get_current_timezone(),
            )

        return session_datetime

    @classmethod
    def _validate_staff_user(cls, user):
        if user is None:
            raise AttendancePermissionError(
                "A staff user is required to perform this operation."
            )

        if not user.is_authenticated:
            raise AttendancePermissionError(
                "Authentication is required."
            )

        if not user.is_staff:
            raise AttendancePermissionError(
                "Only staff members can modify attendance."
            )

    @classmethod
    def _validate_authenticated_user(cls, user):
        if user is None or not user.is_authenticated:
            raise AttendancePermissionError(
                "Authentication is required."
            )

    @classmethod
    def _validate_intern(cls, intern):
        if intern.user.account_status != AccountStatus.ACTIVE:
            raise AttendanceError(
                "Only approved and active interns can record attendance."
            )

        if not intern.user.is_active:
            raise AttendanceError(
                "This intern's user account is inactive."
            )

        if intern.batch is None:
            raise AttendanceError(
                "This intern has not been assigned to a batch."
            )

        if intern.session is None:
            raise AttendanceError(
                "This intern has not been assigned to a session."
            )

        if not intern.session.is_active:
            raise AttendanceError(
                "This intern's session is currently inactive."
            )

    @classmethod
    def _validate_intern_user(cls, intern, user):
        cls._validate_authenticated_user(
            user,
        )

        if intern.user_id != user.pk:
            raise AttendancePermissionError(
                "You can only record attendance for your own "
                "intern profile."
            )

    @classmethod
    def _validate_session_window(
        cls,
        session,
        current_datetime,
    ):
        attendance_date = current_datetime.date()

        session_start = cls._build_session_datetime(
            attendance_date,
            session.start_time,
        )

        session_end = cls._build_session_datetime(
            attendance_date,
            session.end_time,
        )

        if session_end <= session_start:
            session_end += timedelta(
                days=1,
            )

        if current_datetime < session_start:
            raise AttendanceError(
                "Attendance has not opened yet. "
                f"This session starts at "
                f"{session_start.strftime('%H:%M')}."
            )

        if current_datetime > session_end:
            raise AttendanceError(
                "Attendance is closed. "
                f"This session ended at "
                f"{session_end.strftime('%H:%M')}."
            )

        return session_start, session_end

    @classmethod
    def _determine_status(
        cls,
        current_datetime,
        session_start,
    ):
        late_threshold = session_start + timedelta(
            minutes=cls.LATE_GRACE_PERIOD_MINUTES,
        )

        if current_datetime <= late_threshold:
            return AttendanceStatus.PRESENT

        return AttendanceStatus.LATE

    @classmethod
    def _ensure_no_duplicate(
        cls,
        intern,
        session,
        attendance_date,
        exclude_attendance_id=None,
    ):
        records = Attendance.objects.filter(
            intern=intern,
            session=session,
            attendance_date=attendance_date,
        )

        if exclude_attendance_id is not None:
            records = records.exclude(
                pk=exclude_attendance_id,
            )

        if records.exists():
            raise AttendanceError(
                "Attendance has already been recorded for this intern "
                "and session on this date."
            )

    @classmethod
    def _validate_status(cls, status):
        valid_statuses = {
            choice[0]
            for choice in AttendanceStatus.choices
        }

        if status not in valid_statuses:
            raise AttendanceError(
                "The selected attendance status is invalid."
            )

    @classmethod
    def _get_active_attendance_location(
        cls,
        attendance_location,
    ):
        if attendance_location is None:
            raise AttendanceError(
                "An attendance location is required."
            )

        try:
            location = AttendanceLocation.objects.get(
                pk=attendance_location.pk,
            )
        except (
            AttendanceLocation.DoesNotExist,
            AttributeError,
            TypeError,
            ValueError,
        ) as exc:
            raise AttendanceError(
                "The selected attendance location does not exist."
            ) from exc

        if not location.is_active:
            raise AttendanceError(
                "The selected attendance location is inactive."
            )

        return location

    @classmethod
    def _validate_geofence(
        cls,
        *,
        attendance_location,
        latitude,
        longitude,
        accuracy,
    ):
        """
        Validate GPS accuracy and distance from an attendance location.

        Returns the calculated distance from the geofence centre in
        metres.
        """
        try:
            validate_location_accuracy(
                accuracy_metres=accuracy,
                maximum_accuracy_metres=(
                    attendance_location.maximum_accuracy_metres
                ),
            )

            inside_geofence, distance_metres = is_within_geofence(
                user_latitude=latitude,
                user_longitude=longitude,
                location_latitude=attendance_location.latitude,
                location_longitude=attendance_location.longitude,
                radius_metres=attendance_location.radius_metres,
            )
        except ValidationError as exc:
            if hasattr(exc, "message_dict"):
                validation_messages = []

                for field_messages in exc.message_dict.values():
                    validation_messages.extend(
                        str(message)
                        for message in field_messages
                    )

                error_message = " ".join(
                    validation_messages,
                )
            else:
                error_message = " ".join(
                    exc.messages,
                )

            raise AttendanceError(
                error_message,
            ) from exc

        if not inside_geofence:
            raise AttendanceError(
                "You are outside the permitted attendance area. "
                f"Your device is approximately "
                f"{distance_metres:.2f} metres from "
                f"{attendance_location.name}, while the allowed "
                f"radius is "
                f"{float(attendance_location.radius_metres):.2f} "
                "metres."
            )

        return distance_metres

    @classmethod
    def _create_audit(
        cls,
        *,
        attendance,
        action,
        performed_by,
        reason="",
        previous_status=None,
        new_status=None,
        previous_check_in_time=None,
        new_check_in_time=None,
        previous_check_out_time=None,
        new_check_out_time=None,
        previous_attendance_method=None,
        new_attendance_method=None,
    ):
        return AttendanceAudit.objects.create(
            attendance=attendance,
            intern=attendance.intern,
            batch=attendance.batch,
            session=attendance.session,
            attendance_date=attendance.attendance_date,
            action=action,
            previous_status=previous_status,
            new_status=new_status,
            previous_check_in_time=previous_check_in_time,
            new_check_in_time=new_check_in_time,
            previous_check_out_time=previous_check_out_time,
            new_check_out_time=new_check_out_time,
            previous_attendance_method=(
                previous_attendance_method
            ),
            new_attendance_method=new_attendance_method,
            reason=(reason or "").strip(),
            performed_by=performed_by,
        )

    @classmethod
    def _notify_attendance_created(
        cls,
        *,
        attendance,
    ):
        if attendance.status == AttendanceStatus.ABSENT:
            return NotificationService.notify_attendance_absent(
                attendance=attendance,
            )

        return NotificationService.notify_attendance_check_in(
            attendance=attendance,
        )

    @classmethod
    @transaction.atomic
    def record_attendance(
        cls,
        intern,
        recorded_by,
        current_datetime=None,
    ):
        """
        Record attendance through the staff-operated QR scanner.
        """
        cls._validate_staff_user(
            recorded_by,
        )

        intern = (
            InternProfile.objects
            .select_for_update()
            .select_related(
                "user",
                "batch",
                "session",
            )
            .get(
                pk=intern.pk,
            )
        )

        cls._validate_intern(
            intern,
        )

        current_datetime = cls._normalise_datetime(
            current_datetime,
        )

        attendance_date = current_datetime.date()

        session_start, _ = cls._validate_session_window(
            session=intern.session,
            current_datetime=current_datetime,
        )

        cls._ensure_no_duplicate(
            intern=intern,
            session=intern.session,
            attendance_date=attendance_date,
        )

        status = cls._determine_status(
            current_datetime=current_datetime,
            session_start=session_start,
        )

        attendance = Attendance.objects.create(
            intern=intern,
            batch=intern.batch,
            session=intern.session,
            attendance_date=attendance_date,
            check_in_time=current_datetime.time().replace(
                tzinfo=None,
            ),
            attendance_method=AttendanceMethod.QR,
            status=status,
            recorded_by=recorded_by,
        )

        cls._create_audit(
            attendance=attendance,
            action=AttendanceAuditAction.CREATED,
            performed_by=recorded_by,
            reason="Attendance recorded through QR scan.",
            new_status=attendance.status,
            new_check_in_time=attendance.check_in_time,
            new_attendance_method=attendance.attendance_method,
        )

        cls._notify_attendance_created(
            attendance=attendance,
        )

        return attendance

    @classmethod
    @transaction.atomic
    def gps_check_in(
        cls,
        *,
        intern,
        user,
        attendance_location,
        latitude,
        longitude,
        accuracy,
        current_datetime=None,
    ):
        """
        Record an intern's self-service GPS check-in.
        """
        intern = (
            InternProfile.objects
            .select_for_update()
            .select_related(
                "user",
                "batch",
                "session",
            )
            .get(
                pk=intern.pk,
            )
        )

        cls._validate_intern_user(
            intern=intern,
            user=user,
        )

        cls._validate_intern(
            intern,
        )

        attendance_location = (
            cls._get_active_attendance_location(
                attendance_location,
            )
        )

        current_datetime = cls._normalise_datetime(
            current_datetime,
        )

        attendance_date = current_datetime.date()

        session_start, _ = cls._validate_session_window(
            session=intern.session,
            current_datetime=current_datetime,
        )

        cls._validate_geofence(
            attendance_location=attendance_location,
            latitude=latitude,
            longitude=longitude,
            accuracy=accuracy,
        )

        cls._ensure_no_duplicate(
            intern=intern,
            session=intern.session,
            attendance_date=attendance_date,
        )

        status = cls._determine_status(
            current_datetime=current_datetime,
            session_start=session_start,
        )

        attendance = Attendance.objects.create(
            intern=intern,
            batch=intern.batch,
            session=intern.session,
            attendance_location=attendance_location,
            attendance_date=attendance_date,
            check_in_time=current_datetime.time().replace(
                tzinfo=None,
            ),
            check_in_latitude=latitude,
            check_in_longitude=longitude,
            check_in_accuracy=accuracy,
            attendance_method=AttendanceMethod.GPS,
            status=status,
            recorded_by=user,
        )

        cls._create_audit(
            attendance=attendance,
            action=AttendanceAuditAction.CREATED,
            performed_by=user,
            reason=(
                "Intern checked in using GPS at "
                f"{attendance_location.name}."
            ),
            new_status=attendance.status,
            new_check_in_time=attendance.check_in_time,
            new_attendance_method=attendance.attendance_method,
        )

        cls._notify_attendance_created(
            attendance=attendance,
        )

        return attendance

    @classmethod
    @transaction.atomic
    def gps_check_out(
        cls,
        *,
        intern,
        user,
        attendance_location,
        latitude,
        longitude,
        accuracy,
        current_datetime=None,
    ):
        """
        Record an intern's self-service GPS check-out.
        """
        intern = (
            InternProfile.objects
            .select_for_update()
            .select_related(
                "user",
                "batch",
                "session",
            )
            .get(
                pk=intern.pk,
            )
        )

        cls._validate_intern_user(
            intern=intern,
            user=user,
        )

        cls._validate_intern(
            intern,
        )

        attendance_location = (
            cls._get_active_attendance_location(
                attendance_location,
            )
        )

        current_datetime = cls._normalise_datetime(
            current_datetime,
        )

        attendance_date = current_datetime.date()

        cls._validate_session_window(
            session=intern.session,
            current_datetime=current_datetime,
        )

        cls._validate_geofence(
            attendance_location=attendance_location,
            latitude=latitude,
            longitude=longitude,
            accuracy=accuracy,
        )

        try:
            attendance = (
                Attendance.objects
                .select_for_update()
                .select_related(
                    "intern__user",
                    "batch",
                    "session",
                    "attendance_location",
                )
                .get(
                    intern=intern,
                    session=intern.session,
                    attendance_date=attendance_date,
                )
            )
        except Attendance.DoesNotExist as exc:
            raise AttendanceError(
                "You cannot check out before checking in."
            ) from exc

        if attendance.status == AttendanceStatus.ABSENT:
            raise AttendanceError(
                "An absent attendance record cannot be checked out."
            )

        if attendance.check_in_time is None:
            raise AttendanceError(
                "You cannot check out because this attendance record "
                "does not contain a check-in time."
            )

        if attendance.attendance_method != AttendanceMethod.GPS:
            raise AttendanceError(
                "GPS check-out is only available for attendance that "
                "was checked in using GPS."
            )

        if attendance.check_out_time is not None:
            raise AttendanceError(
                "You have already checked out for this session."
            )

        current_time = current_datetime.time().replace(
            tzinfo=None,
        )

        if current_time < attendance.check_in_time:
            raise AttendanceError(
                "Check-out time cannot be earlier than check-in time."
            )

        previous_check_out_time = attendance.check_out_time

        attendance.check_out_time = current_time
        attendance.check_out_latitude = latitude
        attendance.check_out_longitude = longitude
        attendance.check_out_accuracy = accuracy
        attendance.attendance_location = attendance_location
        attendance.recorded_by = user

        attendance.save(
            update_fields=[
                "check_out_time",
                "check_out_latitude",
                "check_out_longitude",
                "check_out_accuracy",
                "attendance_location",
                "recorded_by",
                "updated_at",
            ],
        )

        cls._create_audit(
            attendance=attendance,
            action=AttendanceAuditAction.UPDATED,
            performed_by=user,
            reason=(
                "Intern checked out using GPS at "
                f"{attendance_location.name}."
            ),
            previous_status=attendance.status,
            new_status=attendance.status,
            previous_check_in_time=attendance.check_in_time,
            new_check_in_time=attendance.check_in_time,
            previous_check_out_time=previous_check_out_time,
            new_check_out_time=attendance.check_out_time,
            previous_attendance_method=(
                attendance.attendance_method
            ),
            new_attendance_method=attendance.attendance_method,
        )

        NotificationService.notify_attendance_check_out(
            attendance=attendance,
        )

        return attendance

    @classmethod
    @transaction.atomic
    def record_manual_attendance(
        cls,
        *,
        intern,
        status,
        recorded_by,
        attendance_date=None,
        check_in_time=None,
        reason,
    ):
        cls._validate_staff_user(
            recorded_by,
        )

        if not reason or not reason.strip():
            raise AttendanceError(
                "A reason is required for manual attendance."
            )

        cls._validate_status(
            status,
        )

        intern = (
            InternProfile.objects
            .select_for_update()
            .select_related(
                "user",
                "batch",
                "session",
            )
            .get(
                pk=intern.pk,
            )
        )

        cls._validate_intern(
            intern,
        )

        attendance_date = (
            attendance_date
            or timezone.localdate()
        )

        cls._ensure_no_duplicate(
            intern=intern,
            session=intern.session,
            attendance_date=attendance_date,
        )

        if status == AttendanceStatus.ABSENT:
            check_in_time = None
        elif check_in_time is None:
            check_in_time = (
                timezone.localtime()
                .time()
                .replace(tzinfo=None)
            )

        attendance = Attendance.objects.create(
            intern=intern,
            batch=intern.batch,
            session=intern.session,
            attendance_date=attendance_date,
            check_in_time=check_in_time,
            attendance_method=AttendanceMethod.MANUAL,
            status=status,
            recorded_by=recorded_by,
        )

        cls._create_audit(
            attendance=attendance,
            action=AttendanceAuditAction.CREATED,
            performed_by=recorded_by,
            reason=reason,
            new_status=attendance.status,
            new_check_in_time=attendance.check_in_time,
            new_attendance_method=attendance.attendance_method,
        )

        cls._notify_attendance_created(
            attendance=attendance,
        )

        return attendance

    @classmethod
    def mark_present(
        cls,
        *,
        intern,
        recorded_by,
        attendance_date=None,
        check_in_time=None,
        reason,
    ):
        return cls.record_manual_attendance(
            intern=intern,
            status=AttendanceStatus.PRESENT,
            recorded_by=recorded_by,
            attendance_date=attendance_date,
            check_in_time=check_in_time,
            reason=reason,
        )

    @classmethod
    def mark_late(
        cls,
        *,
        intern,
        recorded_by,
        attendance_date=None,
        check_in_time=None,
        reason,
    ):
        return cls.record_manual_attendance(
            intern=intern,
            status=AttendanceStatus.LATE,
            recorded_by=recorded_by,
            attendance_date=attendance_date,
            check_in_time=check_in_time,
            reason=reason,
        )

    @classmethod
    def mark_absent(
        cls,
        *,
        intern,
        recorded_by,
        attendance_date=None,
        reason,
    ):
        return cls.record_manual_attendance(
            intern=intern,
            status=AttendanceStatus.ABSENT,
            recorded_by=recorded_by,
            attendance_date=attendance_date,
            check_in_time=None,
            reason=reason,
        )

    @classmethod
    @transaction.atomic
    def update_attendance(
        cls,
        *,
        attendance,
        new_status,
        performed_by,
        reason,
        new_check_in_time=None,
        new_attendance_date=None,
    ):
        cls._validate_staff_user(
            performed_by,
        )

        if not reason or not reason.strip():
            raise AttendanceError(
                "A reason is required when correcting attendance."
            )

        cls._validate_status(
            new_status,
        )

        attendance = (
            Attendance.objects
            .select_for_update()
            .select_related(
                "intern__user",
                "batch",
                "session",
            )
            .get(
                pk=attendance.pk,
            )
        )

        previous_status = attendance.status
        previous_check_in_time = attendance.check_in_time
        previous_check_out_time = attendance.check_out_time
        previous_attendance_method = (
            attendance.attendance_method
        )

        attendance_date = (
            new_attendance_date
            or attendance.attendance_date
        )

        cls._ensure_no_duplicate(
            intern=attendance.intern,
            session=attendance.session,
            attendance_date=attendance_date,
            exclude_attendance_id=attendance.pk,
        )

        if new_status == AttendanceStatus.ABSENT:
            new_check_in_time = None
            attendance.check_out_time = None
            attendance.check_out_latitude = None
            attendance.check_out_longitude = None
            attendance.check_out_accuracy = None
        elif new_check_in_time is None:
            new_check_in_time = attendance.check_in_time

            if new_check_in_time is None:
                new_check_in_time = (
                    timezone.localtime()
                    .time()
                    .replace(tzinfo=None)
                )

        attendance.status = new_status
        attendance.attendance_date = attendance_date
        attendance.check_in_time = new_check_in_time
        attendance.recorded_by = performed_by

        attendance.save(
            update_fields=[
                "status",
                "attendance_date",
                "check_in_time",
                "check_out_time",
                "check_out_latitude",
                "check_out_longitude",
                "check_out_accuracy",
                "recorded_by",
                "updated_at",
            ],
        )

        cls._create_audit(
            attendance=attendance,
            action=AttendanceAuditAction.UPDATED,
            performed_by=performed_by,
            reason=reason,
            previous_status=previous_status,
            new_status=attendance.status,
            previous_check_in_time=previous_check_in_time,
            new_check_in_time=attendance.check_in_time,
            previous_check_out_time=previous_check_out_time,
            new_check_out_time=attendance.check_out_time,
            previous_attendance_method=(
                previous_attendance_method
            ),
            new_attendance_method=attendance.attendance_method,
        )

        NotificationService.notify_attendance_updated(
            attendance=attendance,
            reason=reason,
        )

        return attendance

    @classmethod
    @transaction.atomic
    def delete_attendance(
        cls,
        *,
        attendance,
        performed_by,
        reason,
    ):
        cls._validate_staff_user(
            performed_by,
        )

        if not reason or not reason.strip():
            raise AttendanceError(
                "A reason is required when deleting attendance."
            )

        attendance = (
            Attendance.objects
            .select_for_update()
            .select_related(
                "intern__user",
                "batch",
                "session",
            )
            .get(
                pk=attendance.pk,
            )
        )

        recipient = attendance.intern.user
        attendance_date = attendance.attendance_date
        session_name = str(attendance.session)

        audit = cls._create_audit(
            attendance=attendance,
            action=AttendanceAuditAction.DELETED,
            performed_by=performed_by,
            reason=reason,
            previous_status=attendance.status,
            previous_check_in_time=attendance.check_in_time,
            previous_check_out_time=attendance.check_out_time,
            previous_attendance_method=(
                attendance.attendance_method
            ),
        )

        attendance.delete()

        NotificationService.notify_attendance_deleted(
            recipient=recipient,
            attendance_date=attendance_date,
            session_name=session_name,
            reason=reason,
        )

        return audit

    @classmethod
    @transaction.atomic
    def close_session(
        cls,
        *,
        session,
        recorded_by,
        attendance_date=None,
        reason="Automatically marked absent when session closed.",
    ):
        cls._validate_staff_user(
            recorded_by,
        )

        attendance_date = (
            attendance_date
            or timezone.localdate()
        )

        interns = InternProfile.objects.select_related(
            "user",
            "batch",
            "session",
        ).filter(
            session=session,
            user__account_status=AccountStatus.ACTIVE,
            user__is_active=True,
            batch__isnull=False,
        )

        recorded_intern_ids = Attendance.objects.filter(
            session=session,
            attendance_date=attendance_date,
        ).values_list(
            "intern_id",
            flat=True,
        )

        interns_to_mark_absent = list(
            interns.exclude(
                pk__in=recorded_intern_ids,
            )
        )

        absent_records = Attendance.objects.bulk_create(
            [
                Attendance(
                    intern=intern,
                    batch=intern.batch,
                    session=session,
                    attendance_date=attendance_date,
                    check_in_time=None,
                    attendance_method=(
                        AttendanceMethod.AUTOMATIC
                    ),
                    status=AttendanceStatus.ABSENT,
                    recorded_by=recorded_by,
                )
                for intern in interns_to_mark_absent
            ]
        )

        AttendanceAudit.objects.bulk_create(
            [
                AttendanceAudit(
                    attendance=attendance,
                    intern=attendance.intern,
                    batch=attendance.batch,
                    session=attendance.session,
                    attendance_date=attendance.attendance_date,
                    action=AttendanceAuditAction.CREATED,
                    new_status=AttendanceStatus.ABSENT,
                    new_check_in_time=None,
                    new_attendance_method=(
                        AttendanceMethod.AUTOMATIC
                    ),
                    reason=reason,
                    performed_by=recorded_by,
                )
                for attendance in absent_records
            ]
        )

        for attendance in absent_records:
            NotificationService.notify_attendance_absent(
                attendance=attendance,
            )

        return absent_records