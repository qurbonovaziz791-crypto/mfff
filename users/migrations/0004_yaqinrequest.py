# Yaqinlarim: o‘zaro tasdiqlangan aloqa (0003 bilan zanjir birlashtirildi)

from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("users", "0003_rename_users_follo_followi_2b5fbd_idx_users_follo_followi_f3cd22_idx"),
    ]

    operations = [
        migrations.CreateModel(
            name="YaqinRequest",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("status", models.CharField(choices=[("pending", "Kutilmoqda"), ("accepted", "Qabul qilingan")], db_index=True, default="pending", max_length=20)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "from_user",
                    models.ForeignKey(
                        on_delete=models.CASCADE,
                        related_name="yaqin_sent",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "to_user",
                    models.ForeignKey(
                        on_delete=models.CASCADE,
                        related_name="yaqin_recv",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
        ),
        migrations.AddConstraint(
            model_name="yaqinrequest",
            constraint=models.UniqueConstraint(fields=("from_user", "to_user"), name="uniq_yaqin_request_pair"),
        ),
        migrations.AddIndex(
            model_name="yaqinrequest",
            index=models.Index(fields=["to_user", "status"], name="users_yaqin_to_user_status"),
        ),
        migrations.AddIndex(
            model_name="yaqinrequest",
            index=models.Index(fields=["from_user", "status"], name="users_yaqin_from_user_status"),
        ),
    ]
