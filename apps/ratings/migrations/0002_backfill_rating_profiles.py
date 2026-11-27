from decimal import Decimal

from django.conf import settings
from django.db import migrations


def backfill_profiles(apps, schema_editor):
    app_label, model_name = settings.AUTH_USER_MODEL.split(".")
    User = apps.get_model(app_label, model_name)
    PlayerRatingProfile = apps.get_model("ratings", "PlayerRatingProfile")

    existing_user_ids = set(PlayerRatingProfile.objects.values_list("user_id", flat=True))
    to_create = [
        PlayerRatingProfile(
            user_id=uid,
            singles_rating=Decimal("3.000"),
            doubles_rating=Decimal("3.000"),
            singles_reliability=0,
            doubles_reliability=0,
            singles_matches_count=0,
            doubles_matches_count=0,
        )
        for uid in User.objects.values_list("id", flat=True)
        if uid not in existing_user_ids
    ]
    if to_create:
        PlayerRatingProfile.objects.bulk_create(to_create)


class Migration(migrations.Migration):
    dependencies = [
        ("ratings", "0001_initial"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.RunPython(backfill_profiles, migrations.RunPython.noop),
    ]
