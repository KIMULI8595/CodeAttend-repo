from django.contrib import messages
from django.contrib.auth import logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import LoginView
from django.shortcuts import redirect, render
from django.urls import reverse_lazy
from django.views.decorators.http import require_GET, require_POST

from .forms import AdministratorAuthenticationForm, InternAuthenticationForm


@require_GET
def access_portal(request):
    if request.user.is_authenticated:
        return redirect(
            "attendance-dashboard" if request.user.is_staff else "intern-dashboard"
        )
    return render(request, "accounts/access_portal.html")


class InternLoginView(LoginView):
    template_name = "accounts/intern_login.html"
    authentication_form = InternAuthenticationForm
    redirect_authenticated_user = False

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated:
            return redirect(
                "attendance-dashboard" if request.user.is_staff else "intern-dashboard"
            )
        return super().dispatch(request, *args, **kwargs)

    def get_success_url(self):
        return self.get_redirect_url() or reverse_lazy("intern-dashboard")


class AdministratorLoginView(LoginView):
    template_name = "accounts/admin_login.html"
    authentication_form = AdministratorAuthenticationForm
    redirect_authenticated_user = False

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated:
            return redirect(
                "attendance-dashboard" if request.user.is_staff else "intern-dashboard"
            )
        return super().dispatch(request, *args, **kwargs)

    def get_success_url(self):
        return self.get_redirect_url() or reverse_lazy("attendance-dashboard")


@login_required
@require_POST
def account_logout(request):
    was_staff = request.user.is_staff or request.user.is_superuser
    logout(request)
    messages.success(request, "You have been signed out securely.")
    return redirect("admin-login" if was_staff else "login")
