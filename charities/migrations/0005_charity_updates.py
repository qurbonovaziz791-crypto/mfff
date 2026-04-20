import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("charities", "0004_charity_payment_links"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="CharityUpdate",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("message", models.TextField(max_length=1200, verbose_name="Yangilanish matni")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "charity_case",
                    models.ForeignKey(
                        db_index=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="updates",
                        to="charities.charitycase",
                        verbose_name="Hayriya",
                    ),
                ),
                (
                    "created_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="charity_updates_created",
                        to=settings.AUTH_USER_MODEL,
                        verbose_name="Kiritgan",
                    ),
                ),
            ],
            options={
                "verbose_name": "Hayriya yangilanishi",
                "verbose_name_plural": "Hayriya yangilanishlari",
                "ordering": ["-created_at"],
            },
        ),
        migrations.AddIndex(
            model_name="charityupdate",
            index=models.Index(fields=["charity_case", "-created_at"], name="charities_c_charity__f8f8cd_idx"),
        ),
    ]

