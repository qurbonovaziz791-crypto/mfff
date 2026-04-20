from django.db import migrations, models


def seed_kayfiyatlar(apps, schema_editor):
    Kayfiyat = apps.get_model("blogs", "Kayfiyat")
    seed = [
        ("quvnoq", "Quvnoq", "😄", True, 0),
        ("xotirjam", "Xotirjam", "😌", True, 1),
        ("joshqin", "Jo'shqin", "🔥", True, 2),
        ("qaygu", "Qayg'u", "😢", True, 3),
    ]
    for slug, name, emoji, is_primary, sort_order in seed:
        Kayfiyat.objects.get_or_create(
            slug=slug,
            defaults={
                "name": name,
                "emoji": emoji,
                "is_primary": is_primary,
                "sort_order": sort_order,
                "is_active": True,
            },
        )


class Migration(migrations.Migration):

    dependencies = [
        ("blogs", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="Kayfiyat",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("slug", models.SlugField(help_text="Masalan: quvnoq. Postlar SQLite’da shu qiymat bilan saqlanadi.", max_length=64, unique=True, verbose_name="Slug (lotin)")),
                ("name", models.CharField(max_length=64, verbose_name="Nomi")),
                ("emoji", models.CharField(blank=True, max_length=32, verbose_name="Emoji yoki qisqa sticker")),
                ("is_primary", models.BooleanField(db_index=True, default=False, help_text="Yangi postda tepada ko‘rinadigan 4 ta asosiy tanlovdan biri.", verbose_name="Asosiy to‘rtlikdan biri")),
                ("sort_order", models.PositiveSmallIntegerField(default=0, verbose_name="Tartib")),
                ("is_active", models.BooleanField(db_index=True, default=True, verbose_name="Faol")),
            ],
            options={
                "verbose_name": "Kayfiyat",
                "verbose_name_plural": "Kayfiyatlar",
                "ordering": ["-is_primary", "sort_order", "name"],
            },
        ),
        migrations.AlterField(
            model_name="post",
            name="mood",
            field=models.CharField(
                default="quvnoq",
                help_text="Kayfiyat.slug bilan mos keladi (per-user SQLite ham).",
                max_length=64,
                verbose_name="Kayfiyat",
            ),
        ),
        migrations.RunPython(seed_kayfiyatlar, migrations.RunPython.noop),
    ]
