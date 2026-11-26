from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.clubs.models import Club, ClubMembership
from apps.matches.models import Match, MatchParticipant
from apps.ratings.engine import process_verified_match

User = get_user_model()


class AccountAndDashboardTests(TestCase):
    def setUp(self):
        self.password = "StrongPass123!"
        self.player = User.objects.create_user(
            email="player@rallyrate.test",
            password=self.password,
            first_name="Mika",
            last_name="Reyes",
        )
        self.opponent = User.objects.create_user(
            email="opponent@rallyrate.test",
            password=self.password,
            first_name="Jude",
            last_name="Lim",
        )

    def test_signup_creates_player_account_with_3_000_profile(self):
        response = self.client.post(
            reverse("accounts:signup"),
            {
                "full_name": "Chrisnel Caipang",
                "email": "NewPlayer@RallyRate.test",
                "password1": "Pickleball99!",
                "password2": "Pickleball99!",
                "preferred_paddle": "JOOLA Perseus",
                "home_court": "Cebu IT Park",
            },
        )
        self.assertRedirects(response, reverse("accounts:dashboard"), fetch_redirect_response=False)
        created = User.objects.get(email="newplayer@rallyrate.test")
        self.assertEqual(created.first_name, "Chrisnel")
        self.assertEqual(created.last_name, "Caipang")
        self.assertEqual(created.role, User.Role.PLAYER)
        self.assertEqual(created.preferred_paddle, "JOOLA Perseus")
        self.assertEqual(created.rating_profile.doubles_rating, Decimal("3.000"))
        self.assertEqual(created.rating_profile.singles_rating, Decimal("3.000"))

    def test_email_login_and_logout(self):
        login_resp = self.client.post(
            reverse("accounts:login"),
            {"username": "PLAYER@rallyrate.test", "password": self.password},
        )
        self.assertRedirects(login_resp, reverse("accounts:dashboard"), fetch_redirect_response=False)

        logout_resp = self.client.post(reverse("accounts:logout"))
        self.assertRedirects(logout_resp, reverse("accounts:login"), fetch_redirect_response=False)

    def test_unified_dashboard_and_legacy_redirects(self):
        self.client.force_login(self.player)
        dash = self.client.get(reverse("accounts:dashboard"))
        self.assertEqual(dash.status_code, 200)
        self.assertContains(dash, "3.000")

        self.assertRedirects(
            self.client.get(reverse("accounts:player_dashboard")),
            reverse("accounts:dashboard"),
        )
        self.assertRedirects(
            self.client.get(reverse("accounts:organizer_dashboard")),
            reverse("clubs:hub"),
        )

    def test_profile_update_and_club_memberships_display(self):
        club = Club.objects.create(
            name="Cebu Smashers",
            home_court="Metrosports",
            created_by=self.player,
        )
        ClubMembership.objects.create(
            club=club,
            user=self.player,
            role=ClubMembership.Role.HOST,
            status=ClubMembership.Status.ACTIVE,
        )

        self.client.force_login(self.player)
        resp = self.client.post(
            reverse("accounts:profile"),
            {
                "full_name": "Mikaela Reyes",
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

        prof_page = self.client.get(reverse("accounts:profile"))
        self.assertContains(prof_page, "Cebu Smashers")
        self.assertContains(prof_page, "Host")

    def test_dashboard_live_metrics_and_rating_deltas(self):
        verified_win = Match.objects.create(
            submitted_by=self.player,
            match_type=Match.MatchType.SINGLES,
            played_at=timezone.localdate(),
            location="Court 1",
            team_a_score=11,
            team_b_score=5,
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
        process_verified_match(verified_win)

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

        self.client.force_login(self.player)
        resp = self.client.get(reverse("accounts:dashboard"))
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.context["verified_count"], 1)
        self.assertEqual(resp.context["wins"], 1)
        self.assertEqual(resp.context["losses"], 0)
        self.assertEqual(resp.context["awaiting_confirmation_count"], 1)
        self.assertGreater(Decimal(resp.context["singles_rating"]), Decimal("3.000"))

    def test_duplicate_and_blank_email_validations(self):
        dup_resp = self.client.post(
            reverse("accounts:signup"),
            {
                "full_name": "Duplicate User",
                "email": "PLAYER@RALLYRATE.TEST",
                "password1": "Pickleball99!",
                "password2": "Pickleball99!",
            },
        )
        self.assertEqual(dup_resp.status_code, 200)
        self.assertContains(dup_resp, "already exists")

        self.client.force_login(self.player)
        bad_blank = self.client.post(
            reverse("accounts:profile"),
            {
                "full_name": "   ",
                "email": "",
                "phone_number": "",
                "preferred_paddle": "",
                "home_court": "",
            },
        )
        self.assertEqual(bad_blank.status_code, 200)
        self.assertIn("full_name", bad_blank.context["form"].errors)
        self.assertIn("email", bad_blank.context["form"].errors)

    def test_mobile_floating_dock_avatar_and_toast_markup(self):
        # Sign-in validation failure renders floating toast popup
        bad_login = self.client.post(reverse("accounts:login"), {"username": "", "password": ""})
        self.assertEqual(bad_login.status_code, 200)
        self.assertContains(bad_login, 'id="signin-toast"')

        # Workspace pages render floating bottom dock (including Clubs & Ranks), initials avatar, and segmented switcher
        self.client.force_login(self.player)
        overview_resp = self.client.get(reverse("accounts:dashboard"))
        self.assertContains(overview_resp, 'class="ws-float-dock"')
        self.assertContains(overview_resp, 'class="ws-user-avatar"')
        self.assertContains(overview_resp, "MR")
        self.assertContains(overview_resp, "Clubs")

        ranks_resp = self.client.get(reverse("clubs:leaderboard"))
        self.assertContains(ranks_resp, 'class="ws-mobile-segmented"')
        self.assertContains(ranks_resp, "Ranks")
