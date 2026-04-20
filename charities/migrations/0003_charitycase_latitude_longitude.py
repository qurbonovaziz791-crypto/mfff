from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("charities", "0002_charity_status_category_complaint"),
    ]

    operations = [
        migrations.AddField(
            model_name="charitycase",
            name="latitude",
            field=models.DecimalField(
                blank=True,
                decimal_places=6,
                help_text="Xaritadan tanlangan nuqta (ixtiyoriy).",
                max_digits=9,
                null=True,
                verbose_name="Kenglik (xarita)",
            ),
        ),
        migrations.AddField(
            model_name="charitycase",
            name="longitude",
            field=models.DecimalField(
                blank=True,
                decimal_places=6,
                help_text="Xaritadan tanlangan nuqta (ixtiyoriy).",
                max_digits=9,
                null=True,
                verbose_name="Uzunlik (xarita)",
            ),
        ),
    ]
