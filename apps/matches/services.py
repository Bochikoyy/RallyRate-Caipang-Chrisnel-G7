from django.db.models import Case, IntegerField, Q, Value, When
from django.utils import timezone

from .models import Match, MatchParticipant


def _match_queryset():
    return Match.objects.select_related(
        "submitted_by",
        "verified_by",
        "disputed_by",
    ).prefetch_related("participants__player")


def _display_name(user):
    full_name = f"{user.first_name} {user.last_name}".strip()
    return full_name or user.email or user.username


def _decorate_match_for_player(match, user):
    user_team = match.participant_team_for(user) or MatchParticipant.Team.TEAM_A
    teammates = []
    opponents = []
    for p in match.participants.all():
        if p.team == user_team:
            if p.player_id != user.id:
                teammates.append(_display_name(p.player))
        else:
            opponents.append(_display_name(p.player))

    if match.match_type == Match.MatchType.DOUBLES:
        match.partner_line = " · ".join(teammates) if teammates else "Doubles partner"
    else:
        match.partner_line = "Singles match"
    match.opponents_line = " · ".join(opponents) if opponents else "Opponent"
    return match


def _time_greeting():
    hour = timezone.localtime().hour
    if hour < 12:
        return "Good morning"
    if hour < 18:
        return "Good afternoon"
    return "Good evening"


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
    verified_matches = []

    for match in user_matches:
        _decorate_match_for_player(match, user)
        user_team = match.participant_team_for(user)
        if match.status == Match.Status.VERIFIED and user_team is not None:
            verified_count += 1
            verified_matches.append(match)
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

    win_rate = round((wins / verified_count) * 100) if verified_count > 0 else None
    table_matches = verified_matches[:4] if verified_matches else user_matches[:4]

    return {
        "greeting": _time_greeting(),
        "is_new_player": len(user_matches) == 0,
        "total_matches": len(user_matches),
        "verified_count": verified_count,
        "wins": wins,
        "losses": losses,
        "win_rate": win_rate,
        "pending_count": pending_count,
        "disputed_count": disputed_count,
        "awaiting_confirmation": awaiting_confirmation[:5],
        "awaiting_confirmation_count": len(awaiting_confirmation),
        "recent_matches": user_matches[:5],
        "table_matches": table_matches,
        "showing_verified_only": bool(verified_matches),
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
