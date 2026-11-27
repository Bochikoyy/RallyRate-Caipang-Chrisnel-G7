from django.contrib import admin
from django.urls import include, path

from apps.clubs import views as club_views

urlpatterns = [
    path("", include("apps.accounts.urls")),
    path("clubs/", include("apps.clubs.urls")),
    path("matches/", include("apps.matches.urls")),
    path("ratings/", include("apps.ratings.urls")),
    path("leaderboard/", club_views.global_leaderboard, name="global_leaderboard"),
    path("admin/", admin.site.urls),
]
