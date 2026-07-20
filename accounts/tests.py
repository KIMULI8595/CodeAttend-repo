from django.test import TestCase
from django.urls import reverse

from interns.models import InternProfile
from .models import AccountStatus, User


class PortalAuthenticationTests(TestCase):
    def make_user(self, *, email, phone, is_staff=False, status=AccountStatus.ACTIVE, is_active=True):
        user = User.objects.create_user(
            email=email,
            password="StrongPass!246",
            first_name="Test",
            last_name="User",
            phone_number=phone,
            is_staff=is_staff,
            is_active=is_active,
            account_status=status,
        )
        return user

    def test_portal_home_offers_separate_access_interfaces(self):
        response = self.client.get(reverse("access-portal"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Intern portal")
        self.assertContains(response, "Administration portal")

    def test_pending_intern_cannot_log_in(self):
        user = self.make_user(
            email="pending@example.com",
            phone="+256700000101",
            status=AccountStatus.PENDING,
            is_active=False,
        )
        InternProfile.objects.create(
            user=user,
            student_number="PENDING-1",
            university="Test University",
            course="Computing",
        )
        response = self.client.post(
            reverse("login"),
            {"username": user.email, "password": "StrongPass!246"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "awaiting administrator approval")
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_approved_intern_reaches_intern_dashboard(self):
        user = self.make_user(email="intern@example.com", phone="+256700000102")
        InternProfile.objects.create(
            user=user,
            student_number="ACTIVE-1",
            university="Test University",
            course="Computing",
        )
        response = self.client.post(
            reverse("login"),
            {"username": user.email, "password": "StrongPass!246"},
        )
        self.assertRedirects(response, reverse("intern-dashboard"))

    def test_staff_must_use_administration_login(self):
        user = self.make_user(
            email="staff@example.com",
            phone="+256700000103",
            is_staff=True,
        )
        response = self.client.post(
            reverse("login"),
            {"username": user.email, "password": "StrongPass!246"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "administration sign-in page")

        response = self.client.post(
            reverse("admin-login"),
            {"username": user.email, "password": "StrongPass!246"},
        )
        self.assertRedirects(response, reverse("attendance-dashboard"))

    def test_logout_redirects_each_role_to_its_login(self):
        intern = self.make_user(email="intern2@example.com", phone="+256700000104")
        InternProfile.objects.create(
            user=intern,
            student_number="ACTIVE-2",
            university="Test University",
            course="Computing",
        )
        self.client.force_login(intern)
        response = self.client.post(reverse("logout"))
        self.assertRedirects(response, reverse("login"))

        staff = self.make_user(
            email="staff2@example.com",
            phone="+256700000105",
            is_staff=True,
        )
        self.client.force_login(staff)
        response = self.client.post(reverse("logout"))
        self.assertRedirects(response, reverse("admin-login"))
