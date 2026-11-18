from django.contrib.auth.validators import UnicodeUsernameValidator
from django.db import migrations, models
from django.utils.text import slugify


def populate_existing_usernames(apps, schema_editor):
    User = apps.get_model("accounts", "User")
    database = schema_editor.connection.alias
    used = set()

    for user in User.objects.using(database).all().only("pk", "email").iterator():
        base = slugify((user.email or "").partition("@")[0])[:140] or "player"
        candidate = base
        suffix = 1
        while candidate.casefold() in used:
            suffix += 1
            candidate = f"{base[:140 - len(str(suffix))]}{suffix}"
        used.add(candidate.casefold())
        User.objects.using(database).filter(pk=user.pk).update(username=candidate)


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0002_user_phone_number"),
    ]

    operations = [
        migrations.AddField(
            model_name="user",
            name="username",
            field=models.CharField(blank=True, max_length=150, null=True),
        ),
        migrations.RunPython(populate_existing_usernames, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="user",
            name="username",
            field=models.CharField(
                max_length=150,
                unique=True,
                validators=[UnicodeUsernameValidator()],
            ),
        ),
        migrations.AlterField(
            model_name="user",
            name="email",
            field=models.EmailField(
                blank=True,
                max_length=254,
                null=True,
                unique=True,
                verbose_name="email address",
            ),
        ),
    ]
