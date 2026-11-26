from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render

from apps.clubs.models import ClubMembership
from apps.matches.services import get_player_dashboard_summary

from .forms import ProfileForm, SignUpForm


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
