from django.contrib.auth import views as auth_views
from django.urls import path
from .forms import EmailLoginForm
from . import views

app_name = "accounts"
urlpatterns = [
    path("", views.dashboard, name="dashboard"),
    path("player/", views.player_dashboard, name="player_dashboard"),
    path("organizer/", views.organizer_dashboard, name="organizer_dashboard"),
    path("accounts/login/", auth_views.LoginView.as_view(template_name="accounts/login.html", authentication_form=EmailLoginForm), name="login"),
    path("accounts/logout/", auth_views.LogoutView.as_view(), name="logout"),
    path("accounts/signup/", views.signup, name="signup"),
    path("accounts/profile/", views.profile, name="profile"),
]
