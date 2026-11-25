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
        label="Team A — Player 1",
        required=True,
    )
    partner = PlayerChoiceField(
        queryset=User.objects.none(),
        label="Partner (Team A)",
        required=False,
    )
    opponent_1 = PlayerChoiceField(
        queryset=User.objects.none(),
        label="Opponent 1 (Team B)",
        required=True,
    )
    opponent_2 = PlayerChoiceField(
        queryset=User.objects.none(),
        label="Opponent 2 (Team B)",
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
            "notes",
        )
        widgets = {
            "played_at": forms.DateInput(attrs={"type": "date"}),
            "location": forms.TextInput(attrs={"placeholder": "e.g., Cebu Pickleball Center — Court 2"}),
            "team_a_score": forms.NumberInput(attrs={"min": 0, "max": 99, "placeholder": "11"}),
            "team_b_score": forms.NumberInput(attrs={"min": 0, "max": 99, "placeholder": "9"}),
            "notes": forms.Textarea(attrs={"rows": 3, "placeholder": "Optional match notes or rally highlights"}),
        }
        labels = {
            "match_type": "Match format",
            "played_at": "Match date",
            "location": "Court / Venue",
            "team_a_score": "Team A score",
            "team_b_score": "Team B score",
            "notes": "Notes (optional)",
        }

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.user = user
        self.is_organizer = getattr(user, "role", None) == "organizer"

        active_users = User.objects.filter(is_active=True).order_by("first_name", "last_name", "username")

        if self.is_organizer:
            self.fields["team_a_player_1"].queryset = active_users
            self.fields["partner"].queryset = active_users
            self.fields["opponent_1"].queryset = active_users
            self.fields["opponent_2"].queryset = active_users
            if not self.instance.pk and user:
                self.fields["team_a_player_1"].initial = user
        else:
            self.fields.pop("team_a_player_1", None)
            other_users = active_users.exclude(pk=user.pk) if user else active_users
            self.fields["partner"].queryset = other_users
            self.fields["opponent_1"].queryset = other_users
            self.fields["opponent_2"].queryset = other_users
            self.fields["team_a_score"].label = "Your team score (Team A)"
            self.fields["team_b_score"].label = "Opponent score (Team B)"

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
            if self.is_organizer and team_a:
                self.fields["team_a_player_1"].initial = team_a[0].player
                if len(team_a) > 1:
                    self.fields["partner"].initial = team_a[1].player
            elif not self.is_organizer:
                partners = [p.player for p in team_a if not user or p.player_id != user.id]
                if partners:
                    self.fields["partner"].initial = partners[0]

            if team_b:
                self.fields["opponent_1"].initial = team_b[0].player
            if len(team_b) > 1:
                self.fields["opponent_2"].initial = team_b[1].player
        elif user and getattr(user, "home_court", ""):
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

    def clean(self):
        cleaned_data = super().clean()
        match_type = cleaned_data.get("match_type")
        score_a = cleaned_data.get("team_a_score")
        score_b = cleaned_data.get("team_b_score")

        if score_a is not None and score_b is not None:
            if score_a == score_b:
                self.add_error("team_b_score", "Pickleball matches cannot end in a tie.")
            else:
                winner_score = max(score_a, score_b)
                margin = abs(score_a - score_b)
                if winner_score < 11:
                    self.add_error("team_a_score", "Winning score must be at least 11 points.")
                elif margin < 2:
                    self.add_error("team_b_score", "Winner must win by at least 2 points.")

        lead_player = cleaned_data.get("team_a_player_1") if self.is_organizer else self.user
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
                match.status = Match.Status.PENDING
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
            return match
