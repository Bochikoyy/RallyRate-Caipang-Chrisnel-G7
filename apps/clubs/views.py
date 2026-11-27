from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.db.models import Count, Max, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from apps.matches.models import Match, MatchParticipant

from .forms import ClubEventForm, ClubForm, CustomEventMatchForm, EventScoreForm, JoinClubCodeForm
from .models import Club, ClubEvent, ClubMembership, EventParticipant
from .services import generate_event_round, sync_event_games_played

User = get_user_model()


def _display_name(user):
    full_name = f"{user.first_name} {user.last_name}".strip()
    return full_name or user.email or user.username


def _require_club_manager(club, user):
    if not club.is_manager(user):
        raise PermissionDenied("Only the club host or a co-host can manage this club.")


def _require_club_host(club, user):
    if not club.is_host(user):
        raise PermissionDenied("Only the club host can perform this action.")


def _sync_ratings(match=None, full_recalc=False):
    try:
        from apps.ratings.engine import process_verified_match, recalculate_all_ratings
    except ImportError:
        return
    if full_recalc:
        recalculate_all_ratings()
    elif match is not None and match.status == Match.Status.VERIFIED:
        process_verified_match(match)


@login_required
def club_hub(request):
    my_memberships = list(
        ClubMembership.objects.select_related("club", "club__created_by")
        .filter(user=request.user)
        .annotate(
            active_member_count=Count(
                "club__memberships",
                filter=Q(club__memberships__status=ClubMembership.Status.ACTIVE),
            )
        )
        .order_by("status", "role", "club__name")
    )
    my_club_ids = [m.club_id for m in my_memberships]

    discover_clubs = list(
        Club.objects.filter(is_public=True)
        .exclude(id__in=my_club_ids)
        .annotate(
            active_member_count=Count(
                "memberships",
                filter=Q(memberships__status=ClubMembership.Status.ACTIVE),
            )
        )
        .order_by("-active_member_count", "name")[:20]
    )

    code_form = JoinClubCodeForm()
    return render(
        request,
        "clubs/hub.html",
        {
            "my_memberships": my_memberships,
            "discover_clubs": discover_clubs,
            "code_form": code_form,
        },
    )


@login_required
def club_create(request):
    initial = {}
    if request.user.home_court:
        initial["home_court"] = request.user.home_court

    form = ClubForm(request.POST or None, initial=initial)
    if request.method == "POST" and form.is_valid():
        with transaction.atomic():
            club = form.save(commit=False)
            club.created_by = request.user
            club.save()
            ClubMembership.objects.create(
                club=club,
                user=request.user,
                role=ClubMembership.Role.HOST,
                status=ClubMembership.Status.ACTIVE,
            )
            if not request.user.home_court:
                request.user.home_court = club.name
                request.user.save(update_fields=["home_court"])
        messages.success(request, f"Created {club.name}! Share invite code {club.join_code} with your players.")
        return redirect("clubs:detail", slug=club.slug)

    return render(request, "clubs/club_form.html", {"form": form, "is_edit": False})


@login_required
@require_POST
def join_by_code(request):
    form = JoinClubCodeForm(request.POST)
    if not form.is_valid():
        messages.error(request, "Please enter a valid club invite code.")
        return redirect("clubs:hub")

    code = form.cleaned_data["join_code"]
    club = Club.objects.filter(join_code__iexact=code).first()
    if not club:
        messages.error(request, f"No club found matching invite code '{code}'.")
        return redirect("clubs:hub")

    membership, created = ClubMembership.objects.get_or_create(
        club=club,
        user=request.user,
        defaults={
            "role": ClubMembership.Role.MEMBER,
            "status": ClubMembership.Status.ACTIVE,
        },
    )
    if not created and membership.status == ClubMembership.Status.PENDING:
        membership.status = ClubMembership.Status.ACTIVE
        membership.save(update_fields=["status"])
        messages.success(request, f"Invite code accepted! You are now an active member of {club.name}.")
    elif created:
        messages.success(request, f"Welcome to {club.name}!")
    else:
        messages.info(request, f"You are already a member of {club.name}.")

    return redirect("clubs:detail", slug=club.slug)


@login_required
@require_POST
def join_club(request, slug):
    club = get_object_or_404(Club, slug=slug)
    existing = ClubMembership.objects.filter(club=club, user=request.user).first()
    if existing:
        if existing.status == ClubMembership.Status.ACTIVE:
            messages.info(request, f"You are already a member of {club.name}.")
        else:
            messages.info(request, f"Your request to join {club.name} is awaiting host approval.")
        return redirect("clubs:detail", slug=club.slug)

    if club.is_public:
        ClubMembership.objects.create(
            club=club,
            user=request.user,
            role=ClubMembership.Role.MEMBER,
            status=ClubMembership.Status.ACTIVE,
        )
        messages.success(request, f"You joined {club.name}!")
        return redirect("clubs:detail", slug=club.slug)

    ClubMembership.objects.create(
        club=club,
        user=request.user,
        role=ClubMembership.Role.MEMBER,
        status=ClubMembership.Status.PENDING,
    )
    messages.success(request, f"Join request sent to {club.name}'s hosts.")
    return redirect("clubs:hub")


@login_required
@require_POST
def leave_club(request, slug):
    club = get_object_or_404(Club, slug=slug)
    membership = club.membership_for(request.user)
    if not membership:
        return redirect("clubs:hub")

    if membership.role == ClubMembership.Role.HOST and membership.status == ClubMembership.Status.ACTIVE:
        other_hosts = club.memberships.filter(
            role=ClubMembership.Role.HOST,
            status=ClubMembership.Status.ACTIVE,
        ).exclude(pk=membership.pk)
        if not other_hosts.exists():
            messages.error(
                request,
                "Transfer the Host role to another member (or delete the club) before leaving.",
            )
            return redirect("clubs:manage", slug=club.slug)

    membership.delete()
    messages.success(request, f"You have left {club.name}.")
    return redirect("clubs:hub")


@login_required
def club_detail(request, slug):
    club = get_object_or_404(Club.objects.select_related("created_by"), slug=slug)
    membership = club.membership_for(request.user)
    is_active_member = bool(membership and membership.status == ClubMembership.Status.ACTIVE)

    if not club.is_public and not is_active_member:
        raise PermissionDenied("This club is invite-only. Join using the club's invite code.")

    active_memberships_qs = club.memberships.select_related("user").filter(
        status=ClubMembership.Status.ACTIVE
    )
    if hasattr(User, "rating_profile"):
        active_memberships_qs = active_memberships_qs.select_related("user__rating_profile")
    active_memberships = list(
        active_memberships_qs.order_by("role", "user__first_name", "user__last_name", "user__username")
    )

    pending_count = (
        club.memberships.filter(status=ClubMembership.Status.PENDING).count()
        if club.is_manager(request.user)
        else 0
    )

    events = list(
        club.events.select_related("created_by")
        .annotate(player_count=Count("participants"))
        .order_by("-starts_at")[:8]
    )

    club_matches = list(
        Match.objects.select_related("submitted_by", "verified_by", "event")
        .prefetch_related("participants__player")
        .filter(club=club)
        .order_by("-played_at", "-created_at")[:6]
    )
    disputed_club_matches = []
    if club.is_manager(request.user):
        disputed_club_matches = list(
            Match.objects.select_related("submitted_by", "disputed_by")
            .filter(club=club, status__in=[Match.Status.DISPUTED, Match.Status.PENDING])
            .order_by("status", "-played_at")[:5]
        )

    return render(
        request,
        "clubs/club_detail.html",
        {
            "club": club,
            "membership": membership,
            "is_member": is_active_member,
            "is_manager": club.is_manager(request.user),
            "is_host": club.is_host(request.user),
            "active_memberships": active_memberships,
            "member_count": len(active_memberships),
            "pending_count": pending_count,
            "events": events,
            "club_matches": club_matches,
            "disputed_club_matches": disputed_club_matches,
        },
    )


@login_required
def club_manage(request, slug):
    club = get_object_or_404(Club, slug=slug)
    _require_club_manager(club, request.user)

    form = ClubForm(request.POST or None, instance=club)
    if request.method == "POST" and form.is_valid():
        updated = form.save(commit=False)
        updated.slug = Club.generate_unique_slug(updated.name, exclude_pk=club.pk)
        updated.save()
        messages.success(request, "Club settings updated.")
        return redirect("clubs:manage", slug=updated.slug)

    active_memberships = list(
        club.memberships.select_related("user")
        .filter(status=ClubMembership.Status.ACTIVE)
        .order_by("role", "user__first_name", "user__last_name")
    )
    pending_memberships = list(
        club.memberships.select_related("user")
        .filter(status=ClubMembership.Status.PENDING)
        .order_by("joined_at")
    )

    return render(
        request,
        "clubs/club_manage.html",
        {
            "club": club,
            "form": form,
            "is_host": club.is_host(request.user),
            "is_manager": True,
            "active_memberships": active_memberships,
            "pending_memberships": pending_memberships,
        },
    )


@login_required
@require_POST
def regenerate_code(request, slug):
    club = get_object_or_404(Club, slug=slug)
    _require_club_manager(club, request.user)
    new_code = club.regenerate_join_code()
    messages.success(request, f"Invite code rotated to {new_code}.")
    return redirect("clubs:manage", slug=club.slug)


@login_required
@require_POST
def update_member_role(request, slug, membership_id):
    club = get_object_or_404(Club, slug=slug)
    _require_club_host(club, request.user)

    target = get_object_or_404(
        ClubMembership.objects.select_related("user"),
        pk=membership_id,
        club=club,
        status=ClubMembership.Status.ACTIVE,
    )
    new_role = (request.POST.get("role") or "").strip()

    if new_role == ClubMembership.Role.HOST:
        with transaction.atomic():
            my_membership = club.active_membership_for(request.user)
            if my_membership and my_membership.pk != target.pk:
                my_membership.role = ClubMembership.Role.CO_HOST
                my_membership.save(update_fields=["role"])
            target.role = ClubMembership.Role.HOST
            target.save(update_fields=["role"])
        messages.success(request, f"Transferred Host role to {_display_name(target.user)}.")
        return redirect("clubs:detail", slug=club.slug)

    if target.role == ClubMembership.Role.HOST:
        messages.error(request, "Cannot change the Host's role directly. Transfer Host to another member instead.")
        return redirect("clubs:manage", slug=club.slug)

    if new_role in (ClubMembership.Role.CO_HOST, ClubMembership.Role.MEMBER):
        target.role = new_role
        target.save(update_fields=["role"])
        messages.success(
            request,
            f"Updated {_display_name(target.user)} to {target.get_role_display()}.",
        )
    return redirect("clubs:manage", slug=club.slug)


@login_required
@require_POST
def approve_member(request, slug, membership_id):
    club = get_object_or_404(Club, slug=slug)
    _require_club_manager(club, request.user)
    target = get_object_or_404(
        ClubMembership.objects.select_related("user"),
        pk=membership_id,
        club=club,
    )
    target.status = ClubMembership.Status.ACTIVE
    target.save(update_fields=["status"])
    messages.success(request, f"Approved {_display_name(target.user)} to join {club.name}.")
    return redirect("clubs:manage", slug=club.slug)


@login_required
@require_POST
def remove_member(request, slug, membership_id):
    club = get_object_or_404(Club, slug=slug)
    _require_club_manager(club, request.user)
    target = get_object_or_404(
        ClubMembership.objects.select_related("user"),
        pk=membership_id,
        club=club,
    )
    if target.role == ClubMembership.Role.HOST:
        messages.error(request, "The club host cannot be removed.")
        return redirect("clubs:manage", slug=club.slug)
    if target.role == ClubMembership.Role.CO_HOST and not club.is_host(request.user):
        messages.error(request, "Only the club host can remove a co-host.")
        return redirect("clubs:manage", slug=club.slug)

    name = _display_name(target.user)
    target.delete()
    messages.success(request, f"Removed {name} from {club.name}.")
    return redirect("clubs:manage", slug=club.slug)


@login_required
@require_POST
def club_delete(request, slug):
    club = get_object_or_404(Club, slug=slug)
    _require_club_host(club, request.user)
    name = club.name
    with transaction.atomic():
        Match.objects.filter(club=club, status=Match.Status.SCHEDULED).delete()
        club.delete()
    messages.success(request, f"Deleted club '{name}'.")
    return redirect("clubs:hub")


# ============================================================================
# Club Events / Open Play Sessions & Match Generator
# ============================================================================


@login_required
def event_create(request, slug):
    club = get_object_or_404(Club, slug=slug)
    _require_club_manager(club, request.user)

    form = ClubEventForm(request.POST or None, initial={"location": club.home_court})
    if request.method == "POST" and form.is_valid():
        with transaction.atomic():
            event = form.save(commit=False)
            event.club = club
            event.created_by = request.user
            event.save()
            EventParticipant.objects.create(
                event=event,
                user=request.user,
                status=EventParticipant.Status.CHECKED_IN,
            )
        messages.success(request, f"Created game session '{event.title}'. Players can now join!")
        return redirect("clubs:event_detail", slug=club.slug, event_id=event.pk)

    return render(
        request,
        "clubs/event_form.html",
        {"club": club, "form": form, "is_edit": False},
    )


@login_required
def event_update(request, slug, event_id):
    club = get_object_or_404(Club, slug=slug)
    _require_club_manager(club, request.user)
    event = get_object_or_404(ClubEvent, pk=event_id, club=club)

    form = ClubEventForm(request.POST or None, instance=event)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Session settings updated.")
        return redirect("clubs:event_detail", slug=club.slug, event_id=event.pk)

    return render(
        request,
        "clubs/event_form.html",
        {"club": club, "event": event, "form": form, "is_edit": True},
    )


@login_required
def event_detail(request, slug, event_id):
    club = get_object_or_404(Club, slug=slug)
    if not club.is_public and not club.is_member(request.user):
        raise PermissionDenied("Join this club first to view its open-play sessions.")

    event = get_object_or_404(ClubEvent.objects.select_related("club", "created_by"), pk=event_id, club=club)
    is_manager = club.is_manager(request.user)
    is_member = club.is_member(request.user)

    participants_qs = event.participants.select_related("user")
    if hasattr(User, "rating_profile"):
        participants_qs = participants_qs.select_related("user__rating_profile")
    participants = list(participants_qs.order_by("status", "joined_at"))

    active_roster = [p for p in participants if p.status != EventParticipant.Status.WAITLIST]
    waitlist_roster = [p for p in participants if p.status == EventParticipant.Status.WAITLIST]
    my_participation = next((p for p in participants if p.user_id == request.user.id), None)

    matches_qs = event.matches.select_related("verified_by", "submitted_by").prefetch_related("participants__player")
    if hasattr(Match, "rating_entries"):
        matches_qs = matches_qs.prefetch_related("rating_entries")
    event_matches = list(matches_qs.order_by("-round_number", "court_number", "id"))

    for m in event_matches:
        deltas_by_user = {}
        if hasattr(m, "rating_entries"):
            for entry in m.rating_entries.all():
                sign = "+" if entry.delta > 0 else ""
                deltas_by_user[entry.user_id] = f"{sign}{entry.delta}"
        m.team_a_list = [
            {
                "name": _display_name(p.player),
                "delta": deltas_by_user.get(p.player_id),
            }
            for p in m.team_a_participants
        ]
        m.team_b_list = [
            {
                "name": _display_name(p.player),
                "delta": deltas_by_user.get(p.player_id),
            }
            for p in m.team_b_participants
        ]

    unjoined_members = []
    custom_match_form = None
    if is_manager:
        joined_user_ids = [p.user_id for p in participants]
        unjoined_members = list(
            User.objects.filter(
                club_memberships__club=club,
                club_memberships__status=ClubMembership.Status.ACTIVE,
                is_active=True,
            )
            .exclude(id__in=joined_user_ids)
            .order_by("first_name", "last_name", "username")
        )
        custom_match_form = CustomEventMatchForm(event=event)

    return render(
        request,
        "clubs/event_detail.html",
        {
            "club": club,
            "event": event,
            "is_manager": is_manager,
            "is_member": is_member,
            "active_roster": active_roster,
            "waitlist_roster": waitlist_roster,
            "my_participation": my_participation,
            "can_generate": len(active_roster) >= event.players_per_court,
            "event_matches": event_matches,
            "unjoined_members": unjoined_members,
            "custom_match_form": custom_match_form,
        },
    )


@login_required
@require_POST
def event_join(request, slug, event_id):
    club = get_object_or_404(Club, slug=slug)
    event = get_object_or_404(ClubEvent, pk=event_id, club=club)

    if not club.is_member(request.user):
        if club.is_public:
            ClubMembership.objects.get_or_create(
                club=club,
                user=request.user,
                defaults={"role": ClubMembership.Role.MEMBER, "status": ClubMembership.Status.ACTIVE},
            )
        else:
            raise PermissionDenied("You must be an active member of this club to join its games.")

    if event.status in (ClubEvent.Status.COMPLETED, ClubEvent.Status.CANCELLED):
        messages.error(request, "This session is closed to new signups.")
        return redirect("clubs:event_detail", slug=club.slug, event_id=event.pk)

    if EventParticipant.objects.filter(event=event, user=request.user).exists():
        messages.info(request, "You're already on the roster for this game.")
        return redirect("clubs:event_detail", slug=club.slug, event_id=event.pk)

    active_count = event.participants.exclude(status=EventParticipant.Status.WAITLIST).count()
    assigned_status = (
        EventParticipant.Status.JOINED
        if active_count < event.max_players
        else EventParticipant.Status.WAITLIST
    )
    EventParticipant.objects.create(event=event, user=request.user, status=assigned_status)
    if assigned_status == EventParticipant.Status.WAITLIST:
        messages.warning(request, "Session is full — you've been added to the waitlist.")
    else:
        messages.success(request, f"You're in for {event.title}!")
    return redirect("clubs:event_detail", slug=club.slug, event_id=event.pk)


@login_required
@require_POST
def event_leave(request, slug, event_id):
    club = get_object_or_404(Club, slug=slug)
    event = get_object_or_404(ClubEvent, pk=event_id, club=club)
    ep = EventParticipant.objects.filter(event=event, user=request.user).first()
    if ep:
        was_active = ep.status != EventParticipant.Status.WAITLIST
        ep.delete()
        if was_active:
            next_wait = (
                event.participants.filter(status=EventParticipant.Status.WAITLIST)
                .order_by("joined_at")
                .first()
            )
            if next_wait:
                next_wait.status = EventParticipant.Status.JOINED
                next_wait.save(update_fields=["status"])
        messages.success(request, "You have left the session roster.")
    return redirect("clubs:event_detail", slug=club.slug, event_id=event.pk)


@login_required
@require_POST
def event_add_member(request, slug, event_id):
    club = get_object_or_404(Club, slug=slug)
    _require_club_manager(club, request.user)
    event = get_object_or_404(ClubEvent, pk=event_id, club=club)

    user_id = request.POST.get("user_id")
    member_user = get_object_or_404(
        User,
        pk=user_id,
        club_memberships__club=club,
        club_memberships__status=ClubMembership.Status.ACTIVE,
    )
    EventParticipant.objects.get_or_create(
        event=event,
        user=member_user,
        defaults={"status": EventParticipant.Status.CHECKED_IN},
    )
    messages.success(request, f"Added {_display_name(member_user)} to the game.")
    return redirect("clubs:event_detail", slug=club.slug, event_id=event.pk)


@login_required
@require_POST
def event_remove_participant(request, slug, event_id, participant_id):
    club = get_object_or_404(Club, slug=slug)
    _require_club_manager(club, request.user)
    event = get_object_or_404(ClubEvent, pk=event_id, club=club)
    ep = get_object_or_404(EventParticipant.objects.select_related("user"), pk=participant_id, event=event)
    name = _display_name(ep.user)
    ep.delete()
    messages.success(request, f"Removed {name} from the session.")
    return redirect("clubs:event_detail", slug=club.slug, event_id=event.pk)


@login_required
@require_POST
def event_generate_matches(request, slug, event_id):
    club = get_object_or_404(Club, slug=slug)
    _require_club_manager(club, request.user)
    event = get_object_or_404(ClubEvent, pk=event_id, club=club)

    created = generate_event_round(event, submitted_by=request.user)
    if not created:
        messages.error(
            request,
            f"Need at least {event.players_per_court} active players in the session to generate a {event.get_format_display().lower()} match.",
        )
    else:
        messages.success(
            request,
            f"Generated {len(created)} match{'es' if len(created) != 1 else ''} for Round {created[0].round_number}! Enter scores below as games finish.",
        )
    return redirect("clubs:event_detail", slug=club.slug, event_id=event.pk)


@login_required
@require_POST
def event_custom_match(request, slug, event_id):
    club = get_object_or_404(Club, slug=slug)
    _require_club_manager(club, request.user)
    event = get_object_or_404(ClubEvent, pk=event_id, club=club)

    form = CustomEventMatchForm(request.POST, event=event)
    if not form.is_valid():
        errors = "; ".join(str(e) for errs in form.errors.values() for e in errs)
        messages.error(request, errors or "Invalid player pairing.")
        return redirect("clubs:event_detail", slug=club.slug, event_id=event.pk)

    team_a = [p for p in (form.cleaned_data.get("team_a_1"), form.cleaned_data.get("team_a_2")) if p]
    team_b = [p for p in (form.cleaned_data.get("team_b_1"), form.cleaned_data.get("team_b_2")) if p]
    last_round = event.matches.aggregate(mx=Max("round_number"))["mx"] or 1
    event_date = timezone.localdate(event.starts_at) if timezone.is_aware(event.starts_at) else event.starts_at.date()
    played_date = min(event_date, timezone.localdate())

    with transaction.atomic():
        match = Match.objects.create(
            club=club,
            event=event,
            source=Match.Source.CLUB_EVENT,
            round_number=last_round,
            court_number=1,
            submitted_by=request.user,
            match_type=event.format,
            played_at=played_date,
            location=event.location,
            status=Match.Status.SCHEDULED,
        )
        MatchParticipant.objects.bulk_create(
            [MatchParticipant(match=match, player=u, team=MatchParticipant.Team.TEAM_A) for u in team_a]
            + [MatchParticipant(match=match, player=u, team=MatchParticipant.Team.TEAM_B) for u in team_b]
        )
        if event.status == ClubEvent.Status.OPEN:
            event.status = ClubEvent.Status.IN_PROGRESS
            event.save(update_fields=["status", "updated_at"])
    messages.success(request, "Custom matchup added to the board.")
    return redirect("clubs:event_detail", slug=club.slug, event_id=event.pk)


@login_required
@require_POST
def event_record_score(request, slug, event_id, match_id):
    club = get_object_or_404(Club, slug=slug)
    _require_club_manager(club, request.user)
    event = get_object_or_404(ClubEvent, pk=event_id, club=club)
    match = get_object_or_404(Match, pk=match_id, event=event, club=club)

    form = EventScoreForm(request.POST)
    if not form.is_valid():
        errors = "; ".join(str(e) for errs in form.errors.values() for e in errs)
        messages.error(request, errors or "Invalid pickleball score.")
        return redirect("clubs:event_detail", slug=club.slug, event_id=event.pk)

    was_already_verified = match.status == Match.Status.VERIFIED
    match.team_a_score = form.cleaned_data["team_a_score"]
    match.team_b_score = form.cleaned_data["team_b_score"]
    match.game_2_team_a = form.cleaned_data["game_2_team_a"]
    match.game_2_team_b = form.cleaned_data["game_2_team_b"]
    match.game_3_team_a = form.cleaned_data["game_3_team_a"]
    match.game_3_team_b = form.cleaned_data["game_3_team_b"]
    match.status = Match.Status.VERIFIED
    match.verified_by = request.user
    match.verified_at = timezone.now()
    match.save()

    sync_event_games_played(event)
    _sync_ratings(match=match, full_recalc=was_already_verified)

    messages.success(
        request,
        f"Score {match.score_display} saved & verified!",
    )
    return redirect("clubs:event_detail", slug=club.slug, event_id=event.pk)


@login_required
@require_POST
def event_delete_match(request, slug, event_id, match_id):
    club = get_object_or_404(Club, slug=slug)
    _require_club_manager(club, request.user)
    event = get_object_or_404(ClubEvent, pk=event_id, club=club)
    match = get_object_or_404(Match, pk=match_id, event=event, club=club)

    was_verified = match.status == Match.Status.VERIFIED
    match.delete()
    sync_event_games_played(event)
    if was_verified:
        _sync_ratings(full_recalc=True)
    messages.success(request, "Match removed from session.")
    return redirect("clubs:event_detail", slug=club.slug, event_id=event.pk)


@login_required
@require_POST
def event_status(request, slug, event_id):
    club = get_object_or_404(Club, slug=slug)
    _require_club_manager(club, request.user)
    event = get_object_or_404(ClubEvent, pk=event_id, club=club)
    new_status = (request.POST.get("status") or "").strip()
    valid = {choice.value for choice in ClubEvent.Status}
    if new_status in valid:
        event.status = new_status
        event.save(update_fields=["status", "updated_at"])
        messages.success(request, f"Session marked as {event.get_status_display()}.")
    return redirect("clubs:event_detail", slug=club.slug, event_id=event.pk)


def _build_leaderboard_rows(users, current_user, club=None, match_format="doubles", club_roles=None):
    user_ids = [u.id for u in users]
    part_qs = (
        MatchParticipant.objects.select_related("match", "player")
        .filter(match__status=Match.Status.VERIFIED, player_id__in=user_ids)
        .order_by("-match__played_at", "-match__created_at")
    )
    if club is not None:
        part_qs = part_qs.filter(match__club=club)
    if match_format in (Match.MatchType.SINGLES, Match.MatchType.DOUBLES):
        part_qs = part_qs.filter(match__match_type=match_format)

    stats_by_user = {u.id: {"wins": 0, "losses": 0, "last_match": None} for u in users}
    for part in part_qs:
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
    for u in users:
        s = stats_by_user[u.id]
        profile = getattr(u, "rating_profile", None)
        if profile is not None:
            rating_val = (
                profile.singles_rating if match_format == "singles" else profile.doubles_rating
            )
            reliability_val = (
                profile.singles_reliability
                if match_format == "singles"
                else profile.doubles_reliability
            )
        else:
            rating_val = "3.000"
            reliability_val = 0

        total_games = s["wins"] + s["losses"]
        win_pct = round((s["wins"] / total_games) * 100) if total_games > 0 else None

        rows.append(
            {
                "user_id": u.id,
                "name": _display_name(u),
                "home_court": u.home_court,
                "club_role": (club_roles or {}).get(u.id),
                "is_you": u.id == current_user.id,
                "rating": f"{float(rating_val):.3f}",
                "rating_num": float(rating_val),
                "reliability": reliability_val,
                "wins": s["wins"],
                "losses": s["losses"],
                "verified_total": total_games,
                "win_pct": win_pct,
                "last_match": s["last_match"],
            }
        )

    rows.sort(
        key=lambda r: (
            -r["rating_num"],
            -r["wins"],
            r["losses"],
            r["name"].lower(),
        )
    )
    for idx, row in enumerate(rows, start=1):
        row["rank"] = f"{idx:02d}"
    return rows


@login_required
def global_leaderboard(request):
    match_format = request.GET.get("format", "doubles").strip().lower()
    if match_format not in ("doubles", "singles"):
        match_format = "doubles"

    players = list(
        User.objects.filter(is_active=True, is_superuser=False)
        .select_related("rating_profile")
        .order_by("first_name", "last_name", "username")
    )

    rows = _build_leaderboard_rows(
        players,
        request.user,
        club=None,
        match_format=match_format,
    )
    my_clubs = list(
        Club.objects.filter(
            memberships__user=request.user,
            memberships__status=ClubMembership.Status.ACTIVE,
        ).order_by("name")
    )
    return render(
        request,
        "clubs/leaderboard.html",
        {
            "rows": rows,
            "player_count": len(rows),
            "scope": "local",
            "club": None,
            "my_clubs": my_clubs,
            "match_format": match_format,
        },
    )


@login_required
def club_leaderboard(request, slug):
    club = get_object_or_404(Club, slug=slug)
    if not club.is_public and not club.is_member(request.user):
        raise PermissionDenied("This club's leaderboard is restricted to club members.")

    match_format = request.GET.get("format", "doubles").strip().lower()
    if match_format not in ("doubles", "singles"):
        match_format = "doubles"

    memberships = list(
        ClubMembership.objects.select_related("user", "user__rating_profile")
        .filter(
            club=club,
            status=ClubMembership.Status.ACTIVE,
            user__is_active=True,
            user__is_superuser=False,
        )
    )
    players = [m.user for m in memberships]
    club_roles = {
        m.user_id: m.get_role_display()
        for m in memberships
        if m.role in (ClubMembership.Role.HOST, ClubMembership.Role.CO_HOST)
    }

    rows = _build_leaderboard_rows(
        players,
        request.user,
        club=club,
        match_format=match_format,
        club_roles=club_roles,
    )
    my_clubs = list(
        Club.objects.filter(
            memberships__user=request.user,
            memberships__status=ClubMembership.Status.ACTIVE,
        ).order_by("name")
    )
    return render(
        request,
        "clubs/leaderboard.html",
        {
            "rows": rows,
            "player_count": len(rows),
            "scope": "club",
            "club": club,
            "my_clubs": my_clubs,
            "match_format": match_format,
        },
    )


leaderboard = global_leaderboard
