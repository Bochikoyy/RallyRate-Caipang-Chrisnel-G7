from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from functools import wraps
from django.shortcuts import redirect, render
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
    return render(request, "accounts/dashboard.html")


@role_required(User.Role.ORGANIZER)
def organizer_dashboard(request):
    return render(request, "accounts/organizer_dashboard.html")


@login_required
def profile(request):
    form = ProfileForm(request.POST or None, instance=request.user)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Profile updated.")
        return redirect("accounts:profile")
    return render(request, "accounts/profile.html", {"form": form})
