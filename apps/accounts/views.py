from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST

from apps.clubs.models import ClubMembership
from apps.matches.services import get_player_dashboard_summary

from .forms import ProfileForm, SignUpForm
from .models import Notification


def signup(request):
    if request.user.is_authenticated:
        return redirect("accounts:dashboard")
    form = SignUpForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        user = form.save()
        login(request, user)
        messages.success(request, "Your RallyRate account is ready. Create or join a club anytime!")
        return redirect("accounts:dashboard")
    return render(request, "accounts/signup.html", {"form": form})


@login_required
def dashboard(request):
    context = get_player_dashboard_summary(request.user)
    memberships = list(
        ClubMembership.objects.select_related("club")
        .filter(user=request.user, status=ClubMembership.Status.ACTIVE)
        .order_by("role", "club__name")
    )
    context["memberships"] = memberships
    return render(request, "accounts/dashboard.html", context)


@login_required
def player_dashboard(request):
    return redirect("accounts:dashboard")


@login_required
def organizer_dashboard(request):
    return redirect("clubs:hub")


@login_required
def profile(request):
    form = ProfileForm(request.POST or None, instance=request.user)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Profile saved. You're all set for your next match.")
        return redirect("accounts:profile")
    summary = get_player_dashboard_summary(request.user)
    memberships = list(
        ClubMembership.objects.select_related("club")
        .filter(user=request.user, status=ClubMembership.Status.ACTIVE)
        .order_by("role", "club__name")
    )
    return render(
        request,
        "accounts/profile.html",
        {
            "form": form,
            "wins": summary["wins"],
            "losses": summary["losses"],
            "doubles_rating": summary.get("doubles_rating", "3.000"),
            "singles_rating": summary.get("singles_rating", "3.000"),
            "doubles_reliability": summary.get("doubles_reliability", 0),
            "singles_reliability": summary.get("singles_reliability", 0),
            "memberships": memberships,
        },
    )


@login_required
def notifications_list(request):
    filter_mode = request.GET.get("filter", "all").strip().lower()
    qs = Notification.objects.filter(recipient=request.user).select_related("actor")
    unread_total = qs.filter(is_read=False).count()
    all_total = qs.count()

    if filter_mode == "unread":
        notifications = list(qs.filter(is_read=False)[:60])
    else:
        filter_mode = "all"
        notifications = list(qs[:60])

    return render(
        request,
        "accounts/notifications.html",
        {
            "notifications": notifications,
            "filter_mode": filter_mode,
            "unread_total": unread_total,
            "all_total": all_total,
        },
    )


@login_required
def notification_open(request, pk):
    notif = get_object_or_404(Notification, pk=pk, recipient=request.user)
    if not notif.is_read:
        notif.is_read = True
        notif.save(update_fields=["is_read"])

    target = (notif.target_url or "").strip()
    if target and url_has_allowed_host_and_scheme(target, allowed_hosts={request.get_host()}):
        return redirect(target)
    return redirect("accounts:notifications")


@login_required
@require_POST
def notifications_mark_all_read(request):
    Notification.objects.filter(recipient=request.user, is_read=False).update(is_read=True)
    next_url = (request.POST.get("next") or "").strip()
    if next_url and url_has_allowed_host_and_scheme(next_url, allowed_hosts={request.get_host()}):
        return redirect(next_url)
    return redirect("accounts:notifications")
