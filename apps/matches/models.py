from django.conf import settings
from django.db import models
from django.utils import timezone


class Match(models.Model):
    class MatchType(models.TextChoices):
        SINGLES = "singles", "Singles"
        DOUBLES = "doubles", "Doubles"

    class Status(models.TextChoices):
        PENDING = "pending", "Pending verification"
        VERIFIED = "verified", "Verified"
        DISPUTED = "disputed", "Disputed"

    submitted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="submitted_matches",
    )
    match_type = models.CharField(
        max_length=10,
        choices=MatchType.choices,
        default=MatchType.SINGLES,
    )
    played_at = models.DateField(default=timezone.localdate)
    location = models.CharField(max_length=150)
    team_a_score = models.PositiveSmallIntegerField()
    team_b_score = models.PositiveSmallIntegerField()
    game_2_team_a = models.PositiveSmallIntegerField(null=True, blank=True)
    game_2_team_b = models.PositiveSmallIntegerField(null=True, blank=True)
    game_3_team_a = models.PositiveSmallIntegerField(null=True, blank=True)
    game_3_team_b = models.PositiveSmallIntegerField(null=True, blank=True)
    status = models.CharField(
        max_length=12,
        choices=Status.choices,
        default=Status.PENDING,
    )
    verified_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="verified_matches",
    )
    verified_at = models.DateTimeField(null=True, blank=True)
    disputed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="disputed_matches",
    )
    dispute_reason = models.TextField(blank=True)
    notes = models.TextField(blank=True)
    players = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        through="MatchParticipant",
        related_name="matches",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-played_at", "-created_at")
        verbose_name_plural = "matches"
        indexes = [
            models.Index(fields=["status", "-played_at"]),
        ]

    def __str__(self):
        return f"{self.get_match_type_display()} at {self.location} ({self.score_display})"

    @property
    def match_code(self):
        return f"RR-{1000 + (self.pk or 0)}"

    @property
    def games(self):
        items = [{"num": 1, "a": self.team_a_score, "b": self.team_b_score}]
        if self.game_2_team_a is not None and self.game_2_team_b is not None:
            items.append({"num": 2, "a": self.game_2_team_a, "b": self.game_2_team_b})
        if self.game_3_team_a is not None and self.game_3_team_b is not None:
            items.append({"num": 3, "a": self.game_3_team_a, "b": self.game_3_team_b})
        return items

    @property
    def series_wins(self):
        wins_a = sum(1 for g in self.games if g["a"] > g["b"])
        wins_b = sum(1 for g in self.games if g["b"] > g["a"])
        return wins_a, wins_b

    @property
    def score_display(self):
        return ", ".join(f"{g['a']}–{g['b']}" for g in self.games)

    @property
    def series_score_display(self):
        if len(self.games) > 1:
            wins_a, wins_b = self.series_wins
            return f"{wins_a} – {wins_b}"
        return f"{self.team_a_score} – {self.team_b_score}"

    @property
    def winner_team(self):
        wins_a, wins_b = self.series_wins
        if wins_a > wins_b:
            return MatchParticipant.Team.TEAM_A
        if wins_b > wins_a:
            return MatchParticipant.Team.TEAM_B
        return None

    @property
    def team_a_participants(self):
        return [p for p in self.participants.all() if p.team == MatchParticipant.Team.TEAM_A]

    @property
    def team_b_participants(self):
        return [p for p in self.participants.all() if p.team == MatchParticipant.Team.TEAM_B]

    @property
    def verification_rows(self):
        submitter_team = self.participant_team_for(self.submitted_by)
        rows = []
        for p in self.participants.all():
            full_name = f"{p.player.first_name} {p.player.last_name}".strip()
            name = full_name or p.player.email or p.player.username

            if p.player_id == self.submitted_by_id:
                label, state = "Submitted", "submitted"
            elif self.status == self.Status.VERIFIED:
                if p.player_id == self.verified_by_id:
                    label, state = "Confirmed", "confirmed"
                elif submitter_team and p.team == submitter_team:
                    label, state = "Confirmed", "confirmed"
                else:
                    label, state = "Confirmed", "confirmed"
            elif self.status == self.Status.DISPUTED:
                if p.player_id == self.disputed_by_id:
                    label, state = "Disputed", "disputed"
                elif submitter_team and p.team == submitter_team:
                    label, state = "Submitted", "submitted"
                else:
                    label, state = "Under review", "awaiting"
            else:
                if submitter_team and p.team == submitter_team:
                    label, state = "Submitted", "submitted"
                else:
                    label, state = "Awaiting", "awaiting"

            rows.append({"name": name, "label": label, "state": state})
        return rows

    def is_organizer(self, user):
        return getattr(user, "role", None) == "organizer"

    def participant_team_for(self, user):
        if not user or not user.is_authenticated:
            return None
        for participant in self.participants.all():
            if participant.player_id == user.id:
                return participant.team
        return None

    def is_opposing_player(self, user):
        user_team = self.participant_team_for(user)
        if user_team is None or user.id == self.submitted_by_id:
            return False
        submitter_team = self.participant_team_for(self.submitted_by)
        if submitter_team is not None:
            return user_team != submitter_team
        return True

    def can_be_viewed_by(self, user):
        if not user or not user.is_authenticated:
            return False
        if self.is_organizer(user) or self.submitted_by_id == user.id:
            return True
        return self.participant_team_for(user) is not None

    def can_be_modified_by(self, user):
        if not user or not user.is_authenticated:
            return False
        if self.is_organizer(user):
            return True
        return self.submitted_by_id == user.id and self.status == self.Status.PENDING

    def can_be_verified_by(self, user):
        if not user or not user.is_authenticated:
            return False
        if self.is_organizer(user):
            return self.status in (self.Status.PENDING, self.Status.DISPUTED)
        return self.status == self.Status.PENDING and self.is_opposing_player(user)

    def can_be_disputed_by(self, user):
        if not user or not user.is_authenticated:
            return False
        if self.is_organizer(user):
            return self.status == self.Status.PENDING
        return self.status == self.Status.PENDING and self.is_opposing_player(user)


class MatchParticipant(models.Model):
    class Team(models.TextChoices):
        TEAM_A = "A", "Team A"
        TEAM_B = "B", "Team B"

    match = models.ForeignKey(
        Match,
        on_delete=models.CASCADE,
        related_name="participants",
    )
    player = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="match_participations",
    )
    team = models.CharField(max_length=1, choices=Team.choices)

    class Meta:
        ordering = ("team", "id")
        constraints = [
            models.UniqueConstraint(
                fields=("match", "player"),
                name="unique_player_per_match",
            ),
        ]

    def __str__(self):
        return f"{self.player} ({self.get_team_display()})"
