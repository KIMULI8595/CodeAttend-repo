from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from .models import Notification
from .services import (
    NotificationError,
    NotificationService,
)


@login_required
def notification_list(request):
    notifications = Notification.objects.filter(
        recipient=request.user,
    )

    status_filter = request.GET.get(
        "status",
        "",
    ).strip()

    if status_filter == "unread":
        notifications = notifications.filter(
            is_read=False,
        )
    elif status_filter == "read":
        notifications = notifications.filter(
            is_read=True,
        )

    paginator = Paginator(
        notifications,
        20,
    )

    page = paginator.get_page(
        request.GET.get("page"),
    )

    context = {
        "page": page,
        "notifications": page.object_list,
        "status_filter": status_filter,
        "unread_count": Notification.objects.filter(
            recipient=request.user,
            is_read=False,
        ).count(),
    }

    return render(
        request,
        "notifications/notification_list.html",
        context,
    )


@login_required
def notification_detail(
    request,
    notification_id,
):
    notification = get_object_or_404(
        Notification,
        pk=notification_id,
        recipient=request.user,
    )

    if not notification.is_read:
        try:
            NotificationService.mark_as_read(
                notification=notification,
                user=request.user,
            )
        except NotificationError as exc:
            raise Http404(
                str(exc)
            ) from exc

    return render(
        request,
        "notifications/notification_detail.html",
        {
            "notification": notification,
        },
    )


@login_required
@require_POST
def notification_mark_read(
    request,
    notification_id,
):
    notification = get_object_or_404(
        Notification,
        pk=notification_id,
        recipient=request.user,
    )

    try:
        NotificationService.mark_as_read(
            notification=notification,
            user=request.user,
        )

        messages.success(
            request,
            "Notification marked as read.",
        )

    except NotificationError as exc:
        messages.error(
            request,
            str(exc),
        )

    return redirect(
        "notification-list",
    )


@login_required
@require_POST
def notification_mark_unread(
    request,
    notification_id,
):
    notification = get_object_or_404(
        Notification,
        pk=notification_id,
        recipient=request.user,
    )

    try:
        NotificationService.mark_as_unread(
            notification=notification,
            user=request.user,
        )

        messages.success(
            request,
            "Notification marked as unread.",
        )

    except NotificationError as exc:
        messages.error(
            request,
            str(exc),
        )

    return redirect(
        "notification-list",
    )


@login_required
@require_POST
def notification_mark_all_read(request):
    updated_count = NotificationService.mark_all_as_read(
        user=request.user,
    )

    if updated_count:
        messages.success(
            request,
            f"{updated_count} notification(s) marked as read.",
        )
    else:
        messages.info(
            request,
            "You have no unread notifications.",
        )

    return redirect(
        "notification-list",
    )