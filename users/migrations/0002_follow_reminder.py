# Generated manually for MYFEEL features

from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("users", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="user",
            name="reminder_enabled",
            field=models.BooleanField(default=False, verbose_name="Eslatma yoqilgan"),
        ),
        migrations.AddField(
            model_name="user",
            name="reminder_weekday",
            field=models.PositiveSmallIntegerField(
                default=6,
                help_text="0=du, 1=se, 2=ch, 3=pa, 4=ju, 5=sha, 6=yak",
                verbose_name="Hafta kuni (0=du, 6=yak)",
            ),
        ),
        migrations.AddField(
            model_name="user",
            name="reminder_hour",
            field=models.PositiveSmallIntegerField(default=20, verbose_name="Soat (0–23)"),
        ),
        migrations.CreateModel(
            name="Follow",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "follower",
                    models.ForeignKey(
                        on_delete=models.CASCADE,
                        related_name="following_rel",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "following",
                    models.ForeignKey(
                        on_delete=models.CASCADE,
                        related_name="followers_rel",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
        ),
        migrations.AddConstraint(
            model_name="follow",
            constraint=models.UniqueConstraint(fields=("follower", "following"), name="uniq_follow_pair"),
        ),
        migrations.AddIndex(
            model_name="follow",
            index=models.Index(fields=["following", "follower"], name="users_follo_followi_2b5fbd_idx"),
        ),
    ]
