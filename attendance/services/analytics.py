from datetime import timedelta

from django.db.models import Avg, Count, Q
from django.utils import timezone

from accounts.models import AccountStatus
from attendance.models import (
    Attendance,
    AttendanceMethod,
    AttendanceStatus,
)
from interns.models import Batch, InternProfile


class AttendanceAnalyticsService:

    @staticmethod
    def attendance_history(
        search=None,
        intern_id=None,
        batch_id=None,
        session_id=None,
        status=None,
        attendance_method=None,
        start_date=None,
        end_date=None,
        attendance_date=None,
    ):
        records = Attendance.objects.select_related(
            "intern__user",
            "batch",
            "session",
            "attendance_location",
            "recorded_by",
        ).order_by(
            "-attendance_date",
            "-check_in_time",
        )

        if search:
            records = records.filter(
                Q(intern__student_number__icontains=search)
                | Q(intern__user__first_name__icontains=search)
                | Q(intern__user__last_name__icontains=search)
                | Q(intern__user__email__icontains=search)
            )

        if intern_id:
            records = records.filter(
                intern_id=intern_id,
            )

        if batch_id:
            records = records.filter(
                batch_id=batch_id,
            )

        if session_id:
            records = records.filter(
                session_id=session_id,
            )

        if status:
            records = records.filter(
                status=status,
            )

        if attendance_method:
            records = records.filter(
                attendance_method=attendance_method,
            )

        if attendance_date:
            records = records.filter(
                attendance_date=attendance_date,
            )
        else:
            if start_date:
                records = records.filter(
                    attendance_date__gte=start_date,
                )

            if end_date:
                records = records.filter(
                    attendance_date__lte=end_date,
                )

        return records

    @staticmethod
    def _average_time(records, field_name):
        values = list(records.exclude(**{f"{field_name}__isnull": True}).values_list(field_name, flat=True))
        if not values:
            return None
        total_seconds = sum(v.hour * 3600 + v.minute * 60 + v.second for v in values)
        average = round(total_seconds / len(values))
        from datetime import time
        return time((average // 3600) % 24, (average % 3600) // 60, average % 60)

    @staticmethod
    def report_summary(records):
        totals = records.aggregate(
            total=Count("id"),
            present=Count(
                "id",
                filter=Q(status=AttendanceStatus.PRESENT),
            ),
            late=Count(
                "id",
                filter=Q(status=AttendanceStatus.LATE),
            ),
            absent=Count(
                "id",
                filter=Q(status=AttendanceStatus.ABSENT),
            ),
            checked_in=Count(
                "id",
                filter=Q(check_in_time__isnull=False),
            ),
            checked_out=Count(
                "id",
                filter=Q(check_out_time__isnull=False),
            ),
        )

        total = totals["total"] or 0
        present = totals["present"] or 0
        late = totals["late"] or 0
        absent = totals["absent"] or 0
        attended = present + late

        attendance_rate = (
            round((attended / total) * 100, 2)
            if total > 0
            else 0
        )

        return {
            "total": total,
            "present": present,
            "late": late,
            "absent": absent,
            "checked_in": totals["checked_in"] or 0,
            "checked_out": totals["checked_out"] or 0,
            "attendance_rate": attendance_rate,
            "average_check_in": AttendanceAnalyticsService._average_time(records, "check_in_time"),
            "average_check_out": AttendanceAnalyticsService._average_time(records, "check_out_time"),
        }

    @staticmethod
    def intern_summary(intern):
        records = Attendance.objects.filter(
            intern=intern,
        )

        totals = records.aggregate(
            total=Count("id"),
            present=Count(
                "id",
                filter=Q(status=AttendanceStatus.PRESENT),
            ),
            late=Count(
                "id",
                filter=Q(status=AttendanceStatus.LATE),
            ),
            absent=Count(
                "id",
                filter=Q(status=AttendanceStatus.ABSENT),
            ),
        )

        total = totals["total"] or 0
        present = totals["present"] or 0
        late = totals["late"] or 0
        absent = totals["absent"] or 0
        attended = present + late

        attendance_percentage = (
            round((attended / total) * 100, 2)
            if total > 0
            else 0
        )

        return {
            "intern": intern,
            "records": records.select_related(
                "batch",
                "session",
                "recorded_by",
            ).order_by(
                "-attendance_date",
                "-check_in_time",
            ),
            "total": total,
            "present": present,
            "late": late,
            "absent": absent,
            "attended": attended,
            "attendance_percentage": attendance_percentage,
        }

    @staticmethod
    def batch_summary(batch):
        records = Attendance.objects.filter(
            batch=batch,
        )

        totals = records.aggregate(
            total=Count("id"),
            present=Count(
                "id",
                filter=Q(status=AttendanceStatus.PRESENT),
            ),
            late=Count(
                "id",
                filter=Q(status=AttendanceStatus.LATE),
            ),
            absent=Count(
                "id",
                filter=Q(status=AttendanceStatus.ABSENT),
            ),
        )

        total = totals["total"] or 0
        present = totals["present"] or 0
        late = totals["late"] or 0
        absent = totals["absent"] or 0
        attended = present + late

        attendance_rate = (
            round((attended / total) * 100, 2)
            if total > 0
            else 0
        )

        intern_statistics = (
            InternProfile.objects
            .filter(
                batch=batch,
            )
            .annotate(
                total_attendance=Count(
                    "attendance",
                    distinct=True,
                ),
                present_count=Count(
                    "attendance",
                    filter=Q(
                        attendance__status=AttendanceStatus.PRESENT,
                    ),
                    distinct=True,
                ),
                late_count=Count(
                    "attendance",
                    filter=Q(
                        attendance__status=AttendanceStatus.LATE,
                    ),
                    distinct=True,
                ),
                absent_count=Count(
                    "attendance",
                    filter=Q(
                        attendance__status=AttendanceStatus.ABSENT,
                    ),
                    distinct=True,
                ),
            )
            .select_related(
                "user",
                "session",
            )
            .order_by(
                "-absent_count",
                "student_number",
            )
        )

        return {
            "batch": batch,
            "total": total,
            "present": present,
            "late": late,
            "absent": absent,
            "attended": attended,
            "attendance_rate": attendance_rate,
            "intern_statistics": intern_statistics,
        }

    @staticmethod
    def dashboard_summary():
        today = timezone.localdate()
        start_date = today - timedelta(days=6)

        all_records = Attendance.objects.all()
        today_records = all_records.filter(
            attendance_date=today,
        )

        intern_totals = InternProfile.objects.aggregate(
            total=Count("id"),
            active=Count(
                "id",
                filter=Q(
                    user__is_active=True,
                    user__account_status=AccountStatus.ACTIVE,
                ),
            ),
        )

        total_interns = intern_totals["total"] or 0
        active_interns = intern_totals["active"] or 0

        today_totals = today_records.aggregate(
            total=Count("id"),
            present=Count(
                "id",
                filter=Q(status=AttendanceStatus.PRESENT),
            ),
            late=Count(
                "id",
                filter=Q(status=AttendanceStatus.LATE),
            ),
            absent=Count(
                "id",
                filter=Q(status=AttendanceStatus.ABSENT),
            ),
            checked_in=Count(
                "id",
                filter=Q(check_in_time__isnull=False),
            ),
            checked_out=Count(
                "id",
                filter=Q(check_out_time__isnull=False),
            ),
        )

        today_total = today_totals["total"] or 0
        present_today = today_totals["present"] or 0
        late_today = today_totals["late"] or 0
        absent_today = today_totals["absent"] or 0
        checked_in_today = today_totals["checked_in"] or 0
        checked_out_today = today_totals["checked_out"] or 0
        attended_today = present_today + late_today

        today_attendance_rate = (
            round((attended_today / today_total) * 100, 2)
            if today_total > 0
            else 0
        )

        check_out_completion_rate = (
            round((checked_out_today / checked_in_today) * 100, 2)
            if checked_in_today > 0
            else 0
        )

        present_percentage = (
            round((present_today / today_total) * 100, 2)
            if today_total > 0
            else 0
        )

        late_percentage = (
            round((late_today / today_total) * 100, 2)
            if today_total > 0
            else 0
        )

        absent_percentage = (
            round((absent_today / today_total) * 100, 2)
            if today_total > 0
            else 0
        )

        method_totals = today_records.aggregate(
            qr=Count(
                "id",
                filter=Q(attendance_method=AttendanceMethod.QR),
            ),
            gps=Count(
                "id",
                filter=Q(attendance_method=AttendanceMethod.GPS),
            ),
            manual=Count(
                "id",
                filter=Q(attendance_method=AttendanceMethod.MANUAL),
            ),
            automatic=Count(
                "id",
                filter=Q(attendance_method=AttendanceMethod.AUTOMATIC),
            ),
        )

        attendance_methods = [
            {
                "key": AttendanceMethod.QR,
                "label": AttendanceMethod.QR.label,
                "count": method_totals["qr"] or 0,
            },
            {
                "key": AttendanceMethod.GPS,
                "label": AttendanceMethod.GPS.label,
                "count": method_totals["gps"] or 0,
            },
            {
                "key": AttendanceMethod.MANUAL,
                "label": AttendanceMethod.MANUAL.label,
                "count": method_totals["manual"] or 0,
            },
            {
                "key": AttendanceMethod.AUTOMATIC,
                "label": AttendanceMethod.AUTOMATIC.label,
                "count": method_totals["automatic"] or 0,
            },
        ]

        daily_counts = {
            item["attendance_date"]: item["total"]
            for item in (
                all_records
                .filter(
                    attendance_date__range=(
                        start_date,
                        today,
                    ),
                )
                .values(
                    "attendance_date",
                )
                .annotate(
                    total=Count("id"),
                )
            )
        }

        trend_labels = []
        trend_values = []

        for offset in range(7):
            current_date = start_date + timedelta(days=offset)

            trend_labels.append(
                current_date.strftime("%a, %d %b")
            )
            trend_values.append(
                daily_counts.get(
                    current_date,
                    0,
                )
            )

        batch_queryset = (
            Batch.objects
            .annotate(
                intern_count=Count(
                    "internprofile",
                    distinct=True,
                ),
                attendance_count=Count(
                    "attendance",
                    distinct=True,
                ),
                present_count=Count(
                    "attendance",
                    filter=Q(
                        attendance__status=AttendanceStatus.PRESENT,
                    ),
                    distinct=True,
                ),
                late_count=Count(
                    "attendance",
                    filter=Q(
                        attendance__status=AttendanceStatus.LATE,
                    ),
                    distinct=True,
                ),
                absent_count=Count(
                    "attendance",
                    filter=Q(
                        attendance__status=AttendanceStatus.ABSENT,
                    ),
                    distinct=True,
                ),
            )
            .order_by(
                "name",
            )
        )

        batch_overview = []

        for batch in batch_queryset:
            attended_count = (
                batch.present_count
                + batch.late_count
            )

            attendance_rate = (
                round(
                    (
                        attended_count
                        / batch.attendance_count
                    ) * 100,
                    2,
                )
                if batch.attendance_count > 0
                else 0
            )

            batch_overview.append(
                {
                    "id": batch.id,
                    "name": batch.name,
                    "intern_count": batch.intern_count,
                    "attendance_count": batch.attendance_count,
                    "present_count": batch.present_count,
                    "late_count": batch.late_count,
                    "absent_count": batch.absent_count,
                    "attendance_rate": attendance_rate,
                }
            )

        top_batches = sorted(
            batch_overview,
            key=lambda item: (
                item["attendance_rate"],
                item["attendance_count"],
            ),
            reverse=True,
        )[:3]

        recent_records = (
            Attendance.objects
            .select_related(
                "intern__user",
                "batch",
                "session",
                "attendance_location",
                "recorded_by",
            )
            .order_by(
                "-attendance_date",
                "-check_in_time",
                "-created_at",
            )[:10]
        )

        return {
            "today": today,
            "total_interns": total_interns,
            "active_interns": active_interns,
            "total_attendance": all_records.count(),
            "today_attendance": today_total,
            "present_today": present_today,
            "late_today": late_today,
            "absent_today": absent_today,
            "checked_in_today": checked_in_today,
            "checked_out_today": checked_out_today,
            "today_attendance_rate": today_attendance_rate,
            "check_out_completion_rate": check_out_completion_rate,
            "present_percentage": present_percentage,
            "late_percentage": late_percentage,
            "absent_percentage": absent_percentage,
            "attendance_methods": attendance_methods,
            "trend_labels": trend_labels,
            "trend_values": trend_values,
            "batch_overview": batch_overview,
            "top_batches": top_batches,
            "recent_records": recent_records,
        }
