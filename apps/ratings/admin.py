from django.contrib import admin

from .models import PlayerRatingProfile, RatingHistory


@admin.register(PlayerRatingProfile)
class PlayerRatingProfileAdmin(admin.ModelAdmin):
    list_display = (
        "user",
        "doubles_rating",
        "doubles_reliability",
        "doubles_matches_count",
        "singles_rating",
        "singles_reliability",
        "singles_matches_count",
        "updated_at",
    )
    search_fields = ("user__username", "user__email", "user__first_name", "user__last_name")


@admin.register(RatingHistory)
class RatingHistoryAdmin(admin.ModelAdmin):
    list_display = (
        "user",
        "match",
        "match_type",
        "source",
        "rating_before",
        "delta",
        "rating_after",
        "mismatch_protected",
        "created_at",
    )
    list_filter = ("match_type", "source", "mismatch_protected")
    search_fields = ("user__username", "user__email")
