from datetime import date, time, timedelta
from decimal import Decimal

from django.utils import timezone

from accounts.models import AccountStatus, User
from attendance.models import AttendanceLocation
from interns.models import (
    Batch,
    BatchStatus,
    InternProfile,
    Session,
)


class AttendanceTestFactory:
    """
    Shared factory helpers for attendance tests.
    """

    user_counter = 0
    intern_counter = 0
    batch_counter = 0
    session_counter = 0
    location_counter = 0

    @classmethod
    def create_user(
        cls,
        *,
        email=None,
        first_name="Test",
        last_name="User",
        phone_number=None,
        password="TestPassword123!",
        account_status=AccountStatus.ACTIVE,
        is_active=True,
        is_staff=False,
    ):
        cls.user_counter += 1

        if email is None:
            email = f"user{cls.user_counter}@example.com"

        if phone_number is None:
            phone_number = f"+256700{cls.user_counter:06d}"

        user = User.objects.create_user(
            email=email,
            first_name=first_name,
            last_name=last_name,
            phone_number=phone_number,
            password=password,
        )

        user.account_status = account_status
        user.is_active = is_active
        user.is_staff = is_staff

        user.save(
            update_fields=[
                "account_status",
                "is_active",
                "is_staff",
            ]
        )

        return user

    @classmethod
    def create_staff_user(
        cls,
        *,
        email=None,
        first_name="Staff",
        last_name="Member",
        phone_number=None,
        password="TestPassword123!",
    ):
        return cls.create_user(
            email=email,
            first_name=first_name,
            last_name=last_name,
            phone_number=phone_number,
            password=password,
            account_status=AccountStatus.ACTIVE,
            is_active=True,
            is_staff=True,
        )

    @classmethod
    def create_batch(
        cls,
        *,
        name=None,
        start_date=None,
        end_date=None,
        status=BatchStatus.ACTIVE,
    ):
        cls.batch_counter += 1

        today = timezone.localdate()

        return Batch.objects.create(
            name=name or f"Batch {cls.batch_counter}",
            start_date=start_date or today - timedelta(days=30),
            end_date=end_date or today + timedelta(days=30),
            status=status,
        )

    @classmethod
    def create_session(
        cls,
        *,
        name=None,
        start_time=time(8, 0),
        end_time=time(17, 0),
        is_active=True,
    ):
        cls.session_counter += 1

        return Session.objects.create(
            name=name or f"Session {cls.session_counter}",
            start_time=start_time,
            end_time=end_time,
            is_active=is_active,
        )

    @classmethod
    def create_intern(
        cls,
        *,
        user=None,
        batch=None,
        session=None,
        student_number=None,
        university="Test University",
        course="Computer Science",
    ):
        cls.intern_counter += 1

        if user is None:
            user = cls.create_user(
                first_name="Intern",
                last_name=str(cls.intern_counter),
            )

        if batch is None:
            batch = cls.create_batch()

        if session is None:
            session = cls.create_session()

        return InternProfile.objects.create(
            user=user,
            student_number=(
                student_number
                or f"STUDENT-{cls.intern_counter:04d}"
            ),
            university=university,
            course=course,
            batch=batch,
            session=session,
        )

    @classmethod
    def create_location(
        cls,
        *,
        name=None,
        latitude=Decimal("0.347596"),
        longitude=Decimal("32.582520"),
        radius_metres=Decimal("100.00"),
        maximum_accuracy_metres=Decimal("50.00"),
        is_active=True,
    ):
        cls.location_counter += 1

        return AttendanceLocation.objects.create(
            name=name or f"Location {cls.location_counter}",
            latitude=latitude,
            longitude=longitude,
            radius_metres=radius_metres,
            maximum_accuracy_metres=maximum_accuracy_metres,
            is_active=is_active,
        )

    @staticmethod
    def aware_datetime(
        *,
        attendance_date=None,
        hour=8,
        minute=0,
        second=0,
    ):
        attendance_date = (
            attendance_date
            or timezone.localdate()
        )

        naive_datetime = timezone.datetime.combine(
            attendance_date,
            time(
                hour=hour,
                minute=minute,
                second=second,
            ),
        )

        return timezone.make_aware(
            naive_datetime,
            timezone.get_current_timezone(),
        )