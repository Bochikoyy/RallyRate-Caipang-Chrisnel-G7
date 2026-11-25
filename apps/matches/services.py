from django.db.models import Case, IntegerField, Q, Value, When

from .models import Match


def _match_queryset():
    return Match.objects.select_related(
        "submitted_by",
        "verified_by",
        "disputed_by",
    ).prefetch_related("participants__player")


def get_player_dashboard_summary(user):
    user_matches = list(
        _match_queryset()
        .filter(Q(submitted_by=user) | Q(participants__player=user))
        .distinct()
    )

    verified_count = 0
    wins = 0
    losses = 0
    pending_count = 0
    disputed_count = 0
    awaiting_confirmation = []

    for match in user_matches:
        user_team = match.participant_team_for(user)
        if match.status == Match.Status.VERIFIED and user_team is not None:
            verified_count += 1
            if match.winner_team == user_team:
                wins += 1
            elif match.winner_team is not None:
                losses += 1
        elif match.status == Match.Status.PENDING:
            pending_count += 1
            if match.can_be_verified_by(user):
                awaiting_confirmation.append(match)
        elif match.status == Match.Status.DISPUTED:
            disputed_count += 1

    return {
        "total_matches": len(user_matches),
        "verified_count": verified_count,
        "wins": wins,
        "losses": losses,
        "pending_count": pending_count,
        "disputed_count": disputed_count,
        "awaiting_confirmation": awaiting_confirmation[:5],
        "awaiting_confirmation_count": len(awaiting_confirmation),
        "recent_matches": user_matches[:5],
    }


def get_organizer_dashboard_summary():
    base_qs = _match_queryset()
    total_matches = base_qs.count()
    verified_count = base_qs.filter(status=Match.Status.VERIFIED).count()
    pending_count = base_qs.filter(status=Match.Status.PENDING).count()
    disputed_count = base_qs.filter(status=Match.Status.DISPUTED).count()

    review_queue = list(
        base_qs.filter(status__in=[Match.Status.DISPUTED, Match.Status.PENDING])
        .annotate(
            priority=Case(
                When(status=Match.Status.DISPUTED, then=Value(0)),
                default=Value(1),
                output_field=IntegerField(),
            )
        )
        .order_by("priority", "-played_at", "-created_at")[:5]
    )
    recent_matches = list(base_qs[:5])

    return {
        "total_matches": total_matches,
        "verified_count": verified_count,
        "pending_count": pending_count,
        "disputed_count": disputed_count,
        "review_queue": review_queue,
        "recent_matches": recent_matches,
    }
