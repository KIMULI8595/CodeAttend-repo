from django import forms
from django.utils import timezone

from accounts.models import AccountStatus
from interns.models import Batch, InternProfile, Session

from .models import (
    Attendance,
    AttendanceMethod,
    AttendanceStatus,
)


class DateInput(forms.DateInput):
    input_type = "date"


class TimeInput(forms.TimeInput):
    input_type = "time"


class AttendanceReportFilterForm(forms.Form):
    """
    Validates advanced attendance history and reporting filters.
    """

    search = forms.CharField(
        required=False,
        label="Search",
        widget=forms.TextInput(
            attrs={
                "placeholder": "Name, student number or email",
            },
        ),
    )

    intern = forms.ModelChoiceField(
        queryset=InternProfile.objects.none(),
        required=False,
        empty_label="All interns",
        label="Intern",
    )

    batch = forms.ModelChoiceField(
        queryset=Batch.objects.none(),
        required=False,
        empty_label="All batches",
        label="Batch",
    )

    session = forms.ModelChoiceField(
        queryset=Session.objects.none(),
        required=False,
        empty_label="All sessions",
        label="Session",
    )

    status = forms.ChoiceField(
        required=False,
        label="Status",
        choices=[
            ("", "All statuses"),
            *AttendanceStatus.choices,
        ],
    )

    attendance_method = forms.ChoiceField(
        required=False,
        label="Method",
        choices=[
            ("", "All methods"),
            *AttendanceMethod.choices,
        ],
    )

    start_date = forms.DateField(
        required=False,
        label="From",
        widget=DateInput(),
    )

    end_date = forms.DateField(
        required=False,
        label="To",
        widget=DateInput(),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.fields["intern"].queryset = (
            InternProfile.objects
            .select_related(
                "user",
                "batch",
                "session",
            )
            .order_by(
                "student_number",
            )
        )

        self.fields["batch"].queryset = (
            Batch.objects
            .order_by(
                "name",
            )
        )

        self.fields["session"].queryset = (
            Session.objects
            .order_by(
                "name",
            )
        )

        self.fields["intern"].label_from_instance = (
            self._intern_label
        )

        for field in self.fields.values():
            existing_class = field.widget.attrs.get(
                "class",
                "",
            )

            field.widget.attrs["class"] = (
                f"{existing_class} form-control"
            ).strip()

    @staticmethod
    def _intern_label(intern):
        return (
            f"{intern.student_number} — "
            f"{intern.user.full_name}"
        )

    def clean(self):
        cleaned_data = super().clean()

        start_date = cleaned_data.get(
            "start_date",
        )

        end_date = cleaned_data.get(
            "end_date",
        )

        today = timezone.localdate()

        if start_date and start_date > today:
            self.add_error(
                "start_date",
                "The start date cannot be in the future.",
            )

        if end_date and end_date > today:
            self.add_error(
                "end_date",
                "The end date cannot be in the future.",
            )

        if (
            start_date
            and end_date
            and start_date > end_date
        ):
            self.add_error(
                "end_date",
                "The end date must be on or after the start date.",
            )

        return cleaned_data


class AttendanceCreateForm(forms.Form):
    """
    Validates staff-entered attendance records.

    The actual attendance record is created through AttendanceService
    rather than directly through this form.
    """

    intern = forms.ModelChoiceField(
        queryset=InternProfile.objects.none(),
        empty_label="Select an intern",
        label="Intern",
    )

    attendance_date = forms.DateField(
        label="Attendance date",
        widget=DateInput(),
        initial=timezone.localdate,
    )

    status = forms.ChoiceField(
        label="Attendance status",
        choices=AttendanceStatus.choices,
    )

    check_in_time = forms.TimeField(
        label="Check-in time",
        required=False,
        widget=TimeInput(
            format="%H:%M",
        ),
        input_formats=[
            "%H:%M",
            "%H:%M:%S",
        ],
        help_text=(
            "Optional for Present or Late attendance. "
            "It is automatically cleared when the status is Absent."
        ),
    )

    reason = forms.CharField(
        label="Reason",
        widget=forms.Textarea(
            attrs={
                "rows": 4,
                "placeholder": (
                    "Explain why this attendance record is being added manually."
                ),
            },
        ),
        help_text="A reason is required for audit purposes.",
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.fields["intern"].queryset = (
            InternProfile.objects.select_related(
                "user",
                "batch",
                "session",
            )
            .filter(
                user__account_status=AccountStatus.ACTIVE,
                batch__isnull=False,
                session__isnull=False,
            )
            .order_by(
                "student_number",
            )
        )

        self.fields["intern"].label_from_instance = (
            self._intern_label
        )

        self._apply_widget_classes()

    @staticmethod
    def _intern_label(intern):
        return (
            f"{intern.student_number} — "
            f"{intern.user.full_name}"
        )

    def _apply_widget_classes(self):
        for field in self.fields.values():
            existing_class = field.widget.attrs.get(
                "class",
                "",
            )

            field.widget.attrs["class"] = (
                f"{existing_class} form-control"
            ).strip()

    def clean_attendance_date(self):
        attendance_date = self.cleaned_data[
            "attendance_date"
        ]

        if attendance_date > timezone.localdate():
            raise forms.ValidationError(
                "Attendance cannot be recorded for a future date."
            )

        return attendance_date

    def clean_reason(self):
        reason = self.cleaned_data[
            "reason"
        ].strip()

        if not reason:
            raise forms.ValidationError(
                "A reason is required for manual attendance."
            )

        if len(reason) < 5:
            raise forms.ValidationError(
                "Please provide a more meaningful reason."
            )

        return reason

    def clean(self):
        cleaned_data = super().clean()

        intern = cleaned_data.get(
            "intern",
        )

        attendance_date = cleaned_data.get(
            "attendance_date",
        )

        status = cleaned_data.get(
            "status",
        )

        check_in_time = cleaned_data.get(
            "check_in_time",
        )

        if status == AttendanceStatus.ABSENT:
            cleaned_data["check_in_time"] = None

        if intern and attendance_date:
            duplicate_exists = Attendance.objects.filter(
                intern=intern,
                session=intern.session,
                attendance_date=attendance_date,
            ).exists()

            if duplicate_exists:
                raise forms.ValidationError(
                    "Attendance has already been recorded for "
                    "this intern and session on the selected date."
                )

        if (
            status in (
                AttendanceStatus.PRESENT,
                AttendanceStatus.LATE,
            )
            and check_in_time is None
        ):
            self.add_error(
                "check_in_time",
                (
                    "Enter the actual check-in time for manually "
                    "recorded Present or Late attendance."
                ),
            )

        return cleaned_data


class AttendanceUpdateForm(forms.Form):
    """
    Validates corrections to an existing attendance record.

    Intern, batch and session assignments are intentionally not editable
    here. Corrections are limited to the date, status and check-in time.
    """

    attendance_date = forms.DateField(
        label="Attendance date",
        widget=DateInput(),
    )

    status = forms.ChoiceField(
        label="Attendance status",
        choices=AttendanceStatus.choices,
    )

    check_in_time = forms.TimeField(
        label="Check-in time",
        required=False,
        widget=TimeInput(
            format="%H:%M",
        ),
        input_formats=[
            "%H:%M",
            "%H:%M:%S",
        ],
        help_text=(
            "Required for Present or Late attendance and cleared "
            "automatically for Absent attendance."
        ),
    )

    reason = forms.CharField(
        label="Correction reason",
        widget=forms.Textarea(
            attrs={
                "rows": 4,
                "placeholder": (
                    "Explain why this attendance record is being corrected."
                ),
            },
        ),
        help_text="The reason will appear in the attendance audit trail.",
    )

    def __init__(
        self,
        *args,
        attendance=None,
        **kwargs,
    ):
        self.attendance = attendance

        super().__init__(*args, **kwargs)

        if attendance is not None and not self.is_bound:
            self.initial.update(
                {
                    "attendance_date": attendance.attendance_date,
                    "status": attendance.status,
                    "check_in_time": attendance.check_in_time,
                }
            )

        self._apply_widget_classes()

    def _apply_widget_classes(self):
        for field in self.fields.values():
            existing_class = field.widget.attrs.get(
                "class",
                "",
            )

            field.widget.attrs["class"] = (
                f"{existing_class} form-control"
            ).strip()

    def clean_attendance_date(self):
        attendance_date = self.cleaned_data[
            "attendance_date"
        ]

        if attendance_date > timezone.localdate():
            raise forms.ValidationError(
                "Attendance cannot be moved to a future date."
            )

        return attendance_date

    def clean_reason(self):
        reason = self.cleaned_data[
            "reason"
        ].strip()

        if not reason:
            raise forms.ValidationError(
                "A correction reason is required."
            )

        if len(reason) < 5:
            raise forms.ValidationError(
                "Please provide a more meaningful correction reason."
            )

        return reason

    def clean(self):
        cleaned_data = super().clean()

        attendance_date = cleaned_data.get(
            "attendance_date",
        )

        status = cleaned_data.get(
            "status",
        )

        check_in_time = cleaned_data.get(
            "check_in_time",
        )

        if status == AttendanceStatus.ABSENT:
            cleaned_data["check_in_time"] = None

        if (
            status in (
                AttendanceStatus.PRESENT,
                AttendanceStatus.LATE,
            )
            and check_in_time is None
        ):
            self.add_error(
                "check_in_time",
                (
                    "A check-in time is required when attendance "
                    "is Present or Late."
                ),
            )

        if (
            self.attendance is not None
            and attendance_date is not None
        ):
            duplicate_exists = Attendance.objects.filter(
                intern=self.attendance.intern,
                session=self.attendance.session,
                attendance_date=attendance_date,
            ).exclude(
                pk=self.attendance.pk,
            ).exists()

            if duplicate_exists:
                raise forms.ValidationError(
                    "Another attendance record already exists for "
                    "this intern and session on the selected date."
                )

        if (
            self.attendance is not None
            and attendance_date is not None
            and status is not None
            and not self.errors
        ):
            effective_check_in_time = (
                None
                if status == AttendanceStatus.ABSENT
                else check_in_time
            )

            record_changed = any(
                (
                    attendance_date
                    != self.attendance.attendance_date,
                    status != self.attendance.status,
                    effective_check_in_time
                    != self.attendance.check_in_time,
                )
            )

            if not record_changed:
                raise forms.ValidationError(
                    "No attendance changes were detected."
                )

        return cleaned_data


class AttendanceDeleteForm(forms.Form):
    """
    Requires an explanation before an attendance record can be deleted.
    """

    reason = forms.CharField(
        label="Deletion reason",
        widget=forms.Textarea(
            attrs={
                "rows": 4,
                "placeholder": (
                    "Explain why this attendance record should be deleted."
                ),
            },
        ),
        help_text=(
            "The record will be removed, but the deletion will remain "
            "visible in the audit history."
        ),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.fields["reason"].widget.attrs[
            "class"
        ] = "form-control"

    def clean_reason(self):
        reason = self.cleaned_data[
            "reason"
        ].strip()

        if not reason:
            raise forms.ValidationError(
                "A deletion reason is required."
            )

        if len(reason) < 5:
            raise forms.ValidationError(
                "Please provide a more meaningful deletion reason."
            )

        return reason