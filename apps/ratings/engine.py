from decimal import Decimal, ROUND_HALF_UP

from django.contrib.auth import get_user_model
from django.db import transaction

from apps.matches.models import Match, MatchParticipant

from .models import PlayerRatingProfile, RatingHistory

STARTING_RATING = PlayerRatingProfile.STARTING_RATING
MIN_RATING = PlayerRatingProfile.MIN_RATING
MAX_RATING = PlayerRatingProfile.MAX_RATING
MISMATCH_GAP_THRESHOLD = Decimal("0.500")

ELO_SCALE = 1.25
WIN_SHARE_WEIGHT = 0.35
POINT_SHARE_WEIGHT = 0.65

CLUB_EVENT_WEIGHT = 1.0
CASUAL_PEER_WEIGHT = 0.6

CLUB_RELIABILITY_GAIN = 12
PEER_RELIABILITY_GAIN = 8

K_MAX = 0.40
K_MIN = 0.12


def get_or_create_profile(user):
    profile, _ = PlayerRatingProfile.objects.get_or_create(user=user)
    return profile


def _clamp_rating(val):
    if val < MIN_RATING:
        return MIN_RATING
    if val > MAX_RATING:
        return MAX_RATING
    return val.quantize(Decimal("0.001"), rounding=ROUND_HALF_UP)


@transaction.atomic
def process_verified_match(match):
    """
    Apply DUPR-style 1.000-8.000 rating updates for a verified match.
    Idempotent: if RatingHistory rows already exist for this match, returns them.
    """
    if match.status != Match.Status.VERIFIED or not match.has_scores:
        return []

    winner = match.winner_team
    if winner is None:
        return []

    existing = list(RatingHistory.objects.filter(match=match))
    if existing:
        return existing

    parts = list(match.participants.select_related("player").all())
    team_a = [p for p in parts if p.team == MatchParticipant.Team.TEAM_A]
    team_b = [p for p in parts if p.team == MatchParticipant.Team.TEAM_B]
    if not team_a or not team_b:
        return []

    is_singles = match.match_type == Match.MatchType.SINGLES
    profiles = {p.player_id: get_or_create_profile(p.player) for p in parts}

    def _current_rating(player_id):
        prof = profiles[player_id]
        return prof.singles_rating if is_singles else prof.doubles_rating

    def _current_rel(player_id):
        prof = profiles[player_id]
        return prof.singles_reliability if is_singles else prof.doubles_reliability

    avg_a = sum(_current_rating(p.player_id) for p in team_a) / Decimal(len(team_a))
    avg_b = sum(_current_rating(p.player_id) for p in team_b) / Decimal(len(team_b))

    pts_a, pts_b = match.total_points
    total_pts = pts_a + pts_b
    point_share_a = (pts_a / total_pts) if total_pts > 0 else 0.5
    outcome_a = 1.0 if winner == MatchParticipant.Team.TEAM_A else 0.0

    perf_a = WIN_SHARE_WEIGHT * outcome_a + POINT_SHARE_WEIGHT * point_share_a
    perf_b = 1.0 - perf_a

    expected_a = 1.0 / (1.0 + (10.0 ** ((float(avg_b) - float(avg_a)) / ELO_SCALE)))
    expected_b = 1.0 - expected_a

    gap = abs(avg_a - avg_b)
    favorite_won = (
        (avg_a > avg_b and winner == MatchParticipant.Team.TEAM_A)
        or (avg_b > avg_a and winner == MatchParticipant.Team.TEAM_B)
    )
    mismatch_protected = bool(gap >= MISMATCH_GAP_THRESHOLD and favorite_won)

    is_club_event = match.source == Match.Source.CLUB_EVENT
    source_weight = CLUB_EVENT_WEIGHT if is_club_event else CASUAL_PEER_WEIGHT
    rel_gain = CLUB_RELIABILITY_GAIN if is_club_event else PEER_RELIABILITY_GAIN

    created_entries = []
    for p in parts:
        prof = profiles[p.player_id]
        r_before = _current_rating(p.player_id)
        rel_before = _current_rel(p.player_id)
        rel_after = min(100, rel_before + rel_gain)

        if p.team == MatchParticipant.Team.TEAM_A:
            exp_share = expected_a
            act_perf = perf_a
        else:
            exp_share = expected_b
            act_perf = perf_b

        if mismatch_protected:
            r_after = r_before
            delta = Decimal("0.000")
        else:
            k_factor = K_MAX - (K_MAX - K_MIN) * (rel_before / 100.0)
            raw_shift = Decimal(str(k_factor * source_weight * (act_perf - exp_share)))
            r_after = _clamp_rating(r_before + raw_shift)
            delta = (r_after - r_before).quantize(Decimal("0.001"), rounding=ROUND_HALF_UP)

        if is_singles:
            prof.singles_rating = r_after
            prof.singles_reliability = rel_after
            prof.singles_matches_count += 1
            prof.save(
                update_fields=[
                    "singles_rating",
                    "singles_reliability",
                    "singles_matches_count",
                    "updated_at",
                ]
            )
        else:
            prof.doubles_rating = r_after
            prof.doubles_reliability = rel_after
            prof.doubles_matches_count += 1
            prof.save(
                update_fields=[
                    "doubles_rating",
                    "doubles_reliability",
                    "doubles_matches_count",
                    "updated_at",
                ]
            )

        entry = RatingHistory.objects.create(
            user=p.player,
            match=match,
            match_type=match.match_type,
            source=match.source,
            rating_before=r_before,
            rating_after=r_after,
            delta=delta,
            reliability_before=rel_before,
            reliability_after=rel_after,
            expected_score=Decimal(str(round(exp_share, 4))),
            actual_performance=Decimal(str(round(act_perf, 4))),
            mismatch_protected=mismatch_protected,
        )
        created_entries.append(entry)

    return created_entries


@transaction.atomic
def recalculate_all_ratings():
    """
    Replay all verified matches in chronological order so score edits or match
    deletions leave zero rating drift.
    """
    User = get_user_model()
    RatingHistory.objects.all().delete()

    for user in User.objects.all():
        PlayerRatingProfile.objects.update_or_create(
            user=user,
            defaults={
                "singles_rating": STARTING_RATING,
                "doubles_rating": STARTING_RATING,
                "singles_reliability": 0,
                "doubles_reliability": 0,
                "singles_matches_count": 0,
                "doubles_matches_count": 0,
            },
        )

    verified_matches = (
        Match.objects.filter(status=Match.Status.VERIFIED)
        .exclude(team_a_score__isnull=True)
        .exclude(team_b_score__isnull=True)
        .order_by("played_at", "verified_at", "id")
    )
    for m in verified_matches:
        process_verified_match(m)
