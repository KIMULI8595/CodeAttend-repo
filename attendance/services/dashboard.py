from django.utils import timezone

from attendance.models import Attendance


class AttendanceDashboardService:

    @staticmethod
    def today_attendance():

        today = timezone.localdate()

        return Attendance.objects.filter(
            attendance_date=today
        ).select_related(
            "intern",
            "intern__user",
            "batch",
            "session",
        )


    @staticmethod
    def batch_attendance(batch):

        return Attendance.objects.filter(
            batch=batch
        ).select_related(
            "intern",
            "intern__user",
            "session",
        )


    @staticmethod
    def session_attendance(session):

        return Attendance.objects.filter(
            session=session
        ).select_related(
            "intern",
            "intern__user",
        )


    @staticmethod
    def statistics():

        today = timezone.localdate()

        records = Attendance.objects.filter(
            attendance_date=today
        )

        return {
            "total": records.count(),

            "present": records.filter(
                status="PRESENT"
            ).count(),

            "late": records.filter(
                status="LATE"
            ).count(),

            "absent": records.filter(
                status="ABSENT"
            ).count(),
        }