from django.urls import path

from . import views

app_name = "clubs"

urlpatterns = [
    path("", views.club_hub, name="hub"),
    path("create/", views.club_create, name="create"),
    path("join/", views.join_by_code, name="join_by_code"),
    path("leaderboard/", views.global_leaderboard, name="leaderboard"),
    path("<slug:slug>/", views.club_detail, name="detail"),
    path("<slug:slug>/join/", views.join_club, name="join"),
    path("<slug:slug>/leave/", views.leave_club, name="leave"),
    path("<slug:slug>/leaderboard/", views.club_leaderboard, name="club_leaderboard"),
    path("<slug:slug>/manage/", views.club_manage, name="manage"),
    path("<slug:slug>/regenerate-code/", views.regenerate_code, name="regenerate_code"),
    path("<slug:slug>/members/<int:membership_id>/role/", views.update_member_role, name="update_member_role"),
    path("<slug:slug>/members/<int:membership_id>/approve/", views.approve_member, name="approve_member"),
    path("<slug:slug>/members/<int:membership_id>/remove/", views.remove_member, name="remove_member"),
    path("<slug:slug>/delete/", views.club_delete, name="delete"),
]
