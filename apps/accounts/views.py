from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from functools import wraps
from django.shortcuts import redirect, render
from apps.matches.services import (
    get_organizer_dashboard_summary,
    get_player_dashboard_summary,
)
from .forms import ProfileForm, SignUpForm
from .models import User


def signup(request):
    if request.user.is_authenticated:
        return redirect("accounts:dashboard")
    form = SignUpForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        user = form.save()
        login(request, user)
        messages.success(request, "Your RallyRate account is ready.")
        return redirect("accounts:dashboard")
    return render(request, "accounts/signup.html", {"form": form})


@login_required
def dashboard(request):
    if request.user.role == User.Role.ORGANIZER:
        return redirect("accounts:organizer_dashboard")
    return redirect("accounts:player_dashboard")


def role_required(role):
    def decorator(view_func):
        @login_required
        @wraps(view_func)
        def wrapped(request, *args, **kwargs):
            if request.user.role != role:
                return redirect("accounts:dashboard")
            return view_func(request, *args, **kwargs)
        return wrapped
    return decorator


@role_required(User.Role.PLAYER)
def player_dashboard(request):
    context = get_player_dashboard_summary(request.user)
    return render(request, "accounts/dashboard.html", context)


@role_required(User.Role.ORGANIZER)
def organizer_dashboard(request):
    context = get_organizer_dashboard_summary()
    return render(request, "accounts/organizer_dashboard.html", context)


@login_required
def profile(request):
    form = ProfileForm(request.POST or None, instance=request.user)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Profile saved. You're all set for your next match.")
        return redirect("accounts:profile")
    summary = get_player_dashboard_summary(request.user)
    return render(
        request,
        "accounts/profile.html",
        {
            "form": form,
            "wins": summary["wins"],
            "losses": summary["losses"],
        },
    )
