from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from .forms import MatchForm
from .models import Match, MatchParticipant

User = get_user_model()


class MatchCRUDTests(TestCase):
    def setUp(self):
        self.password = "RallyPass123!"
        self.player_a1 = User.objects.create_user(
            email="player1@example.com",
            password=self.password,
            first_name="Alex",
            last_name="Cruz",
            role=User.Role.PLAYER,
        )
        self.player_a2 = User.objects.create_user(
            email="player2@example.com",
            password=self.password,
            first_name="Bea",
            last_name="Lim",
            role=User.Role.PLAYER,
        )
        self.player_b1 = User.objects.create_user(
            email="player3@example.com",
            password=self.password,
            first_name="Carlo",
            last_name="Tan",
            role=User.Role.PLAYER,
        )
        self.player_b2 = User.objects.create_user(
            email="player4@example.com",
            password=self.password,
            first_name="Dana",
            last_name="Reyes",
            role=User.Role.PLAYER,
        )
        self.outsider = User.objects.create_user(
            email="outsider@example.com",
            password=self.password,
            first_name="Eli",
            last_name="Santos",
            role=User.Role.PLAYER,
        )
        self.organizer = User.objects.create_user(
            email="organizer@example.com",
            password=self.password,
            first_name="Coach",
            last_name="Mina",
            role=User.Role.ORGANIZER,
        )

    def _create_singles_match(self, submitted_by=None, status=Match.Status.PENDING):
        submitted_by = submitted_by or self.player_a1
        match = Match.objects.create(
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

    def test_anonymous_user_is_redirected_to_login(self):
        match = self._create_singles_match()
        for url in [
            reverse("matches:list"),
            reverse("matches:create"),
            reverse("matches:detail", args=[match.pk]),
            reverse("matches:update", args=[match.pk]),
            reverse("matches:delete", args=[match.pk]),
        ]:
            response = self.client.get(url)
            self.assertEqual(response.status_code, 302)
            self.assertIn(reverse("accounts:login"), response.url)

    def test_player_can_create_singles_match(self):
        self.client.force_login(self.player_a1)
        response = self.client.post(
            reverse("matches:create"),
            {
                "match_type": Match.MatchType.SINGLES,
                "played_at": timezone.localdate().isoformat(),
                "location": "IT Park Pickleball Court",
                "opponent_1": self.player_b1.pk,
                "team_a_score": 11,
                "team_b_score": 8,
                "notes": "Great rallies",
            },
        )
        self.assertEqual(Match.objects.count(), 1)
        match = Match.objects.first()
        self.assertRedirects(response, reverse("matches:detail", args=[match.pk]))
        self.assertEqual(match.submitted_by, self.player_a1)
        self.assertEqual(match.status, Match.Status.PENDING)
        self.assertEqual(match.participants.count(), 2)
        self.assertEqual(match.winner_team, MatchParticipant.Team.TEAM_A)

    def test_player_can_create_doubles_match(self):
        self.client.force_login(self.player_a1)
        response = self.client.post(
            reverse("matches:create"),
            {
                "match_type": Match.MatchType.DOUBLES,
                "played_at": timezone.localdate().isoformat(),
                "location": "Banilad Club Court 3",
                "partner": self.player_a2.pk,
                "opponent_1": self.player_b1.pk,
                "opponent_2": self.player_b2.pk,
                "team_a_score": 13,
                "team_b_score": 11,
            },
        )
        self.assertEqual(Match.objects.count(), 1)
        match = Match.objects.first()
        self.assertRedirects(response, reverse("matches:detail", args=[match.pk]))
        self.assertEqual(match.participants.filter(team=MatchParticipant.Team.TEAM_A).count(), 2)
        self.assertEqual(match.participants.filter(team=MatchParticipant.Team.TEAM_B).count(), 2)

    def test_form_validation_rules(self):
        base_data = {
            "match_type": Match.MatchType.SINGLES,
            "played_at": timezone.localdate().isoformat(),
            "location": "Court A",
            "opponent_1": self.player_b1.pk,
            "team_a_score": 11,
            "team_b_score": 9,
        }

        # Tied score
        form = MatchForm({**base_data, "team_a_score": 11, "team_b_score": 11}, user=self.player_a1)
        self.assertFalse(form.is_valid())
        self.assertIn("team_b_score", form.errors)

        # Winning score < 11
        form = MatchForm({**base_data, "team_a_score": 10, "team_b_score": 7}, user=self.player_a1)
        self.assertFalse(form.is_valid())
        self.assertIn("team_a_score", form.errors)

        # Margin < 2
        form = MatchForm({**base_data, "team_a_score": 11, "team_b_score": 10}, user=self.player_a1)
        self.assertFalse(form.is_valid())
        self.assertIn("team_b_score", form.errors)

        # Future date
        tomorrow = (timezone.localdate() + timedelta(days=1)).isoformat()
        form = MatchForm({**base_data, "played_at": tomorrow}, user=self.player_a1)
        self.assertFalse(form.is_valid())
        self.assertIn("played_at", form.errors)

        # Doubles missing partner and opponent_2
        form = MatchForm({**base_data, "match_type": Match.MatchType.DOUBLES}, user=self.player_a1)
        self.assertFalse(form.is_valid())
        self.assertIn("partner", form.errors)
        self.assertIn("opponent_2", form.errors)

        # Duplicate players across teams
        form = MatchForm(
            {
                **base_data,
                "match_type": Match.MatchType.DOUBLES,
                "partner": self.player_b1.pk,
                "opponent_1": self.player_b1.pk,
                "opponent_2": self.player_b2.pk,
            },
            user=self.player_a1,
        )
        self.assertFalse(form.is_valid())
        self.assertTrue(form.non_field_errors())

    def test_visibility_and_status_filtering(self):
        pending_match = self._create_singles_match(status=Match.Status.PENDING)
        verified_match = self._create_singles_match(status=Match.Status.VERIFIED)

        # Outsider cannot see matches they are not part of
        self.client.force_login(self.outsider)
        list_resp = self.client.get(reverse("matches:list"))
        self.assertEqual(list_resp.status_code, 200)
        self.assertEqual(list(list_resp.context["matches"]), [])
        self.assertEqual(self.client.get(reverse("matches:detail", args=[pending_match.pk])).status_code, 403)

        # Opponent can see matches they participated in, and status filter works
        self.client.force_login(self.player_b1)
        filtered = self.client.get(reverse("matches:list") + "?status=verified")
        self.assertEqual(list(filtered.context["matches"]), [verified_match])

        # Organizer sees all matches
        self.client.force_login(self.organizer)
        org_list = self.client.get(reverse("matches:list"))
        self.assertEqual(org_list.context["matches"].count(), 2)
        self.assertEqual(self.client.get(reverse("matches:detail", args=[pending_match.pk])).status_code, 200)

    def test_submitter_can_edit_and_delete_pending_match(self):
        match = self._create_singles_match(status=Match.Status.PENDING)
        self.client.force_login(self.player_a1)

        update_resp = self.client.post(
            reverse("matches:update", args=[match.pk]),
            {
                "match_type": Match.MatchType.SINGLES,
                "played_at": timezone.localdate().isoformat(),
                "location": "Updated Court 5",
                "opponent_1": self.player_b2.pk,
                "team_a_score": 15,
                "team_b_score": 12,
                "notes": "Updated score",
            },
        )
        self.assertRedirects(update_resp, reverse("matches:detail", args=[match.pk]))
        match.refresh_from_db()
        self.assertEqual(match.location, "Updated Court 5")
        self.assertEqual(match.team_a_score, 15)
        self.assertTrue(match.participants.filter(player=self.player_b2, team=MatchParticipant.Team.TEAM_B).exists())

        delete_resp = self.client.post(reverse("matches:delete", args=[match.pk]))
        self.assertRedirects(delete_resp, reverse("matches:list"))
        self.assertFalse(Match.objects.filter(pk=match.pk).exists())

    def test_verified_match_locked_for_player_but_editable_by_organizer(self):
        match = self._create_singles_match(status=Match.Status.VERIFIED)

        # Submitter cannot edit or delete verified match
        self.client.force_login(self.player_a1)
        edit_resp = self.client.get(reverse("matches:update", args=[match.pk]))
        self.assertRedirects(edit_resp, reverse("matches:detail", args=[match.pk]))
        del_resp = self.client.post(reverse("matches:delete", args=[match.pk]))
        self.assertRedirects(del_resp, reverse("matches:detail", args=[match.pk]))
        self.assertTrue(Match.objects.filter(pk=match.pk).exists())

        # Opponent gets 403 trying to edit or delete
        self.client.force_login(self.player_b1)
        self.assertEqual(self.client.get(reverse("matches:update", args=[match.pk])).status_code, 403)
        self.assertEqual(self.client.post(reverse("matches:delete", args=[match.pk])).status_code, 403)

        # Organizer can edit and delete
        self.client.force_login(self.organizer)
        org_edit = self.client.post(
            reverse("matches:update", args=[match.pk]),
            {
                "match_type": Match.MatchType.SINGLES,
                "played_at": timezone.localdate().isoformat(),
                "location": "Organizer Corrected Court",
                "team_a_player_1": self.player_a1.pk,
                "opponent_1": self.player_b1.pk,
                "team_a_score": 11,
                "team_b_score": 9,
            },
        )
        self.assertRedirects(org_edit, reverse("matches:detail", args=[match.pk]))
        match.refresh_from_db()
        self.assertEqual(match.location, "Organizer Corrected Court")

        org_del = self.client.post(reverse("matches:delete", args=[match.pk]))
        self.assertRedirects(org_del, reverse("matches:list"))
        self.assertFalse(Match.objects.filter(pk=match.pk).exists())
