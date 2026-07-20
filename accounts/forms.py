from django import forms
from django.contrib.auth import authenticate, get_user_model
from django.contrib.auth.forms import AuthenticationForm

from .models import AccountStatus

User = get_user_model()


class BaseRoleAuthenticationForm(AuthenticationForm):
    """Authentication form with clear account-state errors and role checks."""

    role_label = "user"

    username = forms.EmailField(
        label="Email address",
        widget=forms.EmailInput(
            attrs={
                "autofocus": True,
                "autocomplete": "email",
                "class": "form-control",
                "placeholder": "name@example.com",
            }
        ),
    )
    password = forms.CharField(
        label="Password",
        strip=False,
        widget=forms.PasswordInput(
            attrs={
                "autocomplete": "current-password",
                "class": "form-control password-input",
                "placeholder": "Enter your password",
            }
        ),
    )

    def clean(self):
        email = self.cleaned_data.get("username")
        password = self.cleaned_data.get("password")

        if email and password:
            existing_user = User.objects.filter(email__iexact=email.strip()).first()
            if existing_user:
                if existing_user.account_status == AccountStatus.PENDING:
                    raise forms.ValidationError(
                        "Your registration is still awaiting administrator approval.",
                        code="pending_approval",
                    )
                if existing_user.account_status == AccountStatus.REJECTED:
                    raise forms.ValidationError(
                        "Your registration was not approved. Contact an administrator for assistance.",
                        code="rejected_account",
                    )
                if existing_user.account_status in {
                    AccountStatus.SUSPENDED,
                    AccountStatus.DEACTIVATED,
                }:
                    raise forms.ValidationError(
                        "This account is currently unavailable. Contact an administrator.",
                        code="inactive_account",
                    )

            self.user_cache = authenticate(
                self.request,
                username=email,
                password=password,
            )
            if self.user_cache is None:
                raise self.get_invalid_login_error()
            self.confirm_login_allowed(self.user_cache)
            self.confirm_role_allowed(self.user_cache)

        return self.cleaned_data

    def confirm_role_allowed(self, user):
        raise NotImplementedError


class InternAuthenticationForm(BaseRoleAuthenticationForm):
    role_label = "intern"

    def confirm_role_allowed(self, user):
        if user.is_staff or user.is_superuser:
            raise forms.ValidationError(
                "Administrator and staff accounts must use the administration sign-in page.",
                code="wrong_portal",
            )
        if not hasattr(user, "intern_profile"):
            raise forms.ValidationError(
                "This account is not linked to an intern profile.",
                code="missing_profile",
            )
        if user.account_status != AccountStatus.ACTIVE:
            raise forms.ValidationError(
                "Your account must be approved before you can sign in.",
                code="not_approved",
            )


class AdministratorAuthenticationForm(BaseRoleAuthenticationForm):
    role_label = "administrator"

    def confirm_role_allowed(self, user):
        if not (user.is_staff or user.is_superuser):
            raise forms.ValidationError(
                "Intern accounts must use the intern sign-in page.",
                code="wrong_portal",
            )
        if user.account_status != AccountStatus.ACTIVE:
            raise forms.ValidationError(
                "This administrator account is not active.",
                code="inactive_admin",
            )
