from datetime import time
from decimal import Decimal

from django.test import TestCase

from accounts.models import AccountStatus
from attendance.models import (
    Attendance,
    AttendanceAudit,
    AttendanceAuditAction,
    AttendanceMethod,
    AttendanceStatus,
)
from attendance.services.attendance import (
    AttendanceError,
    AttendancePermissionError,
    AttendanceService,
)

from .factories import AttendanceTestFactory


class GPSCheckInServiceTests(TestCase):
    def setUp(self):
        self.session = AttendanceTestFactory.create_session(
            start_time=time(8, 0),
            end_time=time(17, 0),
        )

        self.batch = AttendanceTestFactory.create_batch()

        self.user = AttendanceTestFactory.create_user(
            first_name="GPS",
            last_name="Intern",
        )

        self.intern = AttendanceTestFactory.create_intern(
            user=self.user,
            batch=self.batch,
            session=self.session,
        )

        self.location = AttendanceTestFactory.create_location(
            latitude=Decimal("0.347596"),
            longitude=Decimal("32.582520"),
            radius_metres=Decimal("100.00"),
            maximum_accuracy_metres=Decimal("50.00"),
        )

        self.current_datetime = (
            AttendanceTestFactory.aware_datetime(
                hour=8,
                minute=5,
            )
        )

    def gps_check_in(self, **overrides):
        values = {
            "intern": self.intern,
            "user": self.user,
            "attendance_location": self.location,
            "latitude": Decimal("0.347596"),
            "longitude": Decimal("32.582520"),
            "accuracy": Decimal("10.00"),
            "current_datetime": self.current_datetime,
        }

        values.update(overrides)

        return AttendanceService.gps_check_in(
            **values
        )

    def test_successful_gps_check_in_creates_attendance(self):
        attendance = self.gps_check_in()

        self.assertEqual(
            Attendance.objects.count(),
            1,
        )

        self.assertEqual(
            attendance.intern,
            self.intern,
        )

        self.assertEqual(
            attendance.batch,
            self.batch,
        )

        self.assertEqual(
            attendance.session,
            self.session,
        )

        self.assertEqual(
            attendance.attendance_location,
            self.location,
        )

        self.assertEqual(
            attendance.attendance_method,
            AttendanceMethod.GPS,
        )

        self.assertEqual(
            attendance.status,
            AttendanceStatus.PRESENT,
        )

        self.assertEqual(
            attendance.recorded_by,
            self.user,
        )

        self.assertEqual(
            attendance.check_in_latitude,
            Decimal("0.347596"),
        )

        self.assertEqual(
            attendance.check_in_longitude,
            Decimal("32.582520"),
        )

        self.assertEqual(
            attendance.check_in_accuracy,
            Decimal("10.00"),
        )

        self.assertIsNotNone(
            attendance.check_in_time,
        )

        self.assertIsNone(
            attendance.check_out_time,
        )

    def test_successful_gps_check_in_creates_audit_record(self):
        attendance = self.gps_check_in()

        audit = AttendanceAudit.objects.get()

        self.assertEqual(
            audit.attendance,
            attendance,
        )

        self.assertEqual(
            audit.intern,
            self.intern,
        )

        self.assertEqual(
            audit.action,
            AttendanceAuditAction.CREATED,
        )

        self.assertEqual(
            audit.new_status,
            AttendanceStatus.PRESENT,
        )

        self.assertEqual(
            audit.new_attendance_method,
            AttendanceMethod.GPS,
        )

        self.assertEqual(
            audit.performed_by,
            self.user,
        )

        self.assertIn(
            self.location.name,
            audit.reason,
        )

    def test_check_in_after_grace_period_is_late(self):
        attendance = self.gps_check_in(
            current_datetime=(
                AttendanceTestFactory.aware_datetime(
                    hour=8,
                    minute=16,
                )
            ),
        )

        self.assertEqual(
            attendance.status,
            AttendanceStatus.LATE,
        )

    def test_check_in_at_grace_period_boundary_is_present(self):
        attendance = self.gps_check_in(
            current_datetime=(
                AttendanceTestFactory.aware_datetime(
                    hour=8,
                    minute=15,
                )
            ),
        )

        self.assertEqual(
            attendance.status,
            AttendanceStatus.PRESENT,
        )

    def test_duplicate_gps_check_in_is_rejected(self):
        self.gps_check_in()

        with self.assertRaisesMessage(
            AttendanceError,
            "Attendance has already been recorded",
        ):
            self.gps_check_in()

        self.assertEqual(
            Attendance.objects.count(),
            1,
        )

    def test_check_in_before_session_start_is_rejected(self):
        with self.assertRaisesMessage(
            AttendanceError,
            "Attendance has not opened yet",
        ):
            self.gps_check_in(
                current_datetime=(
                    AttendanceTestFactory.aware_datetime(
                        hour=7,
                        minute=59,
                    )
                ),
            )

        self.assertFalse(
            Attendance.objects.exists(),
        )

    def test_check_in_after_session_end_is_rejected(self):
        with self.assertRaisesMessage(
            AttendanceError,
            "Attendance is closed",
        ):
            self.gps_check_in(
                current_datetime=(
                    AttendanceTestFactory.aware_datetime(
                        hour=17,
                        minute=1,
                    )
                ),
            )

        self.assertFalse(
            Attendance.objects.exists(),
        )

    def test_check_in_with_inactive_location_is_rejected(self):
        self.location.is_active = False
        self.location.save(
            update_fields=[
                "is_active",
            ]
        )

        with self.assertRaisesMessage(
            AttendanceError,
            "The selected attendance location is inactive.",
        ):
            self.gps_check_in()

        self.assertFalse(
            Attendance.objects.exists(),
        )

    def test_check_in_without_location_is_rejected(self):
        with self.assertRaisesMessage(
            AttendanceError,
            "An attendance location is required.",
        ):
            self.gps_check_in(
                attendance_location=None,
            )

    def test_check_in_with_poor_accuracy_is_rejected(self):
        with self.assertRaises(
            AttendanceError,
        ) as context:
            self.gps_check_in(
                accuracy=Decimal("75.00"),
            )

        self.assertIn(
            "accuracy",
            str(context.exception).lower(),
        )

        self.assertFalse(
            Attendance.objects.exists(),
        )

    def test_check_in_outside_geofence_is_rejected(self):
        with self.assertRaisesMessage(
            AttendanceError,
            "You are outside the permitted attendance area.",
        ):
            self.gps_check_in(
                latitude=Decimal("0.357596"),
                longitude=Decimal("32.592520"),
            )

        self.assertFalse(
            Attendance.objects.exists(),
        )

    def test_wrong_user_cannot_check_in_for_intern(self):
        other_user = AttendanceTestFactory.create_user(
            first_name="Other",
            last_name="User",
        )

        with self.assertRaisesMessage(
            AttendancePermissionError,
            "You can only record attendance for your own intern profile.",
        ):
            self.gps_check_in(
                user=other_user,
            )

        self.assertFalse(
            Attendance.objects.exists(),
        )

    def test_pending_intern_cannot_check_in(self):
        self.user.account_status = AccountStatus.PENDING
        self.user.save(
            update_fields=[
                "account_status",
            ]
        )

        with self.assertRaisesMessage(
            AttendanceError,
            "Only approved and active interns can record attendance.",
        ):
            self.gps_check_in()

    def test_inactive_user_cannot_check_in(self):
        self.user.is_active = False
        self.user.save(
            update_fields=[
                "is_active",
            ]
        )

        with self.assertRaisesMessage(
            AttendanceError,
            "This intern's user account is inactive.",
        ):
            self.gps_check_in()

    def test_intern_without_batch_cannot_check_in(self):
        self.intern.batch = None
        self.intern.save(
            update_fields=[
                "batch",
            ]
        )

        with self.assertRaisesMessage(
            AttendanceError,
            "This intern has not been assigned to a batch.",
        ):
            self.gps_check_in()

    def test_intern_without_session_cannot_check_in(self):
        self.intern.session = None
        self.intern.save(
            update_fields=[
                "session",
            ]
        )

        with self.assertRaisesMessage(
            AttendanceError,
            "This intern has not been assigned to a session.",
        ):
            self.gps_check_in()

    def test_intern_with_inactive_session_cannot_check_in(self):
        self.session.is_active = False
        self.session.save(
            update_fields=[
                "is_active",
            ]
        )

        with self.assertRaisesMessage(
            AttendanceError,
            "This intern's session is currently inactive.",
        ):
            self.gps_check_in()


class GPSCheckOutServiceTests(TestCase):
    def setUp(self):
        self.session = AttendanceTestFactory.create_session(
            start_time=time(8, 0),
            end_time=time(17, 0),
        )

        self.batch = AttendanceTestFactory.create_batch()

        self.user = AttendanceTestFactory.create_user(
            first_name="GPS",
            last_name="Intern",
        )

        self.intern = AttendanceTestFactory.create_intern(
            user=self.user,
            batch=self.batch,
            session=self.session,
        )

        self.location = AttendanceTestFactory.create_location(
            latitude=Decimal("0.347596"),
            longitude=Decimal("32.582520"),
        )

        self.check_in_datetime = (
            AttendanceTestFactory.aware_datetime(
                hour=8,
                minute=5,
            )
        )

        self.check_out_datetime = (
            AttendanceTestFactory.aware_datetime(
                hour=16,
                minute=30,
            )
        )

    def create_gps_check_in(self):
        return AttendanceService.gps_check_in(
            intern=self.intern,
            user=self.user,
            attendance_location=self.location,
            latitude=Decimal("0.347596"),
            longitude=Decimal("32.582520"),
            accuracy=Decimal("10.00"),
            current_datetime=self.check_in_datetime,
        )

    def gps_check_out(self, **overrides):
        values = {
            "intern": self.intern,
            "user": self.user,
            "attendance_location": self.location,
            "latitude": Decimal("0.347596"),
            "longitude": Decimal("32.582520"),
            "accuracy": Decimal("12.00"),
            "current_datetime": self.check_out_datetime,
        }

        values.update(overrides)

        return AttendanceService.gps_check_out(
            **values
        )

    def test_successful_gps_check_out_updates_attendance(self):
        attendance = self.create_gps_check_in()

        updated_attendance = self.gps_check_out()

        attendance.refresh_from_db()

        self.assertEqual(
            updated_attendance.pk,
            attendance.pk,
        )

        self.assertIsNotNone(
            attendance.check_out_time,
        )

        self.assertEqual(
            attendance.check_out_latitude,
            Decimal("0.347596"),
        )

        self.assertEqual(
            attendance.check_out_longitude,
            Decimal("32.582520"),
        )

        self.assertEqual(
            attendance.check_out_accuracy,
            Decimal("12.00"),
        )

    def test_successful_check_out_creates_update_audit(self):
        attendance = self.create_gps_check_in()

        self.gps_check_out()

        audits = AttendanceAudit.objects.filter(
            attendance=attendance,
        ).order_by(
            "created_at",
        )

        self.assertEqual(
            audits.count(),
            2,
        )

        checkout_audit = audits.last()

        self.assertEqual(
            checkout_audit.action,
            AttendanceAuditAction.UPDATED,
        )

        self.assertEqual(
            checkout_audit.previous_status,
            attendance.status,
        )

        self.assertEqual(
            checkout_audit.new_status,
            attendance.status,
        )

        self.assertEqual(
            checkout_audit.previous_attendance_method,
            AttendanceMethod.GPS,
        )

        self.assertEqual(
            checkout_audit.new_attendance_method,
            AttendanceMethod.GPS,
        )

        self.assertIsNotNone(
            checkout_audit.new_check_out_time,
        )

        self.assertIn(
            self.location.name,
            checkout_audit.reason,
        )

    def test_check_out_before_check_in_record_exists_is_rejected(self):
        with self.assertRaisesMessage(
            AttendanceError,
            "You cannot check out before checking in.",
        ):
            self.gps_check_out()

    def test_duplicate_check_out_is_rejected(self):
        self.create_gps_check_in()
        self.gps_check_out()

        with self.assertRaisesMessage(
            AttendanceError,
            "You have already checked out for this session.",
        ):
            self.gps_check_out()

    def test_check_out_for_manual_attendance_is_rejected(self):
        staff_user = AttendanceTestFactory.create_staff_user()

        AttendanceService.record_manual_attendance(
            intern=self.intern,
            status=AttendanceStatus.PRESENT,
            recorded_by=staff_user,
            attendance_date=self.check_in_datetime.date(),
            check_in_time=time(8, 5),
            reason="Manual attendance test.",
        )

        with self.assertRaisesMessage(
            AttendanceError,
            "GPS check-out is only available for attendance that "
            "was checked in using GPS.",
        ):
            self.gps_check_out()

    def test_absent_attendance_cannot_check_out(self):
        Attendance.objects.create(
            intern=self.intern,
            batch=self.batch,
            session=self.session,
            attendance_date=self.check_in_datetime.date(),
            attendance_method=AttendanceMethod.GPS,
            status=AttendanceStatus.ABSENT,
            recorded_by=self.user,
        )

        with self.assertRaisesMessage(
            AttendanceError,
            "An absent attendance record cannot be checked out.",
        ):
            self.gps_check_out()

    def test_attendance_without_check_in_time_cannot_check_out(self):
        Attendance.objects.create(
            intern=self.intern,
            batch=self.batch,
            session=self.session,
            attendance_date=self.check_in_datetime.date(),
            attendance_method=AttendanceMethod.GPS,
            status=AttendanceStatus.PRESENT,
            recorded_by=self.user,
        )

        with self.assertRaisesMessage(
            AttendanceError,
            "does not contain a check-in time",
        ):
            self.gps_check_out()

    def test_check_out_before_recorded_check_in_time_is_rejected(self):
        self.create_gps_check_in()

        with self.assertRaisesMessage(
            AttendanceError,
            "Check-out time cannot be earlier than check-in time.",
        ):
            self.gps_check_out(
                current_datetime=(
                    AttendanceTestFactory.aware_datetime(
                        hour=8,
                        minute=1,
                    )
                ),
            )

    def test_check_out_outside_geofence_is_rejected(self):
        self.create_gps_check_in()

        with self.assertRaisesMessage(
            AttendanceError,
            "You are outside the permitted attendance area.",
        ):
            self.gps_check_out(
                latitude=Decimal("0.357596"),
                longitude=Decimal("32.592520"),
            )

    def test_check_out_with_poor_accuracy_is_rejected(self):
        self.create_gps_check_in()

        with self.assertRaises(
            AttendanceError,
        ) as context:
            self.gps_check_out(
                accuracy=Decimal("100.00"),
            )

        self.assertIn(
            "accuracy",
            str(context.exception).lower(),
        )

    def test_wrong_user_cannot_check_out(self):
        self.create_gps_check_in()

        other_user = AttendanceTestFactory.create_user(
            first_name="Other",
            last_name="Person",
        )

        with self.assertRaisesMessage(
            AttendancePermissionError,
            "You can only record attendance for your own intern profile.",
        ):
            self.gps_check_out(
                user=other_user,
            )