from django.contrib.auth.decorators import login_required
from django.shortcuts import render

from apps.matches.models import Match
from apps.matches.services import _decorate_match_for_player

from .engine import get_or_create_profile
from .models import RatingHistory


def _build_svg_points(entries_chronological, base_rating=3.0):
    values = [base_rating] + [float(e.rating_after) for e in entries_chronological]
    if len(values) < 2:
        return None

    low = min(values) - 0.15
    high = max(values) + 0.15
    if high - low < 0.4:
        mid = (high + low) / 2.0
        low, high = mid - 0.2, mid + 0.2

    width = 640.0
    height = 140.0
    step_x = width / (len(values) - 1)
    pts = []
    dots = []
    for idx, val in enumerate(values):
        x = round(idx * step_x, 1)
        norm = (val - low) / (high - low)
        y = round(height - (norm * (height - 24.0)) - 12.0, 1)
        pts.append(f"{x},{y}")
        dots.append({"x": x, "y": y, "val": f"{val:.3f}"})

    return {
        "polyline": " ".join(pts),
        "dots": dots,
        "top_label": f"{high:.2f}",
        "mid_label": f"{((high + low) / 2.0):.2f}",
        "bot_label": f"{low:.2f}",
    }


@login_required
def rating_history(request):
    match_format = request.GET.get("format", "doubles").strip().lower()
    if match_format not in ("doubles", "singles"):
        match_format = "doubles"

    profile = get_or_create_profile(request.user)
    current_rating = (
        profile.singles_rating if match_format == "singles" else profile.doubles_rating
    )
    current_reliability = (
        profile.singles_reliability
        if match_format == "singles"
        else profile.doubles_reliability
    )

    history_entries = list(
        RatingHistory.objects.select_related("match", "match__club", "match__event")
        .prefetch_related("match__participants__player")
        .filter(user=request.user, match_type=match_format)
        .order_by("-match__played_at", "-created_at", "-id")
    )

    for entry in history_entries:
        _decorate_match_for_player(entry.match, request.user)
        user_team = entry.match.participant_team_for(request.user)
        entry.player_result = "Win" if entry.match.winner_team == user_team else "Loss"

    chrono = list(reversed(history_entries[:20]))
    chart = _build_svg_points(chrono, base_rating=3.0)

    return render(
        request,
        "ratings/history.html",
        {
            "profile": profile,
            "match_format": match_format,
            "current_rating": f"{float(current_rating):.3f}",
            "current_reliability": current_reliability,
            "history_entries": history_entries[:25],
            "verified_count": len(history_entries),
            "chart": chart,
        },
    )


@login_required
def rating_rules(request):
    return render(request, "ratings/rules.html")
