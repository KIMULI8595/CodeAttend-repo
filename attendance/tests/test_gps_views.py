from datetime import time
from decimal import Decimal
from unittest.mock import patch

from django.contrib.messages import get_messages
from django.test import TestCase
from django.urls import reverse

from accounts.models import AccountStatus
from attendance.models import (
    Attendance,
    AttendanceLocation,
    AttendanceMethod,
    AttendanceStatus,
)

from .factories import AttendanceTestFactory


class GPSAttendancePageTests(TestCase):
    def setUp(self):
        self.password = "TestPassword123!"

        self.session = AttendanceTestFactory.create_session(
            start_time=time(8, 0),
            end_time=time(17, 0),
        )

        self.batch = AttendanceTestFactory.create_batch()

        self.user = AttendanceTestFactory.create_user(
            email="intern@example.com",
            password=self.password,
            first_name="Page",
            last_name="Intern",
        )

        self.intern = AttendanceTestFactory.create_intern(
            user=self.user,
            batch=self.batch,
            session=self.session,
        )

        self.location = AttendanceTestFactory.create_location()

        self.url = reverse(
            "gps-attendance",
        )

    def test_anonymous_user_is_redirected_to_login(self):
        response = self.client.get(
            self.url,
        )

        self.assertEqual(
            response.status_code,
            302,
        )

        self.assertIn(
            reverse("login"),
            response.url,
        )

    def test_authenticated_intern_can_open_page(self):
        self.client.force_login(
            self.user,
        )

        response = self.client.get(
            self.url,
        )

        self.assertEqual(
            response.status_code,
            200,
        )

        self.assertTemplateUsed(
            response,
            "attendance/gps_attendance.html",
        )

        self.assertEqual(
            response.context["intern"],
            self.intern,
        )

        self.assertTrue(
            response.context["can_use_gps"],
        )

        self.assertContains(
            response,
            self.location.name,
        )

    def test_user_without_intern_profile_receives_forbidden_page(self):
        user_without_profile = AttendanceTestFactory.create_user(
            email="no-profile@example.com",
        )

        self.client.force_login(
            user_without_profile,
        )

        response = self.client.get(
            self.url,
        )

        self.assertEqual(
            response.status_code,
            403,
        )

        self.assertFalse(
            response.context["can_use_gps"],
        )

        self.assertContains(
            response,
            "not linked to an intern profile",
            status_code=403,
        )

    def test_pending_intern_cannot_use_gps(self):
        self.user.account_status = AccountStatus.PENDING
        self.user.save(
            update_fields=[
                "account_status",
            ]
        )

        self.client.force_login(
            self.user,
        )

        response = self.client.get(
            self.url,
        )

        self.assertRedirects(
            response,
            reverse("login"),
        )

        self.assertNotIn(
            "_auth_user_id",
            self.client.session,
        )

    def test_page_disables_gps_when_no_active_locations_exist(self):
        self.location.is_active = False
        self.location.save(
            update_fields=[
                "is_active",
            ]
        )

        self.client.force_login(
            self.user,
        )

        response = self.client.get(
            self.url,
        )

        self.assertEqual(
            response.status_code,
            200,
        )

        self.assertFalse(
            response.context["can_use_gps"],
        )

    def test_page_displays_todays_attendance(self):
        attendance = Attendance.objects.create(
            intern=self.intern,
            batch=self.batch,
            session=self.session,
            attendance_location=self.location,
            attendance_date=(
                AttendanceTestFactory.aware_datetime(
                    hour=8,
                ).date()
            ),
            check_in_time=time(8, 5),
            attendance_method=AttendanceMethod.GPS,
            status=AttendanceStatus.PRESENT,
            recorded_by=self.user,
        )

        self.client.force_login(
            self.user,
        )

        response = self.client.get(
            self.url,
        )

        self.assertEqual(
            response.context["attendance"],
            attendance,
        )


class GPSCheckInViewTests(TestCase):
    def setUp(self):
        self.session = AttendanceTestFactory.create_session(
            start_time=time(8, 0),
            end_time=time(17, 0),
        )

        self.batch = AttendanceTestFactory.create_batch()

        self.user = AttendanceTestFactory.create_user(
            email="checkin@example.com",
            first_name="Check",
            last_name="In",
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

        self.url = reverse(
            "gps-check-in",
        )

        self.redirect_url = reverse(
            "gps-attendance",
        )

        self.valid_data = {
            "attendance_location": str(self.location.pk),
            "latitude": "0.347596",
            "longitude": "32.582520",
            "accuracy": "10.00",
        }

    def get_messages(self, response):
        return [
            str(message)
            for message in get_messages(
                response.wsgi_request
            )
        ]

    def test_check_in_requires_authentication(self):
        response = self.client.post(
            self.url,
            self.valid_data,
        )

        self.assertEqual(
            response.status_code,
            302,
        )

        self.assertIn(
            reverse("login"),
            response.url,
        )

    def test_check_in_rejects_get_request(self):
        self.client.force_login(
            self.user,
        )

        response = self.client.get(
            self.url,
        )

        self.assertEqual(
            response.status_code,
            405,
        )

    @patch(
        "attendance.services.attendance."
        "AttendanceService._get_current_local_datetime"
    )
    def test_successful_check_in_creates_attendance(
        self,
        mocked_datetime,
    ):
        mocked_datetime.return_value = (
            AttendanceTestFactory.aware_datetime(
                hour=8,
                minute=5,
            )
        )

        self.client.force_login(
            self.user,
        )

        response = self.client.post(
            self.url,
            self.valid_data,
        )

        self.assertRedirects(
            response,
            self.redirect_url,
        )

        attendance = Attendance.objects.get()

        self.assertEqual(
            attendance.intern,
            self.intern,
        )

        self.assertEqual(
            attendance.attendance_method,
            AttendanceMethod.GPS,
        )

        self.assertEqual(
            attendance.attendance_location,
            self.location,
        )

        messages = self.get_messages(
            response,
        )

        self.assertTrue(
            any(
                "checked" in message.lower()
                and "success" in message.lower()
                for message in messages
            )
        )

    def test_check_in_with_missing_location_is_rejected(self):
        self.client.force_login(
            self.user,
        )

        data = self.valid_data.copy()
        data["attendance_location"] = ""

        response = self.client.post(
            self.url,
            data,
        )

        self.assertRedirects(
            response,
            self.redirect_url,
        )

        self.assertFalse(
            Attendance.objects.exists(),
        )

        messages = self.get_messages(
            response,
        )

        self.assertIn(
            "Please select an attendance location.",
            messages,
        )

    def test_check_in_with_invalid_latitude_is_rejected(self):
        self.client.force_login(
            self.user,
        )

        data = self.valid_data.copy()
        data["latitude"] = "not-a-number"

        response = self.client.post(
            self.url,
            data,
        )

        self.assertRedirects(
            response,
            self.redirect_url,
        )

        self.assertFalse(
            Attendance.objects.exists(),
        )

        messages = self.get_messages(
            response,
        )

        self.assertIn(
            "Latitude must be a valid number.",
            messages,
        )

    def test_check_in_with_missing_accuracy_is_rejected(self):
        self.client.force_login(
            self.user,
        )

        data = self.valid_data.copy()
        data["accuracy"] = ""

        response = self.client.post(
            self.url,
            data,
        )

        self.assertRedirects(
            response,
            self.redirect_url,
        )

        self.assertFalse(
            Attendance.objects.exists(),
        )

        messages = self.get_messages(
            response,
        )

        self.assertIn(
            "GPS accuracy is required.",
            messages,
        )

    def test_check_in_with_inactive_location_is_rejected(self):
        self.location.is_active = False
        self.location.save(
            update_fields=[
                "is_active",
            ]
        )

        self.client.force_login(
            self.user,
        )

        response = self.client.post(
            self.url,
            self.valid_data,
        )

        self.assertRedirects(
            response,
            self.redirect_url,
        )

        self.assertFalse(
            Attendance.objects.exists(),
        )

        messages = self.get_messages(
            response,
        )

        self.assertIn(
            "The selected attendance location is unavailable.",
            messages,
        )

    def test_user_without_intern_profile_cannot_check_in(self):
        user_without_profile = AttendanceTestFactory.create_user(
            email="missing-profile@example.com",
        )

        self.client.force_login(
            user_without_profile,
        )

        response = self.client.post(
            self.url,
            self.valid_data,
        )

        self.assertRedirects(
            response,
            self.redirect_url,
        )

        self.assertFalse(
            Attendance.objects.exists(),
        )

        messages = self.get_messages(
            response,
        )

        self.assertIn(
            "Your account is not linked to an intern profile.",
            messages,
        )


class GPSCheckOutViewTests(TestCase):
    def setUp(self):
        self.session = AttendanceTestFactory.create_session(
            start_time=time(8, 0),
            end_time=time(17, 0),
        )

        self.batch = AttendanceTestFactory.create_batch()

        self.user = AttendanceTestFactory.create_user(
            email="checkout@example.com",
            first_name="Check",
            last_name="Out",
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

        self.url = reverse(
            "gps-check-out",
        )

        self.redirect_url = reverse(
            "gps-attendance",
        )

        self.valid_data = {
            "attendance_location": str(self.location.pk),
            "latitude": "0.347596",
            "longitude": "32.582520",
            "accuracy": "10.00",
        }

    def get_messages(self, response):
        return [
            str(message)
            for message in get_messages(
                response.wsgi_request
            )
        ]

    def create_check_in(self):
        return Attendance.objects.create(
            intern=self.intern,
            batch=self.batch,
            session=self.session,
            attendance_location=self.location,
            attendance_date=(
                AttendanceTestFactory.aware_datetime(
                    hour=8,
                ).date()
            ),
            check_in_time=time(8, 5),
            check_in_latitude=Decimal("0.347596"),
            check_in_longitude=Decimal("32.582520"),
            check_in_accuracy=Decimal("10.00"),
            attendance_method=AttendanceMethod.GPS,
            status=AttendanceStatus.PRESENT,
            recorded_by=self.user,
        )

    def test_check_out_requires_authentication(self):
        response = self.client.post(
            self.url,
            self.valid_data,
        )

        self.assertEqual(
            response.status_code,
            302,
        )

        self.assertIn(
            reverse("login"),
            response.url,
        )

    def test_check_out_rejects_get_request(self):
        self.client.force_login(
            self.user,
        )

        response = self.client.get(
            self.url,
        )

        self.assertEqual(
            response.status_code,
            405,
        )

    @patch(
        "attendance.services.attendance."
        "AttendanceService._get_current_local_datetime"
    )
    def test_successful_check_out_updates_attendance(
        self,
        mocked_datetime,
    ):
        mocked_datetime.return_value = (
            AttendanceTestFactory.aware_datetime(
                hour=16,
                minute=30,
            )
        )

        attendance = self.create_check_in()

        self.client.force_login(
            self.user,
        )

        response = self.client.post(
            self.url,
            self.valid_data,
        )

        self.assertRedirects(
            response,
            self.redirect_url,
        )

        attendance.refresh_from_db()

        self.assertIsNotNone(
            attendance.check_out_time,
        )

        self.assertEqual(
            attendance.check_out_accuracy,
            Decimal("10.00"),
        )

        messages = self.get_messages(
            response,
        )

        self.assertTrue(
            any(
                "check-out completed successfully"
                in message.lower()
                for message in messages
            )
        )

    @patch(
        "attendance.services.attendance."
        "AttendanceService._get_current_local_datetime"
    )
    def test_check_out_without_check_in_is_rejected(
        self,
        mocked_datetime,
    ):
        mocked_datetime.return_value = (
            AttendanceTestFactory.aware_datetime(
                hour=16,
                minute=30,
            )
        )

        self.client.force_login(
            self.user,
        )

        response = self.client.post(
            self.url,
            self.valid_data,
        )

        self.assertRedirects(
            response,
            self.redirect_url,
        )

        messages = self.get_messages(
            response,
        )

        self.assertIn(
            "You cannot check out before checking in.",
            messages,
        )

    def test_check_out_with_invalid_longitude_is_rejected(self):
        self.client.force_login(
            self.user,
        )

        data = self.valid_data.copy()
        data["longitude"] = "invalid"

        response = self.client.post(
            self.url,
            data,
        )

        self.assertRedirects(
            response,
            self.redirect_url,
        )

        messages = self.get_messages(
            response,
        )

        self.assertIn(
            "Longitude must be a valid number.",
            messages,
        )