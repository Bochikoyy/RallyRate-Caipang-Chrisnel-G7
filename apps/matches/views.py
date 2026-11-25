from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from .forms import MatchDisputeForm, MatchForm
from .models import Match


def _base_match_queryset():
    return Match.objects.select_related(
        "submitted_by",
        "verified_by",
        "disputed_by",
    ).prefetch_related("participants__player")


def _matches_for_user(user):
    queryset = _base_match_queryset()
    if getattr(user, "role", None) == "organizer":
        return queryset
    return queryset.filter(
        Q(submitted_by=user) | Q(participants__player=user)
    ).distinct()


@login_required
def match_list(request):
    status_filter = request.GET.get("status", "all").strip().lower()
    valid_statuses = {choice.value for choice in Match.Status}
    is_organizer = getattr(request.user, "role", None) == "organizer"

    visible_matches = _matches_for_user(request.user)
    counts = {
        "all": visible_matches.count(),
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
        if is_organizer:
            match.needs_action = match.status in (Match.Status.PENDING, Match.Status.DISPUTED)
        else:
            match.needs_action = match.can_be_verified_by(request.user)

    context = {
        "matches": matches,
        "status_filter": status_filter,
        "counts": counts,
        "is_organizer": is_organizer,
    }
    return render(request, "matches/match_list.html", context)


def _detail_context(match, user, dispute_form=None):
    return {
        "match": match,
        "can_modify": match.can_be_modified_by(user),
        "can_verify": match.can_be_verified_by(user),
        "can_dispute": match.can_be_disputed_by(user),
        "dispute_form": dispute_form or MatchDisputeForm(),
        "is_organizer": getattr(user, "role", None) == "organizer",
    }


@login_required
def match_detail(request, pk):
    match = get_object_or_404(_base_match_queryset(), pk=pk)
    if not match.can_be_viewed_by(request.user):
        raise PermissionDenied("You do not have permission to view this match.")

    return render(request, "matches/match_detail.html", _detail_context(match, request.user))


@login_required
def match_create(request):
    form = MatchForm(request.POST or None, user=request.user)
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
            "is_organizer": getattr(request.user, "role", None) == "organizer",
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
                "Only pending matches can be edited. Contact a club organizer for changes to verified or disputed matches.",
            )
            return redirect("matches:detail", pk=match.pk)
        raise PermissionDenied("You do not have permission to edit this match.")

    form = MatchForm(request.POST or None, instance=match, user=request.user)
    if request.method == "POST" and form.is_valid():
        form.save_with_participants(submitted_by=match.submitted_by)
        messages.success(request, "Match details updated.")
        return redirect("matches:detail", pk=match.pk)

    return render(
        request,
        "matches/match_form.html",
        {
            "form": form,
            "match": match,
            "is_edit": True,
            "is_organizer": getattr(request.user, "role", None) == "organizer",
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
                "Only pending matches can be deleted. Contact a club organizer for changes to verified or disputed matches.",
            )
            return redirect("matches:detail", pk=match.pk)
        raise PermissionDenied("You do not have permission to delete this match.")

    if request.method == "POST":
        match.delete()
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

    if was_disputed:
        messages.success(request, "Dispute resolved and match verified.")
    else:
        messages.success(request, "Match score confirmed and verified.")
    return redirect("matches:detail", pk=match.pk)


@login_required
@require_POST
def match_dispute(request, pk):
    match = get_object_or_404(_base_match_queryset(), pk=pk)
    if not match.can_be_viewed_by(request.user):
        raise PermissionDenied("You do not have permission to dispute this match.")
    if not match.can_be_disputed_by(request.user):
        messages.error(request, "Only an opposing player or club organizer can dispute a pending match.")
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
        messages.success(request, "Match marked as disputed for club organizer review.")
        return redirect("matches:detail", pk=match.pk)

    messages.error(request, "Please provide a clear dispute reason.")
    return render(request, "matches/match_detail.html", _detail_context(match, request.user, dispute_form=dispute_form))
