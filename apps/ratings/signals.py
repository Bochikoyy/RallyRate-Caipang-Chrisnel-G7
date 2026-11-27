from django.conf import settings
from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import PlayerRatingProfile


@receiver(post_save, sender=settings.AUTH_USER_MODEL)
def ensure_rating_profile(sender, instance, created, **kwargs):
    if created:
        PlayerRatingProfile.objects.get_or_create(user=instance)
