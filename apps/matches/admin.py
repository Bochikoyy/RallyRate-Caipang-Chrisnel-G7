from django.contrib import admin
from .models import Match, MatchParticipant


class MatchParticipantInline(admin.TabularInline):
    model = MatchParticipant
    extra = 0
    autocomplete_fields = ("player",)


@admin.register(Match)
class MatchAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "match_type",
        "played_at",
        "location",
        "score_display",
        "status",
        "submitted_by",
        "verified_by",
    )
    list_filter = ("status", "match_type", "played_at")
    search_fields = ("location", "submitted_by__username", "submitted_by__email", "notes")
    readonly_fields = ("created_at", "updated_at")
    inlines = [MatchParticipantInline]
