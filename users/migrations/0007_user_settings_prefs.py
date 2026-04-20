from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("users", "0006_rename_users_commen_post_ow_3d4e5f_idx_users_comme_post_ow_947a98_idx_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="user",
            name="allow_collab_invites",
            field=models.BooleanField(
                default=True,
                help_text="Boshqalar sizni postiga hammuallif qilib qo‘shishi mumkin.",
                verbose_name="Hammualliflik takliflari",
            ),
        ),
        migrations.AddField(
            model_name="user",
            name="allow_yaqin_requests",
            field=models.BooleanField(
                default=True,
                help_text="Boshqalar sizga yaqin bo‘lish so‘rovi yuborishi mumkin.",
                verbose_name="Yaqin so‘rovlari",
            ),
        ),
        migrations.AddField(
            model_name="user",
            name="compose_autosave_enabled",
            field=models.BooleanField(
                default=True,
                help_text="Hissiyot yozishda avtomatik qoralama saqlash (brauzerda).",
                verbose_name="Compose autosave",
            ),
        ),
        migrations.AddField(
            model_name="user",
            name="default_post_visibility",
            field=models.PositiveSmallIntegerField(
                default=0,
                help_text="0=Faqat men, 1=Havola, 2=Yaqinlar, 3=Ochiq",
                verbose_name="Post ko‘rinishi (default)",
            ),
        ),
    ]

