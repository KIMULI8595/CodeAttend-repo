from django.urls import path
from .views import (
    approve_intern,
    intern_qr,
    pending_interns,
    register_intern,
    registration_success,
    reject_intern,
)

urlpatterns = [
    path("register/", register_intern, name="intern-register"),
    path("register/success/", registration_success, name="registration-success"),
    path("pending/", pending_interns, name="pending-interns"),
    path("<int:intern_id>/approve/", approve_intern, name="approve-intern"),
    path("<int:intern_id>/reject/", reject_intern, name="reject-intern"),
    path("qr/<int:intern_id>/", intern_qr, name="intern-qr"),
]
