from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.contrib.auth.validators import UnicodeUsernameValidator
from django.db import models
from django.utils.text import slugify


class UserManager(BaseUserManager):
    use_in_migrations = True

    def username_for_email(self, email):
        base = slugify(email.partition("@")[0])[:140] or "player"
        candidate = base
        suffix = 1
        while self.filter(username__iexact=candidate).exists():
            suffix += 1
            candidate = f"{base[:140 - len(str(suffix))]}{suffix}"
        return candidate

    def _create_user(self, username, email=None, password=None, **extra_fields):
        if not username:
            raise ValueError("A username is required.")
        email = self.normalize_email(email).strip().lower() if email else None
        user = self.model(username=username, email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_user(self, email, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", False)
        extra_fields.setdefault("is_superuser", False)
        username = extra_fields.pop("username", None) or self.username_for_email(email)
        return self._create_user(username, email, password, **extra_fields)

    def create_superuser(self, username, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        if extra_fields.get("is_staff") is not True or extra_fields.get("is_superuser") is not True:
            raise ValueError("A superuser must have is_staff=True and is_superuser=True.")
        return self._create_user(username, password=password, **extra_fields)


class User(AbstractUser):
    class Role(models.TextChoices):
        PLAYER = "player", "Player"
        ORGANIZER = "organizer", "Club organizer"

    username = models.CharField(
        max_length=150,
        unique=True,
        validators=[UnicodeUsernameValidator()],
    )
    email = models.EmailField("email address", unique=True, blank=True, null=True)
    role = models.CharField(max_length=12, choices=Role.choices, default=Role.PLAYER)
    phone_number = models.CharField(max_length=30, blank=True)
    preferred_paddle = models.CharField(max_length=100, blank=True)
    home_court = models.CharField(max_length=150, blank=True)

    USERNAME_FIELD = "username"
    REQUIRED_FIELDS = []
    objects = UserManager()

    def __str__(self):
        return self.email or self.username
