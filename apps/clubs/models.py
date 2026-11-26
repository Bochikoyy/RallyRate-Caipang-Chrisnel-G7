import secrets

from django.conf import settings
from django.db import models
from django.utils.text import slugify


def _random_join_code():
    alphabet = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
    token = "".join(secrets.choice(alphabet) for _ in range(6))
    return f"RR-{token}"


class Club(models.Model):
    RESERVED_SLUGS = {"create", "join", "leaderboard"}

    name = models.CharField(max_length=120)
    slug = models.SlugField(max_length=140, unique=True)
    description = models.TextField(blank=True)
    home_court = models.CharField(max_length=150)
    join_code = models.CharField(max_length=12, unique=True, db_index=True)
    is_public = models.BooleanField(
        default=True,
        help_text="Public clubs appear in the club directory and allow instant joining.",
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="created_clubs",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("name",)

    def __str__(self):
        return self.name

    @classmethod
    def generate_unique_slug(cls, name, exclude_pk=None):
        base = slugify(name)[:125] or "club"
        if base.lower() in cls.RESERVED_SLUGS:
            base = f"{base}-club"
        candidate = base
        suffix = 1
        qs = cls.objects.all()
        if exclude_pk:
            qs = qs.exclude(pk=exclude_pk)
        while qs.filter(slug__iexact=candidate).exists() or candidate.lower() in cls.RESERVED_SLUGS:
            suffix += 1
            candidate = f"{base[:125 - len(str(suffix)) - 1]}-{suffix}"
        return candidate

    @classmethod
    def generate_unique_join_code(cls, exclude_pk=None):
        qs = cls.objects.all()
        if exclude_pk:
            qs = qs.exclude(pk=exclude_pk)
        code = _random_join_code()
        while qs.filter(join_code__iexact=code).exists():
            code = _random_join_code()
        return code

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = self.generate_unique_slug(self.name, exclude_pk=self.pk)
        if not self.join_code:
            self.join_code = self.generate_unique_join_code(exclude_pk=self.pk)
        super().save(*args, **kwargs)

    def regenerate_join_code(self):
        self.join_code = self.generate_unique_join_code(exclude_pk=self.pk)
        self.save(update_fields=["join_code", "updated_at"])
        return self.join_code

    def membership_for(self, user):
        if not user or not user.is_authenticated:
            return None
        return self.memberships.filter(user=user).first()

    def active_membership_for(self, user):
        if not user or not user.is_authenticated:
            return None
        return self.memberships.filter(user=user, status=ClubMembership.Status.ACTIVE).first()

    def is_member(self, user):
        return self.active_membership_for(user) is not None

    def is_manager(self, user):
        membership = self.active_membership_for(user)
        return bool(
            membership
            and membership.role in (ClubMembership.Role.HOST, ClubMembership.Role.CO_HOST)
        )

    def is_host(self, user):
        membership = self.active_membership_for(user)
        return bool(membership and membership.role == ClubMembership.Role.HOST)


class ClubMembership(models.Model):
    class Role(models.TextChoices):
        HOST = "host", "Host"
        CO_HOST = "co_host", "Co-host"
        MEMBER = "member", "Member"

    class Status(models.TextChoices):
        ACTIVE = "active", "Active"
        PENDING = "pending", "Pending approval"

    club = models.ForeignKey(
        Club,
        on_delete=models.CASCADE,
        related_name="memberships",
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="club_memberships",
    )
    role = models.CharField(
        max_length=12,
        choices=Role.choices,
        default=Role.MEMBER,
    )
    status = models.CharField(
        max_length=12,
        choices=Status.choices,
        default=Status.ACTIVE,
    )
    joined_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("joined_at",)
        constraints = [
            models.UniqueConstraint(fields=["club", "user"], name="unique_club_membership"),
        ]

    def __str__(self):
        return f"{self.user} in {self.club} ({self.get_role_display()})"

    @property
    def is_manager(self):
        return self.status == self.Status.ACTIVE and self.role in (
            self.Role.HOST,
            self.Role.CO_HOST,
        )
