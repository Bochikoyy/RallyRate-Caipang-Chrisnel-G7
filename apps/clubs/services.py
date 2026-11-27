import random
from decimal import Decimal

from django.db import transaction
from django.db.models import Max
from django.utils import timezone

from apps.matches.models import Match, MatchParticipant

from .models import ClubEvent, EventParticipant


def _player_rating_for_format(user, match_format):
    profile = getattr(user, "rating_profile", None)
    if profile is None:
        return Decimal("3.000")
    if match_format == ClubEvent.Format.SINGLES:
        return profile.singles_rating
    return profile.doubles_rating


def _prior_pair_counts(event):
    partner_counts = {}
    opponent_counts = {}
    existing_matches = event.matches.prefetch_related("participants").all()
    for m in existing_matches:
        parts = list(m.participants.all())
        team_a = [p.player_id for p in parts if p.team == MatchParticipant.Team.TEAM_A]
        team_b = [p.player_id for p in parts if p.team == MatchParticipant.Team.TEAM_B]
        for side in (team_a, team_b):
            if len(side) == 2:
                key = tuple(sorted(side))
                partner_counts[key] = partner_counts.get(key, 0) + 1
        for a_id in team_a:
            for b_id in team_b:
                key = tuple(sorted((a_id, b_id)))
                opponent_counts[key] = opponent_counts.get(key, 0) + 1
    return partner_counts, opponent_counts


def sync_event_games_played(event):
    scored_matches = event.matches.filter(status=Match.Status.VERIFIED).prefetch_related("participants")
    counts = {}
    for m in scored_matches:
        for p in m.participants.all():
            counts[p.player_id] = counts.get(p.player_id, 0) + 1

    for ep in event.participants.all():
        new_count = counts.get(ep.user_id, 0)
        if ep.games_played != new_count:
            ep.games_played = new_count
            ep.save(update_fields=["games_played"])


def generate_event_round(event, submitted_by):
    assigned_counts = {}
    for m in event.matches.filter(
        status__in=[Match.Status.VERIFIED, Match.Status.SCHEDULED]
    ).prefetch_related("participants"):
        for p in m.participants.all():
            assigned_counts[p.player_id] = assigned_counts.get(p.player_id, 0) + 1

    eligible = list(
        event.participants.select_related("user")
        .exclude(status=EventParticipant.Status.WAITLIST)
        .order_by("games_played", "joined_at")
    )
    eligible.sort(key=lambda ep: (assigned_counts.get(ep.user_id, 0), ep.games_played, ep.joined_at))

    per_court = event.players_per_court
    if len(eligible) < per_court:
        return []

    max_courts = min(event.courts_count, len(eligible) // per_court)
    selected_entries = eligible[: max_courts * per_court]
    selected_users = [ep.user for ep in selected_entries]

    mode = event.matchmaking_mode
    partner_counts, opponent_counts = _prior_pair_counts(event)

    if mode == ClubEvent.MatchmakingMode.RANDOM:
        random.shuffle(selected_users)
    elif mode == ClubEvent.MatchmakingMode.BALANCED:
        selected_users.sort(
            key=lambda u: (_player_rating_for_format(u, event.format), -u.id),
            reverse=True,
        )
    else:
        random.shuffle(selected_users)
        selected_users.sort(key=lambda u: assigned_counts.get(u.id, 0))

    last_round = event.matches.aggregate(mx=Max("round_number"))["mx"] or 0
    next_round = last_round + 1
    event_date = timezone.localdate(event.starts_at) if timezone.is_aware(event.starts_at) else event.starts_at.date()
    played_date = min(event_date, timezone.localdate())

    created_matches = []
    with transaction.atomic():
        for court_idx in range(max_courts):
            pod = selected_users[court_idx * per_court : (court_idx + 1) * per_court]
            if event.format == ClubEvent.Format.SINGLES:
                team_a_users = [pod[0]]
                team_b_users = [pod[1]]
            else:
                if mode == ClubEvent.MatchmakingMode.BALANCED:
                    team_a_users = [pod[0], pod[3]]
                    team_b_users = [pod[1], pod[2]]
                elif mode == ClubEvent.MatchmakingMode.ROUND_ROBIN:
                    candidates = [
                        ([pod[0], pod[3]], [pod[1], pod[2]]),
                        ([pod[0], pod[2]], [pod[1], pod[3]]),
                        ([pod[0], pod[1]], [pod[2], pod[3]]),
                    ]
                    def _repeat_cost(pair_tuple):
                        ta, tb = pair_tuple
                        ka = tuple(sorted((ta[0].id, ta[1].id)))
                        kb = tuple(sorted((tb[0].id, tb[1].id)))
                        p_cost = partner_counts.get(ka, 0) * 3 + partner_counts.get(kb, 0) * 3
                        o_cost = sum(
                            opponent_counts.get(tuple(sorted((a.id, b.id))), 0)
                            for a in ta
                            for b in tb
                        )
                        return p_cost + o_cost

                    team_a_users, team_b_users = min(candidates, key=_repeat_cost)
                else:
                    team_a_users = [pod[0], pod[1]]
                    team_b_users = [pod[2], pod[3]]

            court_num = court_idx + 1
            location_label = (
                f"{event.location} · Court {court_num}"
                if max_courts > 1
                else event.location
            )
            match = Match.objects.create(
                club=event.club,
                event=event,
                source=Match.Source.CLUB_EVENT,
                round_number=next_round,
                court_number=court_num,
                submitted_by=submitted_by,
                match_type=event.format,
                played_at=played_date,
                location=location_label,
                status=Match.Status.SCHEDULED,
            )
            MatchParticipant.objects.bulk_create(
                [
                    MatchParticipant(match=match, player=u, team=MatchParticipant.Team.TEAM_A)
                    for u in team_a_users
                ]
                + [
                    MatchParticipant(match=match, player=u, team=MatchParticipant.Team.TEAM_B)
                    for u in team_b_users
                ]
            )
            created_matches.append(match)

        if event.status == ClubEvent.Status.OPEN:
            event.status = ClubEvent.Status.IN_PROGRESS
            event.save(update_fields=["status", "updated_at"])

    return created_matches

