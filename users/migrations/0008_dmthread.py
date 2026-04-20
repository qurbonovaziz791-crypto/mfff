# Generated manually

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("users", "0007_user_settings_prefs"),
    ]

    operations = [
        migrations.CreateModel(
            name="DMThread",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("last_preview", models.CharField(blank=True, default="", max_length=140)),
                ("unread_for_low", models.PositiveIntegerField(default=0)),
                ("unread_for_high", models.PositiveIntegerField(default=0)),
                (
                    "last_sender",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="+",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "user_high",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="dm_threads_as_high",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "user_low",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="dm_threads_as_low",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "indexes": [
                    models.Index(fields=["user_low", "-updated_at"], name="users_dmthr_user_lo_7a8b9c_idx"),
                    models.Index(fields=["user_high", "-updated_at"], name="users_dmthr_user_hi_7a8b9d_idx"),
                ],
                "constraints": [
                    models.UniqueConstraint(fields=("user_low", "user_high"), name="uniq_dm_thread_pair"),
                ],
            },
        ),
    ]
