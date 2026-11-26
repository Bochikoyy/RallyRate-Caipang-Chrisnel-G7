from django import forms
from django.contrib.auth import get_user_model
from django.utils import timezone

from .models import Club, ClubEvent

User = get_user_model()


class ClubForm(forms.ModelForm):
    class Meta:
        model = Club
        fields = ("name", "home_court", "description", "is_public")
        widgets = {
            "name": forms.TextInput(attrs={"class": "field-input", "placeholder": "e.g., Cebu Smashers Pickleball Club"}),
            "home_court": forms.TextInput(attrs={"class": "field-input", "placeholder": "e.g., Metrosports Lahug · Courts 1–4"}),
            "description": forms.Textarea(
                attrs={
                    "class": "field-input",
                    "rows": 3,
                    "placeholder": "Share club schedule, skill levels welcome, and court etiquette.",
                }
            ),
            "is_public": forms.CheckboxInput(),
        }
        labels = {
            "name": "Club name",
            "home_court": "Primary court / venue",
            "description": "About this club",
            "is_public": "Public club (visible in directory & open for instant join)",
        }

    def clean_name(self):
        name = (self.cleaned_data.get("name") or "").strip()
        if len(name) < 3:
            raise forms.ValidationError("Club name must be at least 3 characters.")
        return name

    def clean_home_court(self):
        court = (self.cleaned_data.get("home_court") or "").strip()
        if not court:
            raise forms.ValidationError("Please enter the club's primary court or venue.")
        return court


class JoinClubCodeForm(forms.Form):
    join_code = forms.CharField(
        label="Club invite code",
        max_length=16,
        widget=forms.TextInput(
            attrs={
                "class": "field-input",
                "placeholder": "e.g., RR-7K4M9P",
                "autocomplete": "off",
            }
        ),
    )

    def clean_join_code(self):
        code = (self.cleaned_data.get("join_code") or "").strip().upper()
        if not code:
            raise forms.ValidationError("Enter a club invite code.")
        return code


class ClubEventForm(forms.ModelForm):
    starts_at = forms.DateTimeField(
        label="Session date & time",
        input_formats=["%Y-%m-%dT%H:%M", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M"],
        widget=forms.DateTimeInput(
            format="%Y-%m-%dT%H:%M",
            attrs={"type": "datetime-local", "class": "field-input"},
        ),
    )

    class Meta:
        model = ClubEvent
        fields = (
            "title",
            "location",
            "starts_at",
            "format",
            "matchmaking_mode",
            "courts_count",
            "max_players",
            "notes",
        )
        widgets = {
            "title": forms.TextInput(attrs={"class": "field-input", "placeholder": "e.g., Friday Night Open Play"}),
            "location": forms.TextInput(attrs={"class": "field-input", "placeholder": "e.g., Courts 1 & 2"}),
            "format": forms.Select(attrs={"class": "field-input"}),
            "matchmaking_mode": forms.Select(attrs={"class": "field-input"}),
            "courts_count": forms.NumberInput(attrs={"class": "field-input", "min": 1, "max": 20}),
            "max_players": forms.NumberInput(attrs={"class": "field-input", "min": 2, "max": 128}),
            "notes": forms.Textarea(
                attrs={
                    "class": "field-input",
                    "rows": 2,
                    "placeholder": "Optional session rules, warm-up time, or ball info.",
                }
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if not self.instance.pk and not self.is_bound:
            now_local = timezone.localtime().replace(minute=0, second=0, microsecond=0)
            self.fields["starts_at"].initial = now_local.strftime("%Y-%m-%dT%H:%M")

    def clean_max_players(self):
        val = self.cleaned_data.get("max_players") or 0
        fmt = self.cleaned_data.get("format")
        min_req = 4 if fmt == ClubEvent.Format.DOUBLES else 2
        if val < min_req:
            raise forms.ValidationError(f"At least {min_req} players are required for {fmt}.")
        return val


class EventScoreForm(forms.Form):
    team_a_score = forms.IntegerField(min_value=0, max_value=99, required=True)
    team_b_score = forms.IntegerField(min_value=0, max_value=99, required=True)
    game_2_team_a = forms.IntegerField(min_value=0, max_value=99, required=False)
    game_2_team_b = forms.IntegerField(min_value=0, max_value=99, required=False)
    game_3_team_a = forms.IntegerField(min_value=0, max_value=99, required=False)
    game_3_team_b = forms.IntegerField(min_value=0, max_value=99, required=False)

    def _validate_pair(self, a, b, label):
        if a == b:
            raise forms.ValidationError(f"{label}: Pickleball games cannot end in a tie.")
        if max(a, b) < 11:
            raise forms.ValidationError(f"{label}: Winning score must be at least 11 points.")
        if abs(a - b) < 2:
            raise forms.ValidationError(f"{label}: Winner must win by at least 2 points.")

    def clean(self):
        cleaned = super().clean()
        g1_a, g1_b = cleaned.get("team_a_score"), cleaned.get("team_b_score")
        g2_a, g2_b = cleaned.get("game_2_team_a"), cleaned.get("game_2_team_b")
        g3_a, g3_b = cleaned.get("game_3_team_a"), cleaned.get("game_3_team_b")

        if g1_a is None or g1_b is None:
            raise forms.ValidationError("Enter both Team A and Team B scores for Game 1.")
        self._validate_pair(g1_a, g1_b, "Game 1")

        g2_any = g2_a is not None or g2_b is not None
        g3_any = g3_a is not None or g3_b is not None

        if g2_any:
            if g2_a is None or g2_b is None:
                raise forms.ValidationError("Enter both scores for Game 2, or leave both blank.")
            self._validate_pair(g2_a, g2_b, "Game 2")

        if g3_any:
            if not g2_any:
                raise forms.ValidationError("Enter Game 2 before recording Game 3.")
            if g3_a is None or g3_b is None:
                raise forms.ValidationError("Enter both scores for Game 3, or leave both blank.")
            self._validate_pair(g3_a, g3_b, "Game 3")
            if (g1_a > g1_b) == (g2_a > g2_b):
                raise forms.ValidationError("Game 3 is not needed when the match already ended 2–0.")
        elif g2_any and ((g1_a > g1_b) != (g2_a > g2_b)):
            raise forms.ValidationError("Series is tied 1–1; enter Game 3 to determine the winner.")

        return cleaned


class CustomEventMatchForm(forms.Form):
    team_a_1 = forms.ModelChoiceField(queryset=User.objects.none(), label="Team A · Player 1")
    team_a_2 = forms.ModelChoiceField(queryset=User.objects.none(), label="Team A · Partner", required=False)
    team_b_1 = forms.ModelChoiceField(queryset=User.objects.none(), label="Team B · Player 1")
    team_b_2 = forms.ModelChoiceField(queryset=User.objects.none(), label="Team B · Partner", required=False)

    def __init__(self, *args, event=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.event = event
        qs = User.objects.none()
        if event is not None:
            qs = User.objects.filter(
                event_participations__event=event,
                is_active=True,
            ).order_by("first_name", "last_name", "username")

        for field_name in ("team_a_1", "team_a_2", "team_b_1", "team_b_2"):
            field = self.fields[field_name]
            field.queryset = qs
            field.widget.attrs["class"] = "field-input"
            field.label_from_instance = lambda u: (
                f"{u.first_name} {u.last_name}".strip() or u.email or u.username
            )

        if event and event.format == ClubEvent.Format.SINGLES:
            self.fields.pop("team_a_2", None)
            self.fields.pop("team_b_2", None)
        else:
            self.fields["team_a_2"].required = True
            self.fields["team_b_2"].required = True

    def clean(self):
        cleaned = super().clean()
        players = [
            p
            for p in (
                cleaned.get("team_a_1"),
                cleaned.get("team_a_2"),
                cleaned.get("team_b_1"),
                cleaned.get("team_b_2"),
            )
            if p is not None
        ]
        ids = [p.pk for p in players]
        if len(ids) != len(set(ids)):
            raise forms.ValidationError("Each player in a matchup must be distinct.")
        return cleaned
