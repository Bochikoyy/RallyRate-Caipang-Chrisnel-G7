from django.urls import path

from . import views

app_name = "matches"

urlpatterns = [
    path("", views.match_list, name="list"),
    path("new/", views.match_create, name="create"),
    path("<int:pk>/", views.match_detail, name="detail"),
    path("<int:pk>/edit/", views.match_update, name="update"),
    path("<int:pk>/delete/", views.match_delete, name="delete"),
    path("<int:pk>/verify/", views.match_verify, name="verify"),
    path("<int:pk>/dispute/", views.match_dispute, name="dispute"),
]
