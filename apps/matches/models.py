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
        return f"{self.get_match_type_display()} at {self.location} ({self.team_a_score}-{self.team_b_score})"

    @property
    def score_display(self):
        return f"{self.team_a_score} - {self.team_b_score}"

    @property
    def winner_team(self):
        if self.team_a_score > self.team_b_score:
            return MatchParticipant.Team.TEAM_A
        if self.team_b_score > self.team_a_score:
            return MatchParticipant.Team.TEAM_B
        return None

    @property
    def team_a_participants(self):
        return [p for p in self.participants.all() if p.team == MatchParticipant.Team.TEAM_A]

    @property
    def team_b_participants(self):
        return [p for p in self.participants.all() if p.team == MatchParticipant.Team.TEAM_B]

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
