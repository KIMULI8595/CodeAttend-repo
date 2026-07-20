from django.urls import path

from .views import (
    AdministratorLoginView,
    InternLoginView,
    access_portal,
    account_logout,
)

urlpatterns = [
    path("", access_portal, name="access-portal"),
    path("login/", InternLoginView.as_view(), name="login"),
    path("intern/login/", InternLoginView.as_view(), name="intern-login"),
    path("admin/login/", AdministratorLoginView.as_view(), name="admin-login"),
    path("logout/", account_logout, name="logout"),
]
