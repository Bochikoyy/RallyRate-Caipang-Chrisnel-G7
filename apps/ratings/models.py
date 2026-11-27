from decimal import Decimal

from django.conf import settings
from django.db import models


class PlayerRatingProfile(models.Model):
    STARTING_RATING = Decimal("3.000")
    MIN_RATING = Decimal("1.000")
    MAX_RATING = Decimal("8.000")

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="rating_profile",
    )
    singles_rating = models.DecimalField(
        max_digits=4,
        decimal_places=3,
        default=STARTING_RATING,
    )
    doubles_rating = models.DecimalField(
        max_digits=4,
        decimal_places=3,
        default=STARTING_RATING,
    )
    singles_reliability = models.PositiveSmallIntegerField(default=0)
    doubles_reliability = models.PositiveSmallIntegerField(default=0)
    singles_matches_count = models.PositiveIntegerField(default=0)
    doubles_matches_count = models.PositiveIntegerField(default=0)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-doubles_rating", "-singles_rating")

    def __str__(self):
        return f"{self.user} · DBL {self.doubles_rating} / SGL {self.singles_rating}"

    @property
    def primary_format(self):
        if self.doubles_matches_count == 0 and self.singles_matches_count > 0:
            return "Singles"
        return "Doubles"

    @property
    def primary_rating(self):
        if self.doubles_matches_count == 0 and self.singles_matches_count > 0:
            return self.singles_rating
        return self.doubles_rating

    @property
    def primary_reliability(self):
        if self.doubles_matches_count == 0 and self.singles_matches_count > 0:
            return self.singles_reliability
        return self.doubles_reliability


class RatingHistory(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="rating_history",
    )
    match = models.ForeignKey(
        "matches.Match",
        on_delete=models.CASCADE,
        related_name="rating_entries",
    )
    match_type = models.CharField(max_length=10)
    source = models.CharField(max_length=16)
    rating_before = models.DecimalField(max_digits=4, decimal_places=3)
    rating_after = models.DecimalField(max_digits=4, decimal_places=3)
    delta = models.DecimalField(max_digits=5, decimal_places=3)
    reliability_before = models.PositiveSmallIntegerField(default=0)
    reliability_after = models.PositiveSmallIntegerField(default=0)
    expected_score = models.DecimalField(
        max_digits=5,
        decimal_places=4,
        default=Decimal("0.5000"),
    )
    actual_performance = models.DecimalField(
        max_digits=5,
        decimal_places=4,
        default=Decimal("0.5000"),
    )
    mismatch_protected = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-match__played_at", "-created_at", "-id")
        constraints = [
            models.UniqueConstraint(
                fields=["user", "match"],
                name="unique_rating_entry_per_user_match",
            ),
        ]

    def __str__(self):
        sign = "+" if self.delta > 0 else ""
        return f"{self.user} · {self.rating_before} -> {self.rating_after} ({sign}{self.delta})"
