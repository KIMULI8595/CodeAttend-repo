from django.contrib import messages
from django.contrib.auth.decorators import login_required, user_passes_test
from django.core.exceptions import PermissionDenied
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET, require_POST, require_http_methods

from accounts.models import AccountStatus, User
from core.exceptions import InvalidApprovalError
from .forms import InternRegistrationForm, InternRejectionForm
from .models import InternProfile
from .services.approval import ApprovalService
from .services.qr import QRService

staff_required = user_passes_test(
    lambda user: user.is_authenticated and user.is_staff,
    login_url="admin-login",
)


@require_http_methods(["GET", "POST"])
def register_intern(request):
    form = InternRegistrationForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        form.save()
        request.session["registration_email"] = form.cleaned_data["email"]
        return redirect("registration-success")
    return render(request, "interns/register.html", {"form": form})


@require_GET
def registration_success(request):
    email = request.session.pop("registration_email", None)
    return render(request, "interns/registration_success.html", {"registered_email": email})


@login_required
@staff_required
@require_GET
def pending_interns(request):
    interns = (
        InternProfile.objects.select_related("user", "batch", "session")
        .filter(user__account_status=AccountStatus.PENDING)
        .order_by("created_at")
    )
    return render(request, "interns/pending_list.html", {"interns": interns})


@login_required
@staff_required
@require_POST
def approve_intern(request, intern_id):
    intern = get_object_or_404(InternProfile.objects.select_related("user"), pk=intern_id)
    try:
        ApprovalService.approve_intern(intern.user, request.user, request.POST.get("reason", ""))
        messages.success(request, f"{intern.user.full_name} has been approved.")
    except InvalidApprovalError as exc:
        messages.error(request, str(exc))
    return redirect("pending-interns")


@login_required
@staff_required
@require_http_methods(["GET", "POST"])
def reject_intern(request, intern_id):
    intern = get_object_or_404(InternProfile.objects.select_related("user"), pk=intern_id)
    form = InternRejectionForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        try:
            ApprovalService.reject_intern(intern.user, request.user, form.cleaned_data["reason"])
            messages.success(request, f"{intern.user.full_name} has been rejected.")
            return redirect("pending-interns")
        except InvalidApprovalError as exc:
            form.add_error(None, str(exc))
    return render(request, "interns/reject.html", {"intern": intern, "form": form})


@login_required
@require_GET
@never_cache
def intern_qr(request, intern_id):
    intern = get_object_or_404(InternProfile.objects.select_related("user"), id=intern_id)
    if not (request.user.pk == intern.user_id or request.user.is_staff):
        raise PermissionDenied("You do not have permission to view this QR code.")
    if not intern.is_approved:
        raise PermissionDenied("A QR code is not available until the intern is approved.")
    if not intern.qr_code:
        raise PermissionDenied("This intern does not have an active QR code yet.")
    qr_image = QRService.generate_qr(intern)
    response = HttpResponse(qr_image, content_type="image/png")
    response["Content-Disposition"] = f'inline; filename="intern-{intern.pk}-qr.png"'
    response["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    return response
