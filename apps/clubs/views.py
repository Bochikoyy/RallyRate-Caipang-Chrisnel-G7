from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from apps.matches.models import Match, MatchParticipant

from .forms import ClubForm, JoinClubCodeForm
from .models import Club, ClubMembership

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

    active_memberships = list(
        club.memberships.select_related("user")
        .filter(status=ClubMembership.Status.ACTIVE)
        .order_by("role", "user__first_name", "user__last_name", "user__username")
    )
    pending_count = (
        club.memberships.filter(status=ClubMembership.Status.PENDING).count()
        if club.is_manager(request.user)
        else 0
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
            "events": [],
            "club_matches": [],
            "disputed_club_matches": [],
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
    club.delete()
    messages.success(request, f"Deleted club '{name}'.")
    return redirect("clubs:hub")


@login_required
def global_leaderboard(request):
    players = list(
        User.objects.filter(is_active=True, is_superuser=False).order_by(
            "first_name", "last_name", "username"
        )
    )
    verified_participations = (
        MatchParticipant.objects.select_related("match", "player")
        .filter(match__status=Match.Status.VERIFIED)
        .order_by("-match__played_at", "-match__created_at")
    )
    stats_by_user = {u.id: {"wins": 0, "losses": 0, "last_match": None} for u in players}
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
    for idx, u in enumerate(players, start=1):
        s = stats_by_user[u.id]
        rows.append(
            {
                "rank": f"{idx:02d}",
                "user_id": u.id,
                "name": _display_name(u),
                "is_you": u.id == request.user.id,
                "wins": s["wins"],
                "losses": s["losses"],
                "verified_total": s["wins"] + s["losses"],
                "last_match": s["last_match"],
            }
        )
    return render(request, "clubs/leaderboard.html", {"rows": rows, "player_count": len(rows)})


@login_required
def club_leaderboard(request, slug):
    club = get_object_or_404(Club, slug=slug)
    if not club.is_public and not club.is_member(request.user):
        raise PermissionDenied("This club's leaderboard is restricted to club members.")
    players = list(
        User.objects.filter(
            is_active=True,
            is_superuser=False,
            club_memberships__club=club,
            club_memberships__status=ClubMembership.Status.ACTIVE,
        )
        .distinct()
        .order_by("first_name", "last_name", "username")
    )
    rows = [
        {
            "rank": f"{idx:02d}",
            "user_id": u.id,
            "name": _display_name(u),
            "is_you": u.id == request.user.id,
            "wins": 0,
            "losses": 0,
            "verified_total": 0,
            "last_match": None,
        }
        for idx, u in enumerate(players, start=1)
    ]
    return render(request, "clubs/leaderboard.html", {"rows": rows, "player_count": len(rows), "club": club})


leaderboard = global_leaderboard
