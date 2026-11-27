from django import forms
from django.contrib.auth import get_user_model
from django.db import transaction
from django.utils import timezone

from .models import Match, MatchParticipant

User = get_user_model()


class PlayerChoiceField(forms.ModelChoiceField):
    def label_from_instance(self, obj):
        full_name = f"{obj.first_name} {obj.last_name}".strip()
        identifier = obj.email or obj.username
        if full_name:
            return f"{full_name} ({identifier})"
        return identifier


class MatchForm(forms.ModelForm):
    team_a_player_1 = PlayerChoiceField(
        queryset=User.objects.none(),
        label="Player 1",
        required=False,
    )
    partner = PlayerChoiceField(
        queryset=User.objects.none(),
        label="Partner",
        required=False,
    )
    opponent_1 = PlayerChoiceField(
        queryset=User.objects.none(),
        label="Opponent 1",
        required=True,
    )
    opponent_2 = PlayerChoiceField(
        queryset=User.objects.none(),
        label="Opponent 2",
        required=False,
    )

    class Meta:
        model = Match
        fields = (
            "match_type",
            "played_at",
            "location",
            "team_a_score",
            "team_b_score",
            "game_2_team_a",
            "game_2_team_b",
            "game_3_team_a",
            "game_3_team_b",
            "notes",
        )
        widgets = {
            "played_at": forms.DateInput(attrs={"type": "date"}),
            "location": forms.TextInput(attrs={"placeholder": "Riverside · Court 3"}),
            "team_a_score": forms.NumberInput(attrs={"min": 0, "max": 99, "placeholder": "11"}),
            "team_b_score": forms.NumberInput(attrs={"min": 0, "max": 99, "placeholder": "9"}),
            "game_2_team_a": forms.NumberInput(attrs={"min": 0, "max": 99, "placeholder": "—"}),
            "game_2_team_b": forms.NumberInput(attrs={"min": 0, "max": 99, "placeholder": "—"}),
            "game_3_team_a": forms.NumberInput(attrs={"min": 0, "max": 99, "placeholder": "—"}),
            "game_3_team_b": forms.NumberInput(attrs={"min": 0, "max": 99, "placeholder": "—"}),
            "notes": forms.Textarea(attrs={"rows": 2, "placeholder": "Optional match notes"}),
        }
        labels = {
            "match_type": "Match format",
            "played_at": "Date played",
            "location": "Court",
            "team_a_score": "Game 1 — Your team",
            "team_b_score": "Game 1 — Opponents",
            "game_2_team_a": "Game 2 — Your team",
            "game_2_team_b": "Game 2 — Opponents",
            "game_3_team_a": "Game 3 — Your team",
            "game_3_team_b": "Game 3 — Opponents",
            "notes": "Notes (optional)",
        }

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.user = user
        self.fields["team_a_score"].required = True
        self.fields["team_b_score"].required = True

        self.can_pick_lead = bool(
            self.instance
            and self.instance.pk
            and self.instance.is_club_manager(user)
        )

        active_users = User.objects.filter(is_active=True).order_by("first_name", "last_name", "username")

        if not self.instance.pk and not self.is_bound:
            self.fields["match_type"].initial = Match.MatchType.DOUBLES

        if self.can_pick_lead:
            self.fields["team_a_player_1"].queryset = active_users
            self.fields["partner"].queryset = active_users
            self.fields["opponent_1"].queryset = active_users
            self.fields["opponent_2"].queryset = active_users
        else:
            self.fields.pop("team_a_player_1", None)
            other_users = active_users.exclude(pk=user.pk) if user else active_users
            self.fields["partner"].queryset = other_users
            self.fields["opponent_1"].queryset = other_users
            self.fields["opponent_2"].queryset = other_users

        if self.instance and self.instance.pk:
            team_a = list(
                self.instance.participants.filter(team=MatchParticipant.Team.TEAM_A)
                .select_related("player")
                .order_by("id")
            )
            team_b = list(
                self.instance.participants.filter(team=MatchParticipant.Team.TEAM_B)
                .select_related("player")
                .order_by("id")
            )
            if self.can_pick_lead:
                if team_a:
                    self.fields["team_a_player_1"].initial = team_a[0].player
                    if len(team_a) > 1:
                        self.fields["partner"].initial = team_a[1].player
                if team_b:
                    self.fields["opponent_1"].initial = team_b[0].player
                if len(team_b) > 1:
                    self.fields["opponent_2"].initial = team_b[1].player
            else:
                user_in_team_b = bool(user and any(p.player_id == user.id for p in team_b))
                my_team = team_b if user_in_team_b else team_a
                opp_team = team_a if user_in_team_b else team_b

                partners = [p.player for p in my_team if not user or p.player_id != user.id]
                if partners:
                    self.fields["partner"].initial = partners[0]
                if opp_team:
                    self.fields["opponent_1"].initial = opp_team[0].player
                if len(opp_team) > 1:
                    self.fields["opponent_2"].initial = opp_team[1].player

                if user_in_team_b and not self.is_bound:
                    self.initial["team_a_score"] = self.instance.team_b_score
                    self.initial["team_b_score"] = self.instance.team_a_score
                    self.initial["game_2_team_a"] = self.instance.game_2_team_b
                    self.initial["game_2_team_b"] = self.instance.game_2_team_a
                    self.initial["game_3_team_a"] = self.instance.game_3_team_b
                    self.initial["game_3_team_b"] = self.instance.game_3_team_a
        elif user and getattr(user, "home_court", "") and not self.fields["location"].initial:
            self.fields["location"].initial = user.home_court

        for field in self.fields.values():
            existing = field.widget.attrs.get("class", "")
            field.widget.attrs["class"] = f"{existing} field-input".strip()

    def clean_location(self):
        location = (self.cleaned_data.get("location") or "").strip()
        if not location:
            raise forms.ValidationError("Please enter the court or venue where the match was played.")
        return location

    def clean_played_at(self):
        played_at = self.cleaned_data.get("played_at")
        if played_at and played_at > timezone.localdate():
            raise forms.ValidationError("Match date cannot be in the future.")
        return played_at

    def _validate_game_pair(self, score_a, score_b, field_a, field_b, game_num):
        if score_a == score_b:
            self.add_error(field_b, f"Game {game_num}: Pickleball games cannot end in a tie.")
            return False
        winner_score = max(score_a, score_b)
        margin = abs(score_a - score_b)
        if winner_score < 11:
            self.add_error(field_a, f"Game {game_num}: Winning score must be at least 11 points.")
            return False
        if margin < 2:
            self.add_error(field_b, f"Game {game_num}: Winner must win by at least 2 points.")
            return False
        return True

    def clean(self):
        cleaned_data = super().clean()
        match_type = cleaned_data.get("match_type")
        g1_a = cleaned_data.get("team_a_score")
        g1_b = cleaned_data.get("team_b_score")
        g2_a = cleaned_data.get("game_2_team_a")
        g2_b = cleaned_data.get("game_2_team_b")
        g3_a = cleaned_data.get("game_3_team_a")
        g3_b = cleaned_data.get("game_3_team_b")

        g1_valid = False
        if g1_a is not None and g1_b is not None:
            g1_valid = self._validate_game_pair(g1_a, g1_b, "team_a_score", "team_b_score", 1)

        g2_present = g2_a is not None or g2_b is not None
        g3_present = g3_a is not None or g3_b is not None

        g2_valid = False
        if g2_present:
            if g2_a is None or g2_b is None:
                self.add_error("game_2_team_b", "Enter both scores for Game 2, or leave both blank.")
            else:
                g2_valid = self._validate_game_pair(g2_a, g2_b, "game_2_team_a", "game_2_team_b", 2)

        if g3_present:
            if not g2_present:
                self.add_error("game_3_team_a", "Enter Game 2 before recording Game 3.")
            elif g3_a is None or g3_b is None:
                self.add_error("game_3_team_b", "Enter both scores for Game 3, or leave both blank.")
            else:
                self._validate_game_pair(g3_a, g3_b, "game_3_team_a", "game_3_team_b", 3)
                if g1_valid and g2_valid and ((g1_a > g1_b) == (g2_a > g2_b)):
                    self.add_error("game_3_team_a", "Game 3 is not needed when the match already ended 2–0.")
        elif g1_valid and g2_valid and ((g1_a > g1_b) != (g2_a > g2_b)):
            self.add_error("game_3_team_a", "Series is tied 1–1; enter Game 3 to determine the match winner.")

        chosen_lead = cleaned_data.get("team_a_player_1")
        lead_player = chosen_lead if (self.can_pick_lead and chosen_lead is not None) else self.user

        partner = cleaned_data.get("partner")
        opponent_1 = cleaned_data.get("opponent_1")
        opponent_2 = cleaned_data.get("opponent_2")

        if match_type == Match.MatchType.SINGLES:
            cleaned_data["partner"] = None
            cleaned_data["opponent_2"] = None
            partner = None
            opponent_2 = None
        elif match_type == Match.MatchType.DOUBLES:
            if not partner:
                self.add_error("partner", "Select a partner for a doubles match.")
            if not opponent_2:
                self.add_error("opponent_2", "Select a second opponent for a doubles match.")

        selected = [p for p in (lead_player, partner, opponent_1, opponent_2) if p is not None]
        seen_ids = set()
        duplicate_found = False
        for player in selected:
            if player.pk in seen_ids:
                duplicate_found = True
                break
            seen_ids.add(player.pk)

        if duplicate_found:
            raise forms.ValidationError("Each player can only appear once in a match.")

        cleaned_data["_team_a_players"] = [p for p in (lead_player, partner) if p is not None]
        cleaned_data["_team_b_players"] = [p for p in (opponent_1, opponent_2) if p is not None]
        return cleaned_data

    def save_with_participants(self, submitted_by):
        with transaction.atomic():
            match = super().save(commit=False)
            if not match.pk:
                match.submitted_by = submitted_by
                match.club = None
                match.status = Match.Status.PENDING
                match.source = Match.Source.CASUAL_PEER
            elif self.can_pick_lead:
                if match.status == Match.Status.SCHEDULED and match.has_scores:
                    match.status = Match.Status.VERIFIED
                    match.verified_by = self.user or submitted_by
                    match.verified_at = timezone.now()
            else:
                # Any player edit/counter-proposal resets verification and requires the opposing side to confirm
                match.submitted_by = self.user or submitted_by
                match.status = Match.Status.PENDING
                match.verified_by = None
                match.verified_at = None
                match.disputed_by = None
                match.dispute_reason = ""
            match.save()

            match.participants.all().delete()
            participants = [
                MatchParticipant(match=match, player=player, team=MatchParticipant.Team.TEAM_A)
                for player in self.cleaned_data["_team_a_players"]
            ] + [
                MatchParticipant(match=match, player=player, team=MatchParticipant.Team.TEAM_B)
                for player in self.cleaned_data["_team_b_players"]
            ]
            MatchParticipant.objects.bulk_create(participants)
            if hasattr(match, "_prefetched_objects_cache"):
                match._prefetched_objects_cache.clear()
            return match


class MatchDisputeForm(forms.Form):
    dispute_reason = forms.CharField(
        label="Reason for dispute",
        max_length=500,
        widget=forms.Textarea(
            attrs={
                "class": "field-input",
                "rows": 3,
                "placeholder": "Describe what is inaccurate (e.g., final score or player assignment).",
            }
        ),
    )

    def clean_dispute_reason(self):
        reason = (self.cleaned_data.get("dispute_reason") or "").strip()
        if len(reason) < 5:
            raise forms.ValidationError("Please provide a clear reason (at least 5 characters) for disputing this match.")
        return reason
