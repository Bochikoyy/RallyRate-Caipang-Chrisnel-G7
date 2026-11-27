from django.db import migrations


def normalize_legacy_organizer_roles(apps, schema_editor):
    User = apps.get_model("accounts", "User")
    User.objects.filter(role="organizer").update(role="player")


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0004_notification"),
    ]

    operations = [
        migrations.RunPython(normalize_legacy_organizer_roles, migrations.RunPython.noop),
    ]
