from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("users", "0011_comment_extra_indexes"),
    ]

    operations = [
        migrations.AlterField(
            model_name="notification",
            name="kind",
            field=models.CharField(
                choices=[
                    ("yaqin_request", "Yaqinlik so‘rovi"),
                    ("collab_invite", "Postga ulashish"),
                    ("dm_message", "Shaxsiy xabar"),
                    ("comment", "Izoh"),
                    ("new_post", "Yangi post"),
                ],
                db_index=True,
                max_length=32,
            ),
        ),
    ]

