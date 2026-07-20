from django.contrib import admin, messages
from django.shortcuts import get_object_or_404, redirect
from django.urls import path, reverse

from .models import (
    ApprovalRecord,
    Batch,
    InternProfile,
    Session,
)


@admin.register(Batch)
class BatchAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "start_date",
        "end_date",
        "status",
        "created_at",
    )

    list_filter = (
        "status",
        "start_date",
        "end_date",
    )

    search_fields = (
        "name",
    )

    ordering = (
        "-start_date",
    )


@admin.register(Session)
class SessionAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "start_time",
        "end_time",
        "is_active",
        "created_at",
    )

    list_filter = (
        "is_active",
    )

    search_fields = (
        "name",
    )

    ordering = (
        "start_time",
    )


@admin.register(InternProfile)
class InternProfileAdmin(admin.ModelAdmin):
    list_display = (
        "student_number",
        "user",
        "university",
        "course",
        "batch",
        "session",
        "created_at",
    )

    list_filter = (
        "batch",
        "session",
        "university",
        "course",
    )

    search_fields = (
        "student_number",
        "user__first_name",
        "user__last_name",
        "user__email",
        "university",
        "course",
    )

    autocomplete_fields = (
        "user",
        "batch",
        "session",
    )

    readonly_fields = (
        "qr_code",
        "created_at",
    )

    list_select_related = (
        "user",
        "batch",
        "session",
    )

    ordering = (
        "student_number",
    )

    def get_urls(self):
        default_urls = super().get_urls()

        custom_urls = [
            path(
                "<int:intern_id>/reject/",
                self.admin_site.admin_view(
                    self.reject_intern_view,
                ),
                name="reject-intern",
            ),
        ]

        return custom_urls + default_urls

    def reject_intern_view(self, request, intern_id):
        intern = get_object_or_404(
            InternProfile.objects.select_related(
                "user",
            ),
            pk=intern_id,
        )

        messages.info(
            request,
            (
                f"Rejection was requested for "
                f"{intern.user.full_name}. "
                "Use the intern approval workflow to complete the action."
            ),
        )

        change_url = reverse(
            "admin:interns_internprofile_change",
            args=[intern.pk],
        )

        return redirect(change_url)


@admin.register(ApprovalRecord)
class ApprovalRecordAdmin(admin.ModelAdmin):
    list_display = (
        "user",
        "action",
        "performed_by",
        "performed_at",
    )

    list_filter = (
        "action",
        "performed_at",
    )

    search_fields = (
        "user__first_name",
        "user__last_name",
        "user__email",
        "performed_by__first_name",
        "performed_by__last_name",
        "performed_by__email",
        "reason",
    )

    autocomplete_fields = (
        "user",
        "performed_by",
    )

    readonly_fields = (
        "performed_at",
    )

    list_select_related = (
        "user",
        "performed_by",
    )

    ordering = (
        "-performed_at",
    )