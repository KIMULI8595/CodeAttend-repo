from django.contrib import admin
from django.urls import include, path
from django.views.generic import RedirectView

urlpatterns = [
    path("", RedirectView.as_view(pattern_name="access-portal", permanent=False), name="home"),
    path("admin/", admin.site.urls),
    path("accounts/", include("accounts.urls")),
    path("interns/", include("interns.urls")),
    path("attendance/", include("attendance.urls")),
    path("notifications/", include("notifications.urls")),
]
