from django.contrib import admin
from django.utils.html import format_html

from .models import (
    Attendance,
    AttendanceAudit,
    AttendanceAuditAction,
    AttendanceStatus,
    AttendanceLocation,
)
from .services.attendance import AttendanceError, AttendanceService


class AttendanceAuditInline(admin.TabularInline):
    model = AttendanceAudit

    extra = 0

    can_delete = False

    fields = (
        "action",
        "previous_status",
        "new_status",
        "reason",
        "performed_by",
        "created_at",
    )

    readonly_fields = fields

    ordering = (
        "-created_at",
    )

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(Attendance)
class AttendanceAdmin(admin.ModelAdmin):
    list_display = (
    "intern",
    "student_number",
    "attendance_date",
    "batch",
    "session",
    "status_badge",
    "attendance_method",
    "attendance_location",
    "check_in_time",
    "check_out_time",
    "recorded_by",
    "updated_at",
)

    list_filter = (
        "status",
        "attendance_method",
        "attendance_date",
        "batch",
        "session",
        "attendance_location",
    )

    search_fields = (
        "intern__student_number",
        "intern__user__first_name",
        "intern__user__last_name",
        "intern__user__email",
    )

    autocomplete_fields = (
        "intern",
        "batch",
        "session",
        "recorded_by",
        "attendance_location",
    )

    readonly_fields = (
        "created_at",
        "updated_at",
        "check_in_latitude",
        "check_in_longitude",
        "check_in_accuracy",
        "check_out_latitude",
        "check_out_longitude",
        "check_out_accuracy",
    )

    date_hierarchy = "attendance_date"

    ordering = (
        "-attendance_date",
        "-check_in_time",
    )

    list_select_related = (
        "intern__user",
        "batch",
        "session",
        "recorded_by",
    )

    inlines = (
        AttendanceAuditInline,
    )

    actions = (
        "mark_selected_present",
        "mark_selected_late",
        "mark_selected_absent",
    )

    fieldsets = (
        (
            "Intern",
            {
                "fields": (
                    "intern",
                    "batch",
                    "session",
                ),
            },
        ),
        (
        "Attendance",
        {
            "fields": (
                "attendance_date",
                "attendance_method",
                "attendance_location",
                "check_in_time",
                "check_out_time",
                "check_in_latitude",
                "check_in_longitude",
                "check_in_accuracy",
                "check_out_latitude",
                "check_out_longitude",
                "check_out_accuracy",
                "status",
                "recorded_by",
            ),
        },
    ),
    )

    @admin.display(
        description="Student number",
        ordering="intern__student_number",
    )
    def student_number(self, obj):
        return obj.intern.student_number

    @admin.display(
        description="Status",
        ordering="status",
    )
    def status_badge(self, obj):
        badge_styles = {
            AttendanceStatus.PRESENT: (
                "background:#dcfce7;color:#166534;"
            ),
            AttendanceStatus.LATE: (
                "background:#fef3c7;color:#92400e;"
            ),
            AttendanceStatus.ABSENT: (
                "background:#fee2e2;color:#991b1b;"
            ),
        }

        style = badge_styles.get(
            obj.status,
            "background:#e5e7eb;color:#374151;",
        )

        return format_html(
            '<span style="{}padding:4px 10px;'
            'border-radius:999px;font-weight:600;">{}</span>',
            style,
            obj.get_status_display(),
        )

    @admin.action(
        description="Mark selected records as present",
    )
    def mark_selected_present(self, request, queryset):
        self._update_selected_status(
            request=request,
            queryset=queryset,
            status=AttendanceStatus.PRESENT,
            reason="Bulk correction from Django administration.",
        )

    @admin.action(
        description="Mark selected records as late",
    )
    def mark_selected_late(self, request, queryset):
        self._update_selected_status(
            request=request,
            queryset=queryset,
            status=AttendanceStatus.LATE,
            reason="Bulk correction from Django administration.",
        )

    @admin.action(
        description="Mark selected records as absent",
    )
    def mark_selected_absent(self, request, queryset):
        self._update_selected_status(
            request=request,
            queryset=queryset,
            status=AttendanceStatus.ABSENT,
            reason="Bulk correction from Django administration.",
        )

    def _update_selected_status(
        self,
        *,
        request,
        queryset,
        status,
        reason,
    ):
        updated_count = 0
        failed_count = 0

        for attendance in queryset:
            try:
                AttendanceService.update_attendance(
                    attendance=attendance,
                    new_status=status,
                    performed_by=request.user,
                    reason=reason,
                )

                updated_count += 1

            except AttendanceError:
                failed_count += 1

        if updated_count:
            self.message_user(
                request,
                f"{updated_count} attendance record(s) updated.",
            )

        if failed_count:
            self.message_user(
                request,
                f"{failed_count} attendance record(s) could not be updated.",
                level="ERROR",
            )


@admin.register(AttendanceAudit)
class AttendanceAuditAdmin(admin.ModelAdmin):
    list_display = (
        "intern",
        "attendance_date",
        "action_badge",
        "previous_status",
        "new_status",
        "performed_by",
        "created_at",
    )

    list_filter = (
        "action",
        "previous_status",
        "new_status",
        "attendance_date",
        "created_at",
    )

    search_fields = (
        "intern__student_number",
        "intern__user__first_name",
        "intern__user__last_name",
        "reason",
        "performed_by__email",
    )

    readonly_fields = (
        "attendance",
        "intern",
        "batch",
        "session",
        "attendance_date",
        "action",
        "previous_status",
        "new_status",
        "previous_check_in_time",
        "new_check_in_time",
        "previous_check_out_time",
        "new_check_out_time",
        "previous_attendance_method",
        "new_attendance_method",
        "reason",
        "performed_by",
        "created_at",
    )

    list_select_related = (
        "intern__user",
        "batch",
        "session",
        "performed_by",
    )

    ordering = (
        "-created_at",
    )

    date_hierarchy = "created_at"

    @admin.display(
        description="Action",
        ordering="action",
    )
    def action_badge(self, obj):
        badge_styles = {
            AttendanceAuditAction.CREATED: (
                "background:#dbeafe;color:#1e40af;"
            ),
            AttendanceAuditAction.UPDATED: (
                "background:#fef3c7;color:#92400e;"
            ),
            AttendanceAuditAction.DELETED: (
                "background:#fee2e2;color:#991b1b;"
            ),
        }

        style = badge_styles.get(
            obj.action,
            "background:#e5e7eb;color:#374151;",
        )

        return format_html(
            '<span style="{}padding:4px 10px;'
            'border-radius:999px;font-weight:600;">{}</span>',
            style,
            obj.get_action_display(),
        )

    def has_add_permission(self, request):
        return False

    def has_change_permission(
        self,
        request,
        obj=None,
    ):
        return False

    def has_delete_permission(
        self,
        request,
        obj=None,
    ):
        return False


@admin.register(AttendanceLocation)
class AttendanceLocationAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "latitude",
        "longitude",
        "radius_metres",
        "maximum_accuracy_metres",
        "is_active",
        "updated_at",
    )

    list_filter = (
        "is_active",
    )

    search_fields = (
        "name",
    )

    ordering = (
        "name",
    )

    readonly_fields = (
        "created_at",
        "updated_at",
    )