from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.clubs.models import Club, ClubMembership
from apps.ratings.models import RatingHistory

from .forms import MatchForm
from .models import Match, MatchParticipant

User = get_user_model()


class MatchCRUDAndClubHostTests(TestCase):
    def setUp(self):
        self.password = "RallyPass123!"
        self.player_a1 = User.objects.create_user(
            email="player1@example.com",
            password=self.password,
            first_name="Alex",
            last_name="Cruz",
        )
        self.player_a2 = User.objects.create_user(
            email="player2@example.com",
            password=self.password,
            first_name="Bea",
            last_name="Lim",
        )
        self.player_b1 = User.objects.create_user(
            email="player3@example.com",
            password=self.password,
            first_name="Carlo",
            last_name="Tan",
        )
        self.player_b2 = User.objects.create_user(
            email="player4@example.com",
            password=self.password,
            first_name="Dana",
            last_name="Reyes",
        )
        self.outsider = User.objects.create_user(
            email="outsider@example.com",
            password=self.password,
            first_name="Eli",
            last_name="Santos",
        )
        self.host = User.objects.create_user(
            email="host@example.com",
            password=self.password,
            first_name="Coach",
            last_name="Mina",
        )

        self.club = Club.objects.create(
            name="Banilad Smash Club",
            home_court="Banilad Court 1",
            is_public=False,
            created_by=self.host,
        )
        ClubMembership.objects.bulk_create(
            [
                ClubMembership(club=self.club, user=self.host, role=ClubMembership.Role.HOST),
                ClubMembership(club=self.club, user=self.player_a1, role=ClubMembership.Role.MEMBER),
                ClubMembership(club=self.club, user=self.player_b1, role=ClubMembership.Role.MEMBER),
            ]
        )

    def _create_singles_match(self, submitted_by=None, status=Match.Status.PENDING, club=None):
        submitted_by = submitted_by or self.player_a1
        match = Match.objects.create(
            club=club,
            submitted_by=submitted_by,
            match_type=Match.MatchType.SINGLES,
            played_at=timezone.localdate(),
            location="Cebu Court 1",
            team_a_score=11,
            team_b_score=7,
            status=status,
        )
        MatchParticipant.objects.bulk_create(
            [
                MatchParticipant(match=match, player=submitted_by, team=MatchParticipant.Team.TEAM_A),
                MatchParticipant(match=match, player=self.player_b1, team=MatchParticipant.Team.TEAM_B),
            ]
        )
        return match

    def test_player_can_create_singles_and_doubles_peer_matches(self):
        self.client.force_login(self.player_a1)
        resp = self.client.post(
            reverse("matches:create"),
            {
                "club": self.club.pk,
                "match_type": Match.MatchType.DOUBLES,
                "played_at": timezone.localdate().isoformat(),
                "location": "Banilad Court 3",
                "partner": self.player_a2.pk,
                "opponent_1": self.player_b1.pk,
                "opponent_2": self.player_b2.pk,
                "team_a_score": 11,
                "team_b_score": 8,
            },
        )
        self.assertEqual(Match.objects.count(), 1)
        match = Match.objects.first()
        self.assertRedirects(resp, reverse("matches:detail", args=[match.pk]))
        self.assertEqual(match.club, self.club)
        self.assertEqual(match.source, Match.Source.CASUAL_PEER)
        self.assertEqual(match.status, Match.Status.PENDING)
        self.assertEqual(match.participants.count(), 4)

    def test_pickleball_score_and_best_of_three_validations(self):
        base_data = {
            "match_type": Match.MatchType.SINGLES,
            "played_at": timezone.localdate().isoformat(),
            "location": "Court A",
            "opponent_1": self.player_b1.pk,
            "team_a_score": 11,
            "team_b_score": 9,
        }
        self.assertFalse(MatchForm({**base_data, "team_a_score": 11, "team_b_score": 11}, user=self.player_a1).is_valid())
        self.assertFalse(MatchForm({**base_data, "team_a_score": 10, "team_b_score": 7}, user=self.player_a1).is_valid())
        self.assertFalse(MatchForm({**base_data, "team_a_score": 11, "team_b_score": 10}, user=self.player_a1).is_valid())

        tomorrow = (timezone.localdate() + timedelta(days=1)).isoformat()
        self.assertFalse(MatchForm({**base_data, "played_at": tomorrow}, user=self.player_a1).is_valid())

        # 1-1 split requires Game 3
        split = MatchForm({**base_data, "game_2_team_a": 6, "game_2_team_b": 11}, user=self.player_a1)
        self.assertFalse(split.is_valid())
        self.assertIn("game_3_team_a", split.errors)

    def test_opponent_verify_updates_ratings_and_blocks_self_verify(self):
        match = self._create_singles_match(club=self.club)

        # Submitter cannot self-verify
        self.client.force_login(self.player_a1)
        self.client.post(reverse("matches:verify", args=[match.pk]))
        match.refresh_from_db()
        self.assertEqual(match.status, Match.Status.PENDING)

        # Outsider blocked on private club / non-participant match
        self.client.force_login(self.outsider)
        self.assertEqual(self.client.post(reverse("matches:verify", args=[match.pk])).status_code, 403)

        # Opponent confirms -> status VERIFIED and ratings updated
        self.client.force_login(self.player_b1)
        resp = self.client.post(reverse("matches:verify", args=[match.pk]))
        self.assertRedirects(resp, reverse("matches:detail", args=[match.pk]))
        match.refresh_from_db()
        self.assertEqual(match.status, Match.Status.VERIFIED)
        self.assertEqual(RatingHistory.objects.filter(match=match).count(), 2)
        self.player_a1.rating_profile.refresh_from_db()
        self.player_b1.rating_profile.refresh_from_db()
        self.assertGreater(self.player_a1.rating_profile.singles_rating, Decimal("3.000"))
        self.assertLess(self.player_b1.rating_profile.singles_rating, Decimal("3.000"))

    def test_dispute_and_club_host_resolution_and_edit_recalc(self):
        match = self._create_singles_match(club=self.club)

        # Opponent disputes
        self.client.force_login(self.player_b1)
        self.client.post(
            reverse("matches:dispute", args=[match.pk]),
            {"dispute_reason": "Score was actually 7-11 in my favor."},
        )
        match.refresh_from_db()
        self.assertEqual(match.status, Match.Status.DISPUTED)

        # Players cannot verify disputed match directly
        self.client.post(reverse("matches:verify", args=[match.pk]))
        match.refresh_from_db()
        self.assertEqual(match.status, Match.Status.DISPUTED)

        # Club Host edits the score and resolves & verifies the dispute
        self.client.force_login(self.host)
        self.client.post(
            reverse("matches:update", args=[match.pk]),
            {
                "club": self.club.pk,
                "match_type": Match.MatchType.SINGLES,
                "played_at": timezone.localdate().isoformat(),
                "location": "Banilad Court 1",
                "team_a_player_1": self.player_a1.pk,
                "opponent_1": self.player_b1.pk,
                "team_a_score": 7,
                "team_b_score": 11,
            },
        )
        self.client.post(reverse("matches:verify", args=[match.pk]))
        match.refresh_from_db()
        self.assertEqual(match.status, Match.Status.VERIFIED)
        self.player_b1.rating_profile.refresh_from_db()
        self.assertGreater(self.player_b1.rating_profile.singles_rating, Decimal("3.000"))

        # Deleting verified match as Club Host cleanly reverts ratings back to 3.000
        self.client.post(reverse("matches:delete", args=[match.pk]))
        self.player_b1.rating_profile.refresh_from_db()
        self.assertEqual(self.player_b1.rating_profile.singles_rating, Decimal("3.000"))
