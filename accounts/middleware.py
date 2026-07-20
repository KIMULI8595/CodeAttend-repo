from django.contrib import messages
from django.contrib.auth import logout
from django.shortcuts import redirect

from .models import AccountStatus


class ActiveAccountMiddleware:
    """End authenticated sessions immediately when an account becomes unavailable."""

    exempt_names = {"logout", "login", "intern-login", "admin-login", "access-portal"}

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        user = getattr(request, "user", None)
        resolver_match = getattr(request, "resolver_match", None)
        url_name = resolver_match.url_name if resolver_match else None
        if user and user.is_authenticated and url_name not in self.exempt_names:
            if not user.is_active or user.account_status != AccountStatus.ACTIVE:
                was_staff = user.is_staff or user.is_superuser
                logout(request)
                messages.error(request, "Your account is not currently authorised to access CodeAttend.")
                return redirect("admin-login" if was_staff else "login")
        return self.get_response(request)
