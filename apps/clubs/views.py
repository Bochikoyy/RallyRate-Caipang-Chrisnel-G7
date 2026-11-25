from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.shortcuts import render

from apps.matches.models import Match, MatchParticipant

User = get_user_model()


@login_required
def leaderboard(request):
    players = list(
        User.objects.filter(is_active=True, is_superuser=False)
        .order_by("first_name", "last_name", "username")
    )
    verified_participations = (
        MatchParticipant.objects.select_related("match", "player")
        .filter(match__status=Match.Status.VERIFIED)
        .order_by("-match__played_at", "-match__created_at")
    )

    stats_by_user = {
        u.id: {"wins": 0, "losses": 0, "last_match": None}
        for u in players
    }

    for part in verified_participations:
        bucket = stats_by_user.get(part.player_id)
        if bucket is None:
            continue
        if bucket["last_match"] is None:
            bucket["last_match"] = part.match.played_at
        winner = part.match.winner_team
        if winner == part.team:
            bucket["wins"] += 1
        elif winner is not None:
            bucket["losses"] += 1

    rows = []
    for u in players:
        s = stats_by_user[u.id]
        full_name = f"{u.first_name} {u.last_name}".strip() or u.email or u.username
        rows.append(
            {
                "user_id": u.id,
                "name": full_name,
                "is_you": u.id == request.user.id,
                "wins": s["wins"],
                "losses": s["losses"],
                "verified_total": s["wins"] + s["losses"],
                "last_match": s["last_match"],
            }
        )

    rows.sort(key=lambda r: (-r["wins"], r["losses"], r["name"].lower()))
    for idx, row in enumerate(rows, start=1):
        row["rank"] = f"{idx:02d}"

    return render(
        request,
        "clubs/leaderboard.html",
        {
            "rows": rows,
            "player_count": len(rows),
        },
    )
