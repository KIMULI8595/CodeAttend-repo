import csv
from decimal import Decimal, InvalidOperation

from django.contrib import messages
from django.contrib.auth.decorators import login_required, user_passes_test
from django.core.paginator import Paginator
from django.db import models
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from accounts.models import AccountStatus
from interns.models import Batch, InternProfile, Session

from .forms import (
    AttendanceCreateForm,
    AttendanceDeleteForm,
    AttendanceReportFilterForm,
    AttendanceUpdateForm,
)
from .models import (
    Attendance,
    AttendanceAudit,
    AttendanceLocation,
    AttendanceStatus,
)
from .services.analytics import AttendanceAnalyticsService
from .services.report_export import AttendanceReportExportService
from .services.attendance import AttendanceError, AttendanceService


staff_required = user_passes_test(
    lambda user: user.is_authenticated and user.is_staff,
    login_url="admin-login",
)


def _get_authenticated_intern(request):
    return (
        InternProfile.objects
        .select_related(
            "user",
            "batch",
            "session",
        )
        .get(
            user=request.user,
        )
    )


def _parse_decimal_post_value(request, field_name, display_name):
    raw_value = request.POST.get(
        field_name,
        "",
    ).strip()

    if not raw_value:
        raise AttendanceError(
            f"{display_name} is required."
        )

    try:
        return Decimal(raw_value)
    except (
        InvalidOperation,
        TypeError,
        ValueError,
    ) as exc:
        raise AttendanceError(
            f"{display_name} must be a valid number."
        ) from exc


def _get_posted_attendance_location(request):
    location_id = request.POST.get(
        "attendance_location",
        "",
    ).strip()

    if not location_id:
        raise AttendanceError(
            "Please select an attendance location."
        )

    try:
        return AttendanceLocation.objects.get(
            pk=location_id,
            is_active=True,
        )
    except (
        AttendanceLocation.DoesNotExist,
        TypeError,
        ValueError,
    ) as exc:
        raise AttendanceError(
            "The selected attendance location is unavailable."
        ) from exc


def _get_today_attendance(intern):
    if intern.session_id is None:
        return None

    return (
        Attendance.objects
        .select_related(
            "attendance_location",
            "batch",
            "session",
            "recorded_by",
        )
        .filter(
            intern=intern,
            session=intern.session,
            attendance_date=timezone.localdate(),
        )
        .first()
    )


@login_required
@staff_required
def attendance_dashboard(request):
    summary = AttendanceAnalyticsService.dashboard_summary()

    return render(
        request,
        "attendance/dashboard.html",
        summary,
    )


@login_required
@staff_required
def scanner_page(request):
    return render(
        request,
        "attendance/scanner.html",
    )


@login_required
@staff_required
def scan_attendance(request, qr_code):
    intern = get_object_or_404(
        InternProfile.objects.select_related(
            "user",
            "batch",
            "session",
        ),
        qr_code=qr_code,
    )

    if intern.user.account_status != AccountStatus.ACTIVE:
        messages.error(
            request,
            "This intern has not been approved.",
        )
        return redirect("scanner-page")

    if intern.batch is None:
        messages.error(
            request,
            "This intern has not been assigned to a batch.",
        )
        return redirect("scanner-page")

    if intern.session is None:
        messages.error(
            request,
            "This intern has not been assigned to a session.",
        )
        return redirect("scanner-page")

    try:
        AttendanceService.record_attendance(
            intern=intern,
            recorded_by=request.user,
        )
        messages.success(
            request,
            f"{intern.user.full_name} checked in successfully.",
        )
    except AttendanceError as error:
        messages.error(
            request,
            str(error),
        )

    return redirect("scanner-page")


@login_required
def gps_attendance_page(request):
    if request.user.is_staff:
        messages.info(
            request,
            "GPS attendance is intended for intern self-service.",
        )

    try:
        intern = _get_authenticated_intern(request)
    except InternProfile.DoesNotExist:
        status_code = 200 if request.session.pop("gps_profile_error_after_post", False) else 403
        return render(
            request,
            "attendance/gps_attendance.html",
            {
                "intern": None,
                "attendance": None,
                "attendance_locations": [],
                "can_use_gps": False,
                "profile_error": (
                    "Your account is not linked to an intern profile."
                ),
            },
            status=status_code,
        )

    profile_error = None

    if intern.user.account_status != AccountStatus.ACTIVE:
        profile_error = (
            "Your account has not been approved for attendance."
        )
    elif not intern.user.is_active:
        profile_error = "Your user account is inactive."
    elif intern.batch is None:
        profile_error = "You have not been assigned to a batch."
    elif intern.session is None:
        profile_error = "You have not been assigned to a session."
    elif not intern.session.is_active:
        profile_error = "Your assigned session is inactive."

    attendance_locations = AttendanceLocation.objects.filter(
        is_active=True,
    ).order_by(
        "name",
    )

    attendance = _get_today_attendance(intern)

    context = {
        "intern": intern,
        "attendance": attendance,
        "attendance_locations": attendance_locations,
        "can_use_gps": (
            profile_error is None
            and attendance_locations.exists()
        ),
        "profile_error": profile_error,
    }

    return render(
        request,
        "attendance/gps_attendance.html",
        context,
    )


@login_required
@require_POST
def gps_check_in(request):
    try:
        intern = _get_authenticated_intern(request)
        attendance_location = _get_posted_attendance_location(request)
        latitude = _parse_decimal_post_value(
            request,
            "latitude",
            "Latitude",
        )
        longitude = _parse_decimal_post_value(
            request,
            "longitude",
            "Longitude",
        )
        accuracy = _parse_decimal_post_value(
            request,
            "accuracy",
            "GPS accuracy",
        )

        attendance = AttendanceService.gps_check_in(
            intern=intern,
            user=request.user,
            attendance_location=attendance_location,
            latitude=latitude,
            longitude=longitude,
            accuracy=accuracy,
        )

        messages.success(
            request,
            (
                "GPS attendance checked in successfully at "
                f"{attendance.attendance_location.name}. "
                f"Your status is {attendance.get_status_display()}."
            ),
        )
    except InternProfile.DoesNotExist:
        request.session["gps_profile_error_after_post"] = True
        messages.error(
            request,
            "Your account is not linked to an intern profile.",
        )
    except AttendanceError as error:
        messages.error(
            request,
            str(error),
        )

    return redirect("gps-attendance")


@login_required
@require_POST
def gps_check_out(request):
    try:
        intern = _get_authenticated_intern(request)
        attendance_location = _get_posted_attendance_location(request)
        latitude = _parse_decimal_post_value(
            request,
            "latitude",
            "Latitude",
        )
        longitude = _parse_decimal_post_value(
            request,
            "longitude",
            "Longitude",
        )
        accuracy = _parse_decimal_post_value(
            request,
            "accuracy",
            "GPS accuracy",
        )

        attendance = AttendanceService.gps_check_out(
            intern=intern,
            user=request.user,
            attendance_location=attendance_location,
            latitude=latitude,
            longitude=longitude,
            accuracy=accuracy,
        )

        messages.success(
            request,
            (
                "GPS check-out completed successfully at "
                f"{attendance.attendance_location.name}."
            ),
        )
    except InternProfile.DoesNotExist:
        messages.error(
            request,
            "Your account is not linked to an intern profile.",
        )
    except AttendanceError as error:
        messages.error(
            request,
            str(error),
        )

    return redirect("gps-attendance")


@login_required
@staff_required
def attendance_history(request):
    filter_form, filters, records = _build_attendance_report(request)
    summary = AttendanceAnalyticsService.report_summary(records)

    paginator = Paginator(records, 25)
    page = paginator.get_page(request.GET.get("page"))

    query_parameters = request.GET.copy()
    query_parameters.pop("page", None)

    context = {
        "filter_form": filter_form,
        "page": page,
        "records": page.object_list,
        "summary": summary,
        "filters": filters,
        "query_string": query_parameters.urlencode(),
    }

    return render(request, "attendance/history.html", context)


def _build_attendance_report(request):
    filter_form = AttendanceReportFilterForm(request.GET or None)

    filters = {
        "search": "",
        "intern": "",
        "intern_label": "",
        "batch": "",
        "batch_label": "",
        "session": "",
        "session_label": "",
        "status": "",
        "status_label": "",
        "attendance_method": "",
        "attendance_method_label": "",
        "start_date": "",
        "end_date": "",
    }

    if not filter_form.is_valid():
        return (
            filter_form,
            filters,
            AttendanceAnalyticsService.attendance_history(),
        )

    cleaned_data = filter_form.cleaned_data
    intern = cleaned_data.get("intern")
    batch = cleaned_data.get("batch")
    session = cleaned_data.get("session")
    status = cleaned_data.get("status") or ""
    attendance_method = cleaned_data.get("attendance_method") or ""

    filters.update(
        {
            "search": cleaned_data.get("search") or "",
            "intern": str(intern.pk) if intern else "",
            "intern_label": str(intern) if intern else "",
            "batch": str(batch.pk) if batch else "",
            "batch_label": str(batch) if batch else "",
            "session": str(session.pk) if session else "",
            "session_label": str(session) if session else "",
            "status": status,
            "status_label": dict(AttendanceStatus.choices).get(status, ""),
            "attendance_method": attendance_method,
            "attendance_method_label": dict(
                filter_form.fields["attendance_method"].choices
            ).get(attendance_method, ""),
            "start_date": (
                cleaned_data["start_date"].isoformat()
                if cleaned_data.get("start_date")
                else ""
            ),
            "end_date": (
                cleaned_data["end_date"].isoformat()
                if cleaned_data.get("end_date")
                else ""
            ),
        }
    )

    records = AttendanceAnalyticsService.attendance_history(
        search=cleaned_data.get("search") or None,
        intern_id=intern.pk if intern else None,
        batch_id=batch.pk if batch else None,
        session_id=session.pk if session else None,
        status=status or None,
        attendance_method=attendance_method or None,
        start_date=cleaned_data.get("start_date"),
        end_date=cleaned_data.get("end_date"),
    )

    return filter_form, filters, records


@login_required
@staff_required
def export_attendance_csv(request):
    filter_form, filters, records = _build_attendance_report(request)
    if not filter_form.is_valid():
        messages.error(request, "Please correct the report filters before exporting.")
        return redirect("attendance-history")

    summary = AttendanceAnalyticsService.report_summary(records)
    return AttendanceReportExportService.export_csv(records, summary, filters)


@login_required
@staff_required
def export_attendance_excel(request):
    filter_form, filters, records = _build_attendance_report(request)
    if not filter_form.is_valid():
        messages.error(request, "Please correct the report filters before exporting.")
        return redirect("attendance-history")

    summary = AttendanceAnalyticsService.report_summary(records)
    return AttendanceReportExportService.export_excel(records, summary, filters)


@login_required
@staff_required
def export_attendance_pdf(request):
    filter_form, filters, records = _build_attendance_report(request)
    if not filter_form.is_valid():
        messages.error(request, "Please correct the report filters before exporting.")
        return redirect("attendance-history")

    summary = AttendanceAnalyticsService.report_summary(records)
    return AttendanceReportExportService.export_pdf(records, summary, filters)


@login_required
@staff_required
def create_attendance(request):
    if request.method == "POST":
        form = AttendanceCreateForm(request.POST)

        if form.is_valid():
            try:
                attendance = AttendanceService.record_manual_attendance(
                    intern=form.cleaned_data["intern"],
                    status=form.cleaned_data["status"],
                    recorded_by=request.user,
                    attendance_date=form.cleaned_data[
                        "attendance_date"
                    ],
                    check_in_time=form.cleaned_data.get(
                        "check_in_time"
                    ),
                    reason=form.cleaned_data["reason"],
                )

                messages.success(
                    request,
                    (
                        "Attendance was recorded successfully for "
                        f"{attendance.intern.user.full_name}."
                    ),
                )
                return redirect("attendance-history")
            except AttendanceError as error:
                form.add_error(None, str(error))
    else:
        form = AttendanceCreateForm()

    return render(
        request,
        "attendance/create.html",
        {"form": form},
    )


@login_required
@staff_required
def update_attendance(request, attendance_id):
    attendance = get_object_or_404(
        Attendance.objects.select_related(
            "intern__user",
            "batch",
            "session",
            "recorded_by",
        ),
        pk=attendance_id,
    )

    if request.method == "POST":
        form = AttendanceUpdateForm(
            request.POST,
            attendance=attendance,
        )

        if form.is_valid():
            try:
                updated_attendance = AttendanceService.update_attendance(
                    attendance=attendance,
                    new_status=form.cleaned_data["status"],
                    performed_by=request.user,
                    reason=form.cleaned_data["reason"],
                    new_check_in_time=form.cleaned_data.get(
                        "check_in_time"
                    ),
                    new_attendance_date=form.cleaned_data[
                        "attendance_date"
                    ],
                )

                messages.success(
                    request,
                    (
                        "Attendance was updated successfully for "
                        f"{updated_attendance.intern.user.full_name}."
                    ),
                )
                return redirect("attendance-history")
            except AttendanceError as error:
                form.add_error(None, str(error))
    else:
        form = AttendanceUpdateForm(
            attendance=attendance,
        )

    return render(
        request,
        "attendance/update.html",
        {
            "attendance": attendance,
            "form": form,
        },
    )


@login_required
@staff_required
def delete_attendance(request, attendance_id):
    attendance = get_object_or_404(
        Attendance.objects.select_related(
            "intern__user",
            "batch",
            "session",
            "recorded_by",
        ),
        pk=attendance_id,
    )

    if request.method == "POST":
        form = AttendanceDeleteForm(request.POST)

        if form.is_valid():
            intern_name = attendance.intern.user.full_name

            try:
                AttendanceService.delete_attendance(
                    attendance=attendance,
                    performed_by=request.user,
                    reason=form.cleaned_data["reason"],
                )

                messages.success(
                    request,
                    (
                        "Attendance for "
                        f"{intern_name} was deleted successfully."
                    ),
                )
                return redirect("attendance-history")
            except AttendanceError as error:
                form.add_error(None, str(error))
    else:
        form = AttendanceDeleteForm()

    return render(
        request,
        "attendance/delete.html",
        {
            "attendance": attendance,
            "form": form,
        },
    )


@login_required
@staff_required
def attendance_audit_history(request):
    search = request.GET.get("search", "").strip()
    action = request.GET.get("action", "").strip()

    audits = AttendanceAudit.objects.select_related(
        "intern__user",
        "batch",
        "session",
        "performed_by",
    ).order_by(
        "-created_at",
    )

    if search:
        audits = audits.filter(
            intern__user__full_name__icontains=search,
        )

    if action:
        audits = audits.filter(
            action=action,
        )

    paginator = Paginator(audits, 30)
    page = paginator.get_page(
        request.GET.get("page"),
    )

    return render(
        request,
        "attendance/audit_history.html",
        {
            "page": page,
            "audits": page.object_list,
            "filters": {
                "search": search,
                "action": action,
            },
        },
    )


@login_required
@staff_required
def intern_attendance_detail(request, intern_id):
    intern = get_object_or_404(
        InternProfile.objects.select_related(
            "user",
            "batch",
            "session",
        ),
        pk=intern_id,
    )

    summary = AttendanceAnalyticsService.intern_summary(
        intern,
    )
    paginator = Paginator(
        summary["records"],
        20,
    )
    page = paginator.get_page(
        request.GET.get("page"),
    )

    summary["page"] = page
    summary["records"] = page.object_list

    return render(
        request,
        "attendance/intern_detail.html",
        summary,
    )


@login_required
@staff_required
def batch_attendance_detail(request, batch_id):
    batch = get_object_or_404(
        Batch,
        pk=batch_id,
    )

    summary = AttendanceAnalyticsService.batch_summary(
        batch,
    )
    paginator = Paginator(
        summary["intern_statistics"],
        25,
    )
    page = paginator.get_page(
        request.GET.get("page"),
    )

    summary["page"] = page
    summary["intern_statistics"] = page.object_list

    return render(
        request,
        "attendance/batch_detail.html",
        summary,
    )


@login_required
@staff_required
def export_batch_report(request, batch_id):
    batch = get_object_or_404(
        Batch,
        pk=batch_id,
    )

    records = (
        Attendance.objects
        .filter(
            batch=batch,
        )
        .select_related(
            "intern__user",
            "session",
            "attendance_location",
            "recorded_by",
        )
        .order_by(
            "attendance_date",
            "intern__student_number",
        )
    )

    response = HttpResponse(
        content_type="text/csv",
    )

    safe_batch_name = batch.name.replace(
        " ",
        "_",
    )

    response["Content-Disposition"] = (
        f'attachment; filename="{safe_batch_name}_attendance.csv"'
    )

    writer = csv.writer(response)
    writer.writerow(
        [
            "Student Number",
            "Intern",
            "Batch",
            "Session",
            "Attendance Date",
            "Check-in Time",
            "Check-out Time",
            "Status",
            "Attendance Method",
            "Attendance Location",
            "Recorded By",
        ]
    )

    for record in records:
        writer.writerow(
            [
                record.intern.student_number,
                record.intern.user.full_name,
                record.batch.name,
                record.session.name,
                record.attendance_date,
                record.check_in_time,
                record.check_out_time,
                record.get_status_display(),
                record.get_attendance_method_display(),
                (
                    record.attendance_location.name
                    if record.attendance_location
                    else ""
                ),
                (
                    record.recorded_by.full_name
                    if record.recorded_by
                    else ""
                ),
            ]
        )

    return response

@login_required(login_url="login")
def intern_dashboard(request):
    if request.user.is_staff or request.user.is_superuser:
        return redirect("attendance-dashboard")

    try:
        intern = _get_authenticated_intern(request)
    except InternProfile.DoesNotExist:
        return render(
            request,
            "attendance/intern_dashboard.html",
            {"intern": None, "profile_error": "Your account is not linked to an intern profile."},
            status=403,
        )

    if request.user.account_status != AccountStatus.ACTIVE or not request.user.is_active:
        messages.error(request, "Your account must be approved and active to access the dashboard.")
        return redirect("login")

    today = timezone.localdate()
    today_attendance = _get_today_attendance(intern)
    recent_records = (
        Attendance.objects.select_related("attendance_location", "session")
        .filter(intern=intern)
        .order_by("-attendance_date", "-check_in_time")[:5]
    )
    totals = Attendance.objects.filter(intern=intern).values("status").order_by().annotate(count=models.Count("id"))
    status_totals = {item["status"]: item["count"] for item in totals}

    return render(
        request,
        "attendance/intern_dashboard.html",
        {
            "intern": intern,
            "today": today,
            "today_attendance": today_attendance,
            "recent_records": recent_records,
            "present_count": status_totals.get(AttendanceStatus.PRESENT, 0),
            "late_count": status_totals.get(AttendanceStatus.LATE, 0),
            "absent_count": status_totals.get(AttendanceStatus.ABSENT, 0),
        },
    )
