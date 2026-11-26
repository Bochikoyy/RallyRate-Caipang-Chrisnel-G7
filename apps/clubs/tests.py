from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.matches.models import Match, MatchParticipant

from .models import Club, ClubEvent, ClubMembership, EventParticipant

User = get_user_model()


class ClubEventAndGeneratorTests(TestCase):
    def setUp(self):
        self.password = "ClubPass123!"
        self.host = User.objects.create_user(
            email="host@clubs.test",
            password=self.password,
            first_name="Chrisnel",
            last_name="Host",
        )
        self.cohost = User.objects.create_user(
            email="cohost@clubs.test",
            password=self.password,
            first_name="Ben",
            last_name="CoHost",
        )
        self.p3 = User.objects.create_user(
            email="p3@clubs.test",
            password=self.password,
            first_name="Cara",
            last_name="Three",
        )
        self.p4 = User.objects.create_user(
            email="p4@clubs.test",
            password=self.password,
            first_name="Dan",
            last_name="Four",
        )
        self.p5 = User.objects.create_user(
            email="p5@clubs.test",
            password=self.password,
            first_name="Eva",
            last_name="Five",
        )

    def test_create_club_join_by_code_and_cohost_permissions(self):
        self.client.force_login(self.host)
        resp = self.client.post(
            reverse("clubs:create"),
            {
                "name": "IT Park Smashers",
                "home_court": "Cebu IT Park Courts",
                "description": "Nightly open play",
                "is_public": False,
            },
        )
        club = Club.objects.get(name="IT Park Smashers")
        self.assertRedirects(resp, reverse("clubs:detail", args=[club.slug]))
        self.assertTrue(club.is_host(self.host))

        # Invite-only club blocks non-members until they use join_code
        self.client.force_login(self.cohost)
        self.assertEqual(self.client.get(reverse("clubs:detail", args=[club.slug])).status_code, 403)

        join_resp = self.client.post(
            reverse("clubs:join_by_code"),
            {"join_code": club.join_code.lower()},
        )
        self.assertRedirects(join_resp, reverse("clubs:detail", args=[club.slug]))
        self.assertTrue(club.is_member(self.cohost))

        # Host promotes Ben to Co-host
        self.client.force_login(self.host)
        ben_mem = club.active_membership_for(self.cohost)
        self.client.post(
            reverse("clubs:update_member_role", args=[club.slug, ben_mem.pk]),
            {"role": ClubMembership.Role.CO_HOST},
        )
        ben_mem.refresh_from_db()
        self.assertEqual(ben_mem.role, ClubMembership.Role.CO_HOST)
        self.assertTrue(club.is_manager(self.cohost))

        # Co-host can access manage page, but CANNOT delete club or change roles
        self.client.force_login(self.cohost)
        self.assertEqual(self.client.get(reverse("clubs:manage", args=[club.slug])).status_code, 200)
        self.assertEqual(self.client.post(reverse("clubs:delete", args=[club.slug])).status_code, 403)

    def test_event_waitlist_balanced_generator_and_host_scoring(self):
        club = Club.objects.create(
            name="Metro Dinkers",
            home_court="Metrosports",
            is_public=True,
            created_by=self.host,
        )
        ClubMembership.objects.create(club=club, user=self.host, role=ClubMembership.Role.HOST)

        # Seed distinct doubles ratings to verify (#1 + #4) vs (#2 + #3) balanced pairing
        for user, rating in [
            (self.host, Decimal("4.200")),
            (self.cohost, Decimal("3.900")),
            (self.p3, Decimal("3.500")),
            (self.p4, Decimal("3.100")),
        ]:
            prof = user.rating_profile
            prof.doubles_rating = rating
            prof.save()

        self.client.force_login(self.host)
        now_str = timezone.localtime().strftime("%Y-%m-%dT%H:%M")
        self.client.post(
            reverse("clubs:event_create", args=[club.slug]),
            {
                "title": "Friday Doubles Night",
                "location": "Court 1",
                "starts_at": now_str,
                "format": ClubEvent.Format.DOUBLES,
                "matchmaking_mode": ClubEvent.MatchmakingMode.BALANCED,
                "courts_count": 1,
                "max_players": 4,
                "notes": "Games to 11",
            },
        )
        event = ClubEvent.objects.get(title="Friday Doubles Night")

        # 3 more join -> reaches cap of 4; 5th player lands on WAITLIST
        for u in (self.cohost, self.p3, self.p4, self.p5):
            self.client.force_login(u)
            self.client.post(reverse("clubs:event_join", args=[club.slug, event.pk]))

        self.assertEqual(
            EventParticipant.objects.get(event=event, user=self.p5).status,
            EventParticipant.Status.WAITLIST,
        )

        # Host clicks Generate Next Round -> pairs (#1 host + #4 p4) vs (#2 cohost + #3 p3)
        self.client.force_login(self.host)
        self.client.post(reverse("clubs:event_generate_matches", args=[club.slug, event.pk]))
        self.assertEqual(event.matches.count(), 1)
        gen_match = event.matches.first()
        self.assertEqual(gen_match.status, Match.Status.SCHEDULED)
        self.assertEqual(gen_match.source, Match.Source.CLUB_EVENT)

        team_a_ids = {p.player_id for p in gen_match.team_a_participants}
        team_b_ids = {p.player_id for p in gen_match.team_b_participants}
        self.assertEqual(team_a_ids, {self.host.id, self.p4.id})
        self.assertEqual(team_b_ids, {self.cohost.id, self.p3.id})

        # Host manually inputs the score -> immediately VERIFIED & ratings updated!
        score_resp = self.client.post(
            reverse("clubs:event_record_score", args=[club.slug, event.pk, gen_match.pk]),
            {"team_a_score": 11, "team_b_score": 4},
        )
        self.assertRedirects(score_resp, reverse("clubs:event_detail", args=[club.slug, event.pk]))
        gen_match.refresh_from_db()
        self.assertEqual(gen_match.status, Match.Status.VERIFIED)
        self.host.rating_profile.refresh_from_db()
        self.assertGreater(self.host.rating_profile.doubles_rating, Decimal("4.200"))

        # Dual leaderboards: Club Leaderboard shows club members; Local shows all 5 players
        club_lb = self.client.get(reverse("clubs:club_leaderboard", args=[club.slug]))
        self.assertEqual(club_lb.status_code, 200)
        self.assertEqual(club_lb.context["scope"], "club")
        self.assertEqual(club_lb.context["player_count"], 5)

        local_lb = self.client.get(reverse("global_leaderboard"))
        self.assertEqual(local_lb.status_code, 200)
        self.assertEqual(local_lb.context["scope"], "local")
        self.assertEqual(local_lb.context["rows"][0]["user_id"], self.host.id)
