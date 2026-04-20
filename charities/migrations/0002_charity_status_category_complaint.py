import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


def copy_published_to_status(apps, schema_editor):
    CharityCase = apps.get_model("charities", "CharityCase")
    for row in CharityCase.objects.all():
        row.status = "published" if row.is_published else "draft"
        row.save(update_fields=["status"])


class Migration(migrations.Migration):
    dependencies = [
        ("charities", "0001_initial"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name="charitycase",
            name="status",
            field=models.CharField(
                choices=[
                    ("draft", "Qoralama"),
                    ("review", "Tekshiruvda"),
                    ("published", "Nashr etilgan"),
                    ("closed", "Yopilgan / yordam yakunlandi"),
                ],
                db_index=True,
                default="draft",
                max_length=20,
                verbose_name="Holat",
            ),
        ),
        migrations.AddField(
            model_name="charitycase",
            name="category",
            field=models.CharField(
                choices=[
                    ("medical", "Tibbiy"),
                    ("education", "Ta’lim"),
                    ("housing", "Uy-joy"),
                    ("emergency", "Favqulodda"),
                    ("family", "Oilaviy"),
                    ("food", "Oziq-ovqat"),
                    ("other", "Boshqa"),
                ],
                db_index=True,
                default="other",
                max_length=20,
                verbose_name="Kategoriya",
            ),
        ),
        migrations.AddField(
            model_name="charitycase",
            name="goal_amount",
            field=models.DecimalField(
                blank=True,
                decimal_places=0,
                help_text="Kerakli summa. Bo‘sh qoldirsangiz, progress chizig‘i chiqmaydi.",
                max_digits=14,
                null=True,
                verbose_name="Maqsad (so‘m, ixtiyoriy)",
            ),
        ),
        migrations.AddField(
            model_name="charitycase",
            name="collected_amount",
            field=models.DecimalField(
                blank=True,
                decimal_places=0,
                help_text="Hozirgacha yig‘ilgan (qo‘lda yangilanadi).",
                max_digits=14,
                null=True,
                verbose_name="Yig‘ilgan (so‘m, ixtiyoriy)",
            ),
        ),
        migrations.AddField(
            model_name="charitycase",
            name="is_publicly_verified",
            field=models.BooleanField(
                default=False,
                help_text="Yoqilsa, foydalanuvchilar «Admin tekshirgan» degan badge ko‘radi.",
                verbose_name="Saytda «tekshirilgan» belgisi",
            ),
        ),
        migrations.RunPython(copy_published_to_status, migrations.RunPython.noop),
        migrations.RemoveField(
            model_name="charitycase",
            name="is_published",
        ),
        migrations.CreateModel(
            name="CharityComplaint",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("message", models.TextField(max_length=2000, verbose_name="Matn")),
                (
                    "status",
                    models.CharField(
                        choices=[("pending", "Ko‘rib chiqilmoqda"), ("reviewed", "Ko‘rib chiqilgan")],
                        db_index=True,
                        default="pending",
                        max_length=20,
                        verbose_name="Holat",
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "charity_case",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="complaints",
                        to="charities.charitycase",
                        verbose_name="Hayriya",
                    ),
                ),
                (
                    "reporter",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="charity_complaints",
                        to=settings.AUTH_USER_MODEL,
                        verbose_name="Yuborgan",
                    ),
                ),
            ],
            options={
                "verbose_name": "Hayriya shikoyati",
                "verbose_name_plural": "Hayriya shikoyatlari",
                "ordering": ["-created_at"],
            },
        ),
    ]
