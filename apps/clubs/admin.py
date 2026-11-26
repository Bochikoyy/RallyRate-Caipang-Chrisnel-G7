from django.contrib import admin

from .models import Club, ClubMembership


class ClubMembershipInline(admin.TabularInline):
    model = ClubMembership
    extra = 0
    autocomplete_fields = ("user",)


@admin.register(Club)
class ClubAdmin(admin.ModelAdmin):
    list_display = ("name", "home_court", "join_code", "is_public", "created_by", "created_at")
    list_filter = ("is_public", "created_at")
    search_fields = ("name", "home_court", "join_code", "slug")
    prepopulated_fields = {"slug": ("name",)}
    inlines = [ClubMembershipInline]


@admin.register(ClubMembership)
class ClubMembershipAdmin(admin.ModelAdmin):
    list_display = ("club", "user", "role", "status", "joined_at")
    list_filter = ("role", "status")
    search_fields = ("club__name", "user__email", "user__username", "user__first_name", "user__last_name")
