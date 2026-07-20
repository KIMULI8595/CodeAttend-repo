from accounts.models import User
from interns.models import InternProfile
from django.db import transaction

class RegistrationService:
    # Handles intern registration business logic.
    @staticmethod
    def register_intern(
        *,
        email,
        first_name,
        last_name,
        phone_number,
        password,
        student_number,
        university,
        course,
    ):
        with transaction.atomic():
            user = User.objects.create_user(
                email=email,
                first_name=first_name,
                last_name=last_name,
                phone_number=phone_number,
                password=password,
            )

            intern = InternProfile.objects.create(
                user=user,
                student_number=student_number,
                university=university,
                course=course,
            )

            return intern