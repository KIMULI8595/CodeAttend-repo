from django.db.models import Count, Q

from attendance.models import Attendance


class AttendanceReportService:


    @staticmethod
    def intern_summary(intern):

        records = Attendance.objects.filter(
            intern=intern
        )

        total = records.count()

        present = records.filter(
            status="PRESENT"
        ).count()


        percentage = 0

        if total > 0:
            percentage = (present / total) * 100


        return {
            "intern": intern,
            "total_days": total,
            "present_days": present,
            "attendance_percentage": round(
                percentage,
                2
            )
        }



    @staticmethod
    def batch_summary(batch):

        return Attendance.objects.filter(
            batch=batch
        ).values(
            "intern__user__first_name",
            "intern__user__last_name"
        ).annotate(

            total=Count("id"),

            present=Count(
                "id",
                filter=Q(
                    status="PRESENT"
                )
            )

        )