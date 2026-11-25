from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.matches.models import Match, MatchParticipant

User = get_user_model()


class AccountAndDashboardTests(TestCase):
    def setUp(self):
        self.password = "StrongPass123!"
        self.player = User.objects.create_user(
            email="player@rallyrate.test",
            password=self.password,
            first_name="Mika",
            last_name="Reyes",
            role=User.Role.PLAYER,
        )
        self.opponent = User.objects.create_user(
            email="opponent@rallyrate.test",
            password=self.password,
            first_name="Jude",
            last_name="Lim",
            role=User.Role.PLAYER,
        )
        self.organizer = User.objects.create_user(
            email="organizer@rallyrate.test",
            password=self.password,
            first_name="Coach",
            last_name="Dana",
            role=User.Role.ORGANIZER,
        )

    def test_signup_creates_account_and_redirects_to_dashboard(self):
        response = self.client.post(
            reverse("accounts:signup"),
            {
                "full_name": "Chrisnel Caipang",
                "email": "NewPlayer@RallyRate.test",
                "password1": "Pickleball99!",
                "password2": "Pickleball99!",
                "role": User.Role.PLAYER,
                "preferred_paddle": "JOOLA Perseus",
                "home_court": "Cebu IT Park",
            },
        )
        self.assertRedirects(response, reverse("accounts:dashboard"), fetch_redirect_response=False)
        created = User.objects.get(email="newplayer@rallyrate.test")
        self.assertEqual(created.first_name, "Chrisnel")
        self.assertEqual(created.last_name, "Caipang")
        self.assertEqual(created.preferred_paddle, "JOOLA Perseus")

    def test_email_login_and_logout(self):
        login_resp = self.client.post(
            reverse("accounts:login"),
            {"username": "PLAYER@rallyrate.test", "password": self.password},
        )
        self.assertRedirects(login_resp, reverse("accounts:dashboard"), fetch_redirect_response=False)

        logout_resp = self.client.post(reverse("accounts:logout"))
        self.assertRedirects(logout_resp, reverse("accounts:login"), fetch_redirect_response=False)

    def test_role_based_dashboard_routing(self):
        self.client.force_login(self.player)
        self.assertRedirects(self.client.get(reverse("accounts:dashboard")), reverse("accounts:player_dashboard"))
        self.assertRedirects(
            self.client.get(reverse("accounts:organizer_dashboard")),
            reverse("accounts:dashboard"),
            fetch_redirect_response=False,
        )

        self.client.force_login(self.organizer)
        self.assertRedirects(self.client.get(reverse("accounts:dashboard")), reverse("accounts:organizer_dashboard"))
        self.assertRedirects(
            self.client.get(reverse("accounts:player_dashboard")),
            reverse("accounts:dashboard"),
            fetch_redirect_response=False,
        )

    def test_profile_update_persists_changes(self):
        self.client.force_login(self.player)
        resp = self.client.post(
            reverse("accounts:profile"),
            {
                "first_name": "Mikaela",
                "last_name": "Reyes",
                "email": "MIKA@RallyRate.test",
                "phone_number": "09171234567",
                "preferred_paddle": "Selkirk Vanguard",
                "home_court": "Metrosports Cebu",
            },
        )
        self.assertRedirects(resp, reverse("accounts:profile"))
        self.player.refresh_from_db()
        self.assertEqual(self.player.first_name, "Mikaela")
        self.assertEqual(self.player.email, "mika@rallyrate.test")
        self.assertEqual(self.player.home_court, "Metrosports Cebu")

    def test_role_dashboards_show_live_match_metrics_and_queues(self):
        # 1. Verified win for player
        verified_win = Match.objects.create(
            submitted_by=self.player,
            match_type=Match.MatchType.SINGLES,
            played_at=timezone.localdate(),
            location="Court 1",
            team_a_score=11,
            team_b_score=6,
            status=Match.Status.VERIFIED,
            verified_by=self.opponent,
            verified_at=timezone.now(),
        )
        MatchParticipant.objects.bulk_create(
            [
                MatchParticipant(match=verified_win, player=self.player, team=MatchParticipant.Team.TEAM_A),
                MatchParticipant(match=verified_win, player=self.opponent, team=MatchParticipant.Team.TEAM_B),
            ]
        )

        # 2. Pending match submitted by opponent -> awaits player's confirmation
        pending_for_player = Match.objects.create(
            submitted_by=self.opponent,
            match_type=Match.MatchType.SINGLES,
            played_at=timezone.localdate(),
            location="Court 2",
            team_a_score=11,
            team_b_score=9,
            status=Match.Status.PENDING,
        )
        MatchParticipant.objects.bulk_create(
            [
                MatchParticipant(match=pending_for_player, player=self.opponent, team=MatchParticipant.Team.TEAM_A),
                MatchParticipant(match=pending_for_player, player=self.player, team=MatchParticipant.Team.TEAM_B),
            ]
        )

        # 3. Disputed match -> should appear first in organizer review queue
        disputed_match = Match.objects.create(
            submitted_by=self.player,
            match_type=Match.MatchType.SINGLES,
            played_at=timezone.localdate(),
            location="Court 3",
            team_a_score=12,
            team_b_score=10,
            status=Match.Status.DISPUTED,
            disputed_by=self.opponent,
            dispute_reason="Score was swapped.",
        )
        MatchParticipant.objects.bulk_create(
            [
                MatchParticipant(match=disputed_match, player=self.player, team=MatchParticipant.Team.TEAM_A),
                MatchParticipant(match=disputed_match, player=self.opponent, team=MatchParticipant.Team.TEAM_B),
            ]
        )

        self.client.force_login(self.player)
        player_resp = self.client.get(reverse("accounts:player_dashboard"))
        self.assertEqual(player_resp.status_code, 200)
        self.assertEqual(player_resp.context["verified_count"], 1)
        self.assertEqual(player_resp.context["wins"], 1)
        self.assertEqual(player_resp.context["losses"], 0)
        self.assertEqual(player_resp.context["awaiting_confirmation_count"], 1)
        self.assertEqual(player_resp.context["awaiting_confirmation"], [pending_for_player])

        self.client.force_login(self.organizer)
        org_resp = self.client.get(reverse("accounts:organizer_dashboard"))
        self.assertEqual(org_resp.status_code, 200)
        self.assertEqual(org_resp.context["total_matches"], 3)
        self.assertEqual(org_resp.context["verified_count"], 1)
        self.assertEqual(org_resp.context["pending_count"], 1)
        self.assertEqual(org_resp.context["disputed_count"], 1)
        self.assertEqual(org_resp.context["review_queue"][0], disputed_match)
