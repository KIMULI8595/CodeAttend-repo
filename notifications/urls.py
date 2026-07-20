from django.urls import path

from .views import (
    notification_detail,
    notification_list,
    notification_mark_all_read,
    notification_mark_read,
    notification_mark_unread,
)


urlpatterns = [
    path(
        "",
        notification_list,
        name="notification-list",
    ),
    path(
        "<int:notification_id>/",
        notification_detail,
        name="notification-detail",
    ),
    path(
        "<int:notification_id>/read/",
        notification_mark_read,
        name="notification-mark-read",
    ),
    path(
        "<int:notification_id>/unread/",
        notification_mark_unread,
        name="notification-mark-unread",
    ),
    path(
        "mark-all-read/",
        notification_mark_all_read,
        name="notification-mark-all-read",
    ),
]