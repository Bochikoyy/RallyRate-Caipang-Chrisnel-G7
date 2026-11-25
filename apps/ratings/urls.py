from django.urls import path

from . import views

app_name = "ratings"

urlpatterns = [
    path("", views.rating_history, name="history"),
    path("rules/", views.rating_rules, name="rules"),
]
