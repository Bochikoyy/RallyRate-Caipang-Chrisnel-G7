from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.matches.models import Match, MatchParticipant

from .engine import process_verified_match, recalculate_all_ratings
from .models import PlayerRatingProfile, RatingHistory

User = get_user_model()


class PerformanceRatingEngineTests(TestCase):
    def setUp(self):
        self.p1 = User.objects.create_user(email="r1@test.com", password="pw", first_name="A")
        self.p2 = User.objects.create_user(email="r2@test.com", password="pw", first_name="B")
        self.p3 = User.objects.create_user(email="r3@test.com", password="pw", first_name="C")
        self.p4 = User.objects.create_user(email="r4@test.com", password="pw", first_name="D")

    def _make_singles(self, a, b, score_a, score_b, source=Match.Source.CLUB_EVENT):
        m = Match.objects.create(
            submitted_by=a,
            match_type=Match.MatchType.SINGLES,
            source=source,
            played_at=timezone.localdate(),
            location="Court 1",
            team_a_score=score_a,
            team_b_score=score_b,
            status=Match.Status.VERIFIED,
            verified_by=b,
            verified_at=timezone.now(),
        )
        MatchParticipant.objects.bulk_create(
            [
                MatchParticipant(match=m, player=a, team=MatchParticipant.Team.TEAM_A),
                MatchParticipant(match=m, player=b, team=MatchParticipant.Team.TEAM_B),
            ]
        )
        return m

    def test_margin_of_victory_scales_rating_gain(self):
        # Match 1: p1 beats p2 narrowly 11-9
        m_close = self._make_singles(self.p1, self.p2, 11, 9)
        process_verified_match(m_close)
        close_delta = RatingHistory.objects.get(match=m_close, user=self.p1).delta

        # Match 2: p3 beats p4 decisively 11-2 (both also starting at 3.000)
        m_blowout = self._make_singles(self.p3, self.p4, 11, 2)
        process_verified_match(m_blowout)
        blowout_delta = RatingHistory.objects.get(match=m_blowout, user=self.p3).delta

        self.assertGreater(close_delta, Decimal("0.000"))
        self.assertGreater(blowout_delta, close_delta)

    def test_0_500_mismatch_protection_and_upset_reward(self):
        # Set p1 = 3.700, p2 = 3.000 (gap = 0.700 >= 0.500)
        self.p1.rating_profile.singles_rating = Decimal("3.700")
        self.p1.rating_profile.save()

        # Favorite p1 wins 11-9 -> mismatch protection keeps both ratings unchanged!
        fav_win = self._make_singles(self.p1, self.p2, 11, 9)
        process_verified_match(fav_win)
        entry_fav = RatingHistory.objects.get(match=fav_win, user=self.p1)
        self.assertTrue(entry_fav.mismatch_protected)
        self.assertEqual(entry_fav.delta, Decimal("0.000"))
        self.p1.rating_profile.refresh_from_db()
        self.p2.rating_profile.refresh_from_db()
        self.assertEqual(self.p1.rating_profile.singles_rating, Decimal("3.700"))
        self.assertEqual(self.p2.rating_profile.singles_rating, Decimal("3.000"))

        # Now underdog p2 upsets p1 11-8 -> NOT protected; p2 gets big boost!
        upset = self._make_singles(self.p1, self.p2, 8, 11)
        process_verified_match(upset)
        entry_upset = RatingHistory.objects.get(match=upset, user=self.p2)
        self.assertFalse(entry_upset.mismatch_protected)
        self.assertGreater(entry_upset.delta, Decimal("0.100"))

    def test_club_event_weights_higher_than_casual_peer(self):
        m_club = self._make_singles(self.p1, self.p2, 11, 6, source=Match.Source.CLUB_EVENT)
        process_verified_match(m_club)
        club_entry = RatingHistory.objects.get(match=m_club, user=self.p1)

        m_peer = self._make_singles(self.p3, self.p4, 11, 6, source=Match.Source.CASUAL_PEER)
        process_verified_match(m_peer)
        peer_entry = RatingHistory.objects.get(match=m_peer, user=self.p3)

        self.assertGreater(club_entry.delta, peer_entry.delta)
        self.assertGreater(club_entry.reliability_after, peer_entry.reliability_after)

    def test_recalculate_all_ratings_zero_drift_and_history_views(self):
        m1 = self._make_singles(self.p1, self.p2, 11, 5)
        process_verified_match(m1)
        r_after_win = PlayerRatingProfile.objects.get(user=self.p1).singles_rating
        self.assertGreater(r_after_win, Decimal("3.000"))

        # Flip score so p2 won instead and recalculate
        m1.team_a_score = 5
        m1.team_b_score = 11
        m1.save()
        recalculate_all_ratings()

        p1_prof = PlayerRatingProfile.objects.get(user=self.p1)
        p2_prof = PlayerRatingProfile.objects.get(user=self.p2)
        self.assertLess(p1_prof.singles_rating, Decimal("3.000"))
        self.assertGreater(p2_prof.singles_rating, Decimal("3.000"))

        # Verify rating history & rules pages render cleanly
        self.client.force_login(self.p2)
        hist_resp = self.client.get(reverse("ratings:history") + "?format=singles")
        self.assertEqual(hist_resp.status_code, 200)
        self.assertContains(hist_resp, str(p2_prof.singles_rating))

        rules_resp = self.client.get(reverse("ratings:rules"))
        self.assertEqual(rules_resp.status_code, 200)
        self.assertContains(rules_resp, "0.500 mismatch protection")
