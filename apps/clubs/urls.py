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
    path("<slug:slug>/events/create/", views.event_create, name="event_create"),
    path("<slug:slug>/events/<int:event_id>/", views.event_detail, name="event_detail"),
    path("<slug:slug>/events/<int:event_id>/edit/", views.event_update, name="event_update"),
    path("<slug:slug>/events/<int:event_id>/join/", views.event_join, name="event_join"),
    path("<slug:slug>/events/<int:event_id>/leave/", views.event_leave, name="event_leave"),
    path("<slug:slug>/events/<int:event_id>/add-member/", views.event_add_member, name="event_add_member"),
    path("<slug:slug>/events/<int:event_id>/participants/<int:participant_id>/remove/", views.event_remove_participant, name="event_remove_participant"),
    path("<slug:slug>/events/<int:event_id>/generate/", views.event_generate_matches, name="event_generate_matches"),
    path("<slug:slug>/events/<int:event_id>/custom-match/", views.event_custom_match, name="event_custom_match"),
    path("<slug:slug>/events/<int:event_id>/matches/<int:match_id>/score/", views.event_record_score, name="event_record_score"),
    path("<slug:slug>/events/<int:event_id>/matches/<int:match_id>/delete/", views.event_delete_match, name="event_delete_match"),
    path("<slug:slug>/events/<int:event_id>/status/", views.event_status, name="event_status"),
]
