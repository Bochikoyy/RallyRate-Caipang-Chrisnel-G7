from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render

from .forms import MatchForm
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

    visible_matches = _matches_for_user(request.user)
    counts = {
        "all": visible_matches.count(),
        "pending": visible_matches.filter(status=Match.Status.PENDING).count(),
        "verified": visible_matches.filter(status=Match.Status.VERIFIED).count(),
        "disputed": visible_matches.filter(status=Match.Status.DISPUTED).count(),
    }

    if status_filter in valid_statuses:
        matches = visible_matches.filter(status=status_filter)
    else:
        status_filter = "all"
        matches = visible_matches

    context = {
        "matches": matches,
        "status_filter": status_filter,
        "counts": counts,
        "is_organizer": getattr(request.user, "role", None) == "organizer",
    }
    return render(request, "matches/match_list.html", context)


@login_required
def match_detail(request, pk):
    match = get_object_or_404(_base_match_queryset(), pk=pk)
    if not match.can_be_viewed_by(request.user):
        raise PermissionDenied("You do not have permission to view this match.")

    context = {
        "match": match,
        "can_modify": match.can_be_modified_by(request.user),
        "is_organizer": getattr(request.user, "role", None) == "organizer",
    }
    return render(request, "matches/match_detail.html", context)


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
