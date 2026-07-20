from .models import Notification


def notification_context(request):
    if not request.user.is_authenticated:
        return {
            "notification_unread_count": 0,
            "notification_dropdown_items": [],
            "notification_latest_created_at": None,
        }

    unread_notifications = Notification.objects.filter(
        recipient=request.user,
        is_read=False,
    ).only(
        "id",
        "title",
        "message",
        "created_at",
    )

    dropdown_items = list(
        unread_notifications[:5]
    )

    return {
        "notification_unread_count": unread_notifications.count(),
        "notification_dropdown_items": dropdown_items,
        "notification_latest_created_at": (
            dropdown_items[0].created_at
            if dropdown_items
            else None
        ),
    }
