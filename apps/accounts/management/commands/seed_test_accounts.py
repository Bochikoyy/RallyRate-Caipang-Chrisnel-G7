from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.utils import timezone

from apps.accounts.models import Notification
from apps.accounts.notifications import notify_users
from apps.clubs.models import Club, ClubEvent, ClubMembership, EventParticipant
from apps.matches.models import Match, MatchParticipant
from apps.ratings.engine import process_verified_match

User = get_user_model()


class Command(BaseCommand):
    help = "Creates or updates safe PD2 evaluation test accounts and sample club/match records."

    TEST_PASSWORD = "RallyTest123!"

    def handle(self, *args, **options):
        specs = [
            ("host.test@rallyrate.app", "host_demo", "Marco", "Villanueva", "Selkirk Vanguard", "Metrosports Cebu"),
            ("cohost.test@rallyrate.app", "cohost_demo", "Sofia", "Mendoza", "Joola Perseus", "Metrosports Cebu"),
            ("member.test@rallyrate.app", "member_demo", "Liam", "Navarro", "CRBN 1X Power", "Metrosports Cebu"),
            ("opponent.test@rallyrate.app", "opponent_demo", "Chloe", "Bautista", "Six Zero Double Black", "Banilad Courts"),
        ]

        users = {}
        for email, username, first_name, last_name, paddle, court in specs:
            user = User.objects.filter(email__iexact=email).first() or User.objects.filter(username=username).first()
            if user is None:
                user = User.objects.create_user(
                    email=email,
                    username=username,
                    password=self.TEST_PASSWORD,
                    first_name=first_name,
                    last_name=last_name,
                    preferred_paddle=paddle,
                    home_court=court,
                )
            else:
                user.email = email
                user.first_name = first_name
                user.last_name = last_name
                user.preferred_paddle = paddle
                user.home_court = court
                user.is_active = True
                user.set_password(self.TEST_PASSWORD)
                user.save()
            users[username] = user

        host = users["host_demo"]
        cohost = users["cohost_demo"]
        member = users["member_demo"]
        opponent = users["opponent_demo"]

        club, _ = Club.objects.update_or_create(
            slug="cebu-pickleball-test-club",
            defaults={
                "name": "Cebu Pickleball Test Club",
                "home_court": "Metrosports Cebu",
                "description": "Official PD2 evaluation club for testing Host, Co-host, and Member workflows.",
                "is_public": True,
                "join_code": "RR-PD2TST",
                "created_by": host,
            },
        )

        role_map = [
            (host, ClubMembership.Role.HOST),
            (cohost, ClubMembership.Role.CO_HOST),
            (member, ClubMembership.Role.MEMBER),
            (opponent, ClubMembership.Role.MEMBER),
        ]
        for usr, role in role_map:
            ClubMembership.objects.update_or_create(
                club=club,
                user=usr,
                defaults={"role": role, "status": ClubMembership.Status.ACTIVE},
            )

        session, _ = ClubEvent.objects.get_or_create(
            club=club,
            title="Friday Evening Open Play",
            defaults={
                "location": "Metrosports Cebu · Courts 1–2",
                "starts_at": timezone.now() + timedelta(days=1),
                "format": ClubEvent.Format.DOUBLES,
                "matchmaking_mode": ClubEvent.MatchmakingMode.BALANCED,
                "courts_count": 2,
                "max_players": 16,
                "status": ClubEvent.Status.OPEN,
                "created_by": host,
            },
        )
        for usr in (host, cohost, member, opponent):
            EventParticipant.objects.get_or_create(
                event=session,
                user=usr,
                defaults={"status": EventParticipant.Status.JOINED},
            )

        # Ensure one verified club session match exists for leaderboard & rating history inspection
        if not Match.objects.filter(club=club, source=Match.Source.CLUB_EVENT, status=Match.Status.VERIFIED).exists():
            verified_match = Match.objects.create(
                club=club,
                event=session,
                source=Match.Source.CLUB_EVENT,
                round_number=1,
                court_number=1,
                submitted_by=host,
                verified_by=host,
                verified_at=timezone.now(),
                match_type=Match.MatchType.DOUBLES,
                played_at=timezone.localdate(),
                location="Metrosports Cebu · Court 1",
                team_a_score=11,
                team_b_score=7,
                status=Match.Status.VERIFIED,
            )
            MatchParticipant.objects.bulk_create(
                [
                    MatchParticipant(match=verified_match, player=host, team=MatchParticipant.Team.TEAM_A),
                    MatchParticipant(match=verified_match, player=cohost, team=MatchParticipant.Team.TEAM_A),
                    MatchParticipant(match=verified_match, player=member, team=MatchParticipant.Team.TEAM_B),
                    MatchParticipant(match=verified_match, player=opponent, team=MatchParticipant.Team.TEAM_B),
                ]
            )
            process_verified_match(verified_match)

        # Ensure one pending peer match exists between member_demo and opponent_demo for instant verification testing
        if not Match.objects.filter(
            submitted_by=member,
            source=Match.Source.CASUAL_PEER,
            status=Match.Status.PENDING,
        ).exists():
            pending_match = Match.objects.create(
                club=None,
                source=Match.Source.CASUAL_PEER,
                submitted_by=member,
                match_type=Match.MatchType.SINGLES,
                played_at=timezone.localdate(),
                location="Banilad Courts · Court 2",
                team_a_score=11,
                team_b_score=8,
                status=Match.Status.PENDING,
                notes="Sample pending peer match ready for opponent confirmation or score counter-edit.",
            )
            MatchParticipant.objects.bulk_create(
                [
                    MatchParticipant(match=pending_match, player=member, team=MatchParticipant.Team.TEAM_A),
                    MatchParticipant(match=pending_match, player=opponent, team=MatchParticipant.Team.TEAM_B),
                ]
            )
            notify_users(
                [opponent],
                category=Notification.Category.MATCH_REVIEW,
                title=f"Liam Navarro submitted a singles match ({pending_match.score_display})",
                body="Review and confirm the final score so ratings can update.",
                target_url=f"/matches/{pending_match.pk}/",
                actor=member,
            )

        self.stdout.write(self.style.SUCCESS("Seeded PD2 test accounts and sample club/match data."))
