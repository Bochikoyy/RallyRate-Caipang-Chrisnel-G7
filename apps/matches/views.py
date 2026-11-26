from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from apps.clubs.models import Club, ClubMembership

from .forms import MatchDisputeForm, MatchForm
from .models import Match
from .services import _decorate_match_for_player


def _trigger_rating_sync(match=None, full_recalc=False):
    try:
        from apps.ratings.engine import process_verified_match, recalculate_all_ratings
    except ImportError:
        return
    if full_recalc:
        recalculate_all_ratings()
    elif match is not None and match.status == Match.Status.VERIFIED:
        process_verified_match(match)


def _base_match_queryset():
    qs = Match.objects.select_related(
        "club",
        "event",
        "submitted_by",
        "verified_by",
        "disputed_by",
    ).prefetch_related("participants__player")
    if hasattr(Match, "rating_entries"):
        qs = qs.prefetch_related("rating_entries__user")
    return qs


def _managed_club_ids(user):
    if not user or not user.is_authenticated:
        return []
    return list(
        ClubMembership.objects.filter(
            user=user,
            status=ClubMembership.Status.ACTIVE,
            role__in=[ClubMembership.Role.HOST, ClubMembership.Role.CO_HOST],
        ).values_list("club_id", flat=True)
    )


def _matches_for_user(user):
    queryset = _base_match_queryset()
    if getattr(user, "role", None) == "organizer":
        return queryset
    managed_ids = _managed_club_ids(user)
    q = Q(submitted_by=user) | Q(participants__player=user)
    if managed_ids:
        q = q | Q(club_id__in=managed_ids)
    return queryset.filter(q).distinct()


@login_required
def match_list(request):
    status_filter = request.GET.get("status", "all").strip().lower()
    valid_statuses = {choice.value for choice in Match.Status}
    managed_ids = set(_managed_club_ids(request.user))
    is_manager_any = bool(managed_ids) or getattr(request.user, "role", None) == "organizer"

    visible_matches = _matches_for_user(request.user)
    counts = {
        "all": visible_matches.count(),
        "scheduled": visible_matches.filter(status=Match.Status.SCHEDULED).count(),
        "pending": visible_matches.filter(status=Match.Status.PENDING).count(),
        "verified": visible_matches.filter(status=Match.Status.VERIFIED).count(),
        "disputed": visible_matches.filter(status=Match.Status.DISPUTED).count(),
    }

    if status_filter in valid_statuses:
        matches = list(visible_matches.filter(status=status_filter))
    else:
        status_filter = "all"
        matches = list(visible_matches)

    for match in matches:
        _decorate_match_for_player(match, request.user)
        if match.is_club_manager(request.user):
            match.needs_action = match.status in (
                Match.Status.SCHEDULED,
                Match.Status.PENDING,
                Match.Status.DISPUTED,
            )
        else:
            match.needs_action = match.can_be_verified_by(request.user)

    context = {
        "matches": matches,
        "status_filter": status_filter,
        "counts": counts,
        "is_organizer": is_manager_any,
    }
    return render(request, "matches/match_list.html", context)


def _detail_context(match, user, dispute_form=None):
    user_rating_entry = None
    rating_entries = []
    if hasattr(match, "rating_entries"):
        rating_entries = list(match.rating_entries.all())
        for entry in rating_entries:
            if entry.user_id == user.id:
                user_rating_entry = entry
                break

    return {
        "match": match,
        "can_modify": match.can_be_modified_by(user),
        "can_verify": match.can_be_verified_by(user),
        "can_dispute": match.can_be_disputed_by(user),
        "dispute_form": dispute_form or MatchDisputeForm(),
        "is_organizer": match.is_club_manager(user),
        "user_rating_entry": user_rating_entry,
        "rating_entries": rating_entries,
    }


@login_required
def match_detail(request, pk):
    match = get_object_or_404(_base_match_queryset(), pk=pk)
    if not match.can_be_viewed_by(request.user):
        raise PermissionDenied("You do not have permission to view this match.")

    return render(request, "matches/match_detail.html", _detail_context(match, request.user))


@login_required
def match_create(request):
    initial_club = None
    club_slug = (request.GET.get("club") or "").strip()
    if club_slug:
        club_candidate = Club.objects.filter(slug=club_slug).first()
        if club_candidate and club_candidate.is_member(request.user):
            initial_club = club_candidate

    form = MatchForm(request.POST or None, user=request.user, initial_club=initial_club)
    if request.method == "POST" and form.is_valid():
        match = form.save_with_participants(submitted_by=request.user)
        messages.success(request, "Match logged and submitted for opponent verification.")
        return redirect("matches:detail", pk=match.pk)

    return render(
        request,
        "matches/match_form.html",
        {
            "form": form,
            "is_edit": False,
            "can_pick_lead": form.can_pick_lead,
        },
    )


@login_required
def match_update(request, pk):
    match = get_object_or_404(_base_match_queryset(), pk=pk)
    if not match.can_be_viewed_by(request.user):
        raise PermissionDenied("You do not have permission to edit this match.")
    if not match.can_be_modified_by(request.user):
        if match.submitted_by_id == request.user.id:
            messages.error(
                request,
                "Only pending matches can be edited. Contact your club host for changes to verified or disputed matches.",
            )
            return redirect("matches:detail", pk=match.pk)
        raise PermissionDenied("You do not have permission to edit this match.")

    was_verified = match.status == Match.Status.VERIFIED
    form = MatchForm(request.POST or None, instance=match, user=request.user)
    if request.method == "POST" and form.is_valid():
        updated_match = form.save_with_participants(submitted_by=match.submitted_by)
        if was_verified or updated_match.status == Match.Status.VERIFIED:
            _trigger_rating_sync(match=updated_match, full_recalc=was_verified)
        messages.success(request, "Match details updated.")
        return redirect("matches:detail", pk=match.pk)

    return render(
        request,
        "matches/match_form.html",
        {
            "form": form,
            "match": match,
            "is_edit": True,
            "can_pick_lead": form.can_pick_lead,
        },
    )


@login_required
def match_delete(request, pk):
    match = get_object_or_404(_base_match_queryset(), pk=pk)
    if not match.can_be_viewed_by(request.user):
        raise PermissionDenied("You do not have permission to delete this match.")
    if not match.can_be_modified_by(request.user):
        if match.submitted_by_id == request.user.id:
            messages.error(
                request,
                "Only pending matches can be deleted. Contact your club host for changes to verified or disputed matches.",
            )
            return redirect("matches:detail", pk=match.pk)
        raise PermissionDenied("You do not have permission to delete this match.")

    if request.method == "POST":
        was_verified = match.status == Match.Status.VERIFIED
        event = match.event
        match.delete()
        if event is not None:
            from apps.clubs.services import sync_event_games_played

            sync_event_games_played(event)
        if was_verified:
            _trigger_rating_sync(full_recalc=True)
        messages.success(request, "Match deleted.")
        return redirect("matches:list")

    return render(request, "matches/match_confirm_delete.html", {"match": match})


@login_required
@require_POST
def match_verify(request, pk):
    match = get_object_or_404(_base_match_queryset(), pk=pk)
    if not match.can_be_viewed_by(request.user):
        raise PermissionDenied("You do not have permission to verify this match.")
    if not match.can_be_verified_by(request.user):
        messages.error(request, "You cannot verify your own submission or an already verified match.")
        return redirect("matches:detail", pk=match.pk)

    was_disputed = match.status == Match.Status.DISPUTED
    match.status = Match.Status.VERIFIED
    match.verified_by = request.user
    match.verified_at = timezone.now()
    match.save(update_fields=["status", "verified_by", "verified_at", "updated_at"])

    _trigger_rating_sync(match=match)

    if was_disputed:
        messages.success(request, "Dispute resolved, match verified, and ratings updated.")
    else:
        messages.success(request, "Match score confirmed and ratings updated.")
    return redirect("matches:detail", pk=match.pk)


@login_required
@require_POST
def match_dispute(request, pk):
    match = get_object_or_404(_base_match_queryset(), pk=pk)
    if not match.can_be_viewed_by(request.user):
        raise PermissionDenied("You do not have permission to dispute this match.")
    if not match.can_be_disputed_by(request.user):
        messages.error(request, "Only an opposing player or club host can dispute a pending match.")
        return redirect("matches:detail", pk=match.pk)

    dispute_form = MatchDisputeForm(request.POST)
    if dispute_form.is_valid():
        match.status = Match.Status.DISPUTED
        match.disputed_by = request.user
        match.dispute_reason = dispute_form.cleaned_data["dispute_reason"]
        match.verified_by = None
        match.verified_at = None
        match.save(
            update_fields=[
                "status",
                "disputed_by",
                "dispute_reason",
                "verified_by",
                "verified_at",
                "updated_at",
            ]
        )
        messages.success(request, "Match marked as disputed for review.")
        return redirect("matches:detail", pk=match.pk)

    messages.error(request, "Please provide a clear dispute reason.")
    return render(request, "matches/match_detail.html", _detail_context(match, request.user, dispute_form=dispute_form))
