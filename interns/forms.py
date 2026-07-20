from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.db import transaction
from phonenumber_field.formfields import PhoneNumberField

from .models import InternProfile

User = get_user_model()


class InternRegistrationForm(forms.Form):
    first_name = forms.CharField(
        label="First name",
        max_length=100,
        widget=forms.TextInput(attrs={"autocomplete": "given-name"}),
    )
    last_name = forms.CharField(
        label="Last name",
        max_length=100,
        widget=forms.TextInput(attrs={"autocomplete": "family-name"}),
    )
    email = forms.EmailField(
        label="Email address",
        widget=forms.EmailInput(attrs={"autocomplete": "email"}),
    )
    phone_number = PhoneNumberField(
        label="Phone number",
        region="UG",
        widget=forms.TextInput(
            attrs={
                "autocomplete": "tel",
                "placeholder": "+256 7XX XXX XXX",
            }
        ),
    )
    student_number = forms.CharField(
        label="Student number",
        max_length=50,
        widget=forms.TextInput(attrs={"autocomplete": "off"}),
    )
    university = forms.CharField(
        label="University or institution",
        max_length=150,
        widget=forms.TextInput(attrs={"autocomplete": "organization"}),
    )
    course = forms.CharField(
        label="Course or programme",
        max_length=150,
    )
    password = forms.CharField(
        label="Password",
        strip=False,
        widget=forms.PasswordInput(
            attrs={
                "autocomplete": "new-password",
                "aria-describedby": "password-help",
            }
        ),
        help_text="Use at least 8 characters and avoid common passwords.",
    )
    password_confirmation = forms.CharField(
        label="Confirm password",
        strip=False,
        widget=forms.PasswordInput(attrs={"autocomplete": "new-password"}),
    )
    accept_terms = forms.BooleanField(
        label="I confirm that the information provided is accurate.",
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            existing_class = field.widget.attrs.get("class", "")
            field.widget.attrs["class"] = f"form-control {existing_class}".strip()

        self.fields["accept_terms"].widget.attrs["class"] = "form-check-input"

    @staticmethod
    def _clean_title(value):
        return " ".join(value.split()).title()

    def clean_first_name(self):
        return self._clean_title(self.cleaned_data["first_name"])

    def clean_last_name(self):
        return self._clean_title(self.cleaned_data["last_name"])

    def clean_university(self):
        return " ".join(self.cleaned_data["university"].split())

    def clean_course(self):
        return " ".join(self.cleaned_data["course"].split())

    def clean_email(self):
        email = User.objects.normalize_email(self.cleaned_data["email"]).lower()
        if User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError("An account with this email already exists.")
        return email

    def clean_phone_number(self):
        phone_number = self.cleaned_data["phone_number"]
        if User.objects.filter(phone_number=phone_number).exists():
            raise forms.ValidationError("This phone number is already registered.")
        return phone_number

    def clean_student_number(self):
        student_number = self.cleaned_data["student_number"].strip().upper()
        if InternProfile.objects.filter(student_number__iexact=student_number).exists():
            raise forms.ValidationError("This student number is already registered.")
        return student_number

    def clean(self):
        cleaned_data = super().clean()
        password = cleaned_data.get("password")
        password_confirmation = cleaned_data.get("password_confirmation")

        if password and password_confirmation and password != password_confirmation:
            self.add_error("password_confirmation", "The two passwords do not match.")

        if password:
            candidate_user = User(
                email=cleaned_data.get("email", ""),
                first_name=cleaned_data.get("first_name", ""),
                last_name=cleaned_data.get("last_name", ""),
            )
            try:
                validate_password(password, user=candidate_user)
            except ValidationError as exc:
                self.add_error("password", exc)

        return cleaned_data

    @transaction.atomic
    def save(self):
        if not self.is_valid():
            raise ValueError("Cannot save an invalid registration form.")

        user = User.objects.create_user(
            email=self.cleaned_data["email"],
            password=self.cleaned_data["password"],
            first_name=self.cleaned_data["first_name"],
            last_name=self.cleaned_data["last_name"],
            phone_number=self.cleaned_data["phone_number"],
            is_active=False,
        )

        InternProfile.objects.create(
            user=user,
            student_number=self.cleaned_data["student_number"],
            university=self.cleaned_data["university"],
            course=self.cleaned_data["course"],
        )
        return user


class InternRejectionForm(forms.Form):
    reason = forms.CharField(
        label="Rejection reason",
        min_length=10,
        max_length=1000,
        widget=forms.Textarea(
            attrs={
                "rows": 5,
                "class": "form-control",
                "placeholder": "Explain clearly why this registration was rejected.",
            }
        ),
    )

    def clean_reason(self):
        return " ".join(self.cleaned_data["reason"].split())
