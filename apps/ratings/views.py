from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.shortcuts import render

from apps.matches.models import Match
from apps.matches.services import _decorate_match_for_player


@login_required
def rating_history(request):
    verified_matches = list(
        Match.objects.select_related("submitted_by", "verified_by")
        .prefetch_related("participants__player")
        .filter(
            status=Match.Status.VERIFIED,
            participants__player=request.user,
        )
        .distinct()
    )

    for match in verified_matches:
        _decorate_match_for_player(match, request.user)
        user_team = match.participant_team_for(request.user)
        match.player_result = "Win" if match.winner_team == user_team else "Loss"

    return render(
        request,
        "ratings/history.html",
        {
            "verified_matches": verified_matches[:10],
            "verified_count": len(verified_matches),
        },
    )


@login_required
def rating_rules(request):
    return render(request, "ratings/rules.html")
