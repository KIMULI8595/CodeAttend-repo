from datetime import time

from django.test import TestCase

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


class QRAttendanceRegressionTests(TestCase):
    def setUp(self):
        self.staff_user = (
            AttendanceTestFactory.create_staff_user()
        )

        self.session = AttendanceTestFactory.create_session(
            start_time=time(8, 0),
            end_time=time(17, 0),
        )

        self.intern = AttendanceTestFactory.create_intern(
            session=self.session,
        )

        self.current_datetime = (
            AttendanceTestFactory.aware_datetime(
                hour=8,
                minute=5,
            )
        )

    def test_qr_attendance_is_recorded_with_qr_method(self):
        attendance = AttendanceService.record_attendance(
            intern=self.intern,
            recorded_by=self.staff_user,
            current_datetime=self.current_datetime,
        )

        self.assertEqual(
            attendance.attendance_method,
            AttendanceMethod.QR,
        )

        self.assertEqual(
            attendance.status,
            AttendanceStatus.PRESENT,
        )

        self.assertEqual(
            attendance.recorded_by,
            self.staff_user,
        )

    def test_qr_attendance_creates_audit_record(self):
        attendance = AttendanceService.record_attendance(
            intern=self.intern,
            recorded_by=self.staff_user,
            current_datetime=self.current_datetime,
        )

        audit = AttendanceAudit.objects.get(
            attendance=attendance,
        )

        self.assertEqual(
            audit.action,
            AttendanceAuditAction.CREATED,
        )

        self.assertEqual(
            audit.new_attendance_method,
            AttendanceMethod.QR,
        )

    def test_non_staff_user_cannot_record_qr_attendance(self):
        regular_user = AttendanceTestFactory.create_user()

        with self.assertRaisesMessage(
            AttendancePermissionError,
            "Only staff members can modify attendance.",
        ):
            AttendanceService.record_attendance(
                intern=self.intern,
                recorded_by=regular_user,
                current_datetime=self.current_datetime,
            )

    def test_duplicate_qr_attendance_is_rejected(self):
        AttendanceService.record_attendance(
            intern=self.intern,
            recorded_by=self.staff_user,
            current_datetime=self.current_datetime,
        )

        with self.assertRaisesMessage(
            AttendanceError,
            "Attendance has already been recorded",
        ):
            AttendanceService.record_attendance(
                intern=self.intern,
                recorded_by=self.staff_user,
                current_datetime=self.current_datetime,
            )

        self.assertEqual(
            Attendance.objects.count(),
            1,
        )


class ManualAttendanceRegressionTests(TestCase):
    def setUp(self):
        self.staff_user = (
            AttendanceTestFactory.create_staff_user()
        )

        self.intern = AttendanceTestFactory.create_intern()

    def test_manual_attendance_uses_manual_method(self):
        attendance = (
            AttendanceService.record_manual_attendance(
                intern=self.intern,
                status=AttendanceStatus.PRESENT,
                recorded_by=self.staff_user,
                check_in_time=time(8, 0),
                reason="Manual test attendance.",
            )
        )

        self.assertEqual(
            attendance.attendance_method,
            AttendanceMethod.MANUAL,
        )

    def test_manual_absence_has_no_check_in_time(self):
        attendance = (
            AttendanceService.record_manual_attendance(
                intern=self.intern,
                status=AttendanceStatus.ABSENT,
                recorded_by=self.staff_user,
                check_in_time=time(8, 0),
                reason="Intern was absent.",
            )
        )

        self.assertIsNone(
            attendance.check_in_time,
        )

        self.assertEqual(
            attendance.status,
            AttendanceStatus.ABSENT,
        )

    def test_manual_attendance_requires_reason(self):
        with self.assertRaisesMessage(
            AttendanceError,
            "A reason is required for manual attendance.",
        ):
            AttendanceService.record_manual_attendance(
                intern=self.intern,
                status=AttendanceStatus.PRESENT,
                recorded_by=self.staff_user,
                reason="",
            )


class AutomaticAbsenceRegressionTests(TestCase):
    def setUp(self):
        self.staff_user = (
            AttendanceTestFactory.create_staff_user()
        )

        self.session = AttendanceTestFactory.create_session()

        self.intern = AttendanceTestFactory.create_intern(
            session=self.session,
        )

    def test_close_session_creates_automatic_absence(self):
        records = AttendanceService.close_session(
            session=self.session,
            recorded_by=self.staff_user,
        )

        self.assertEqual(
            len(records),
            1,
        )

        attendance = Attendance.objects.get(
            intern=self.intern,
        )

        self.assertEqual(
            attendance.status,
            AttendanceStatus.ABSENT,
        )

        self.assertEqual(
            attendance.attendance_method,
            AttendanceMethod.AUTOMATIC,
        )

        self.assertIsNone(
            attendance.check_in_time,
        )

    def test_close_session_does_not_duplicate_existing_attendance(self):
        AttendanceService.record_manual_attendance(
            intern=self.intern,
            status=AttendanceStatus.PRESENT,
            recorded_by=self.staff_user,
            reason="Existing attendance.",
        )

        records = AttendanceService.close_session(
            session=self.session,
            recorded_by=self.staff_user,
        )

        self.assertEqual(
            records,
            [],
        )

        self.assertEqual(
            Attendance.objects.filter(
                intern=self.intern,
            ).count(),
            1,
        )