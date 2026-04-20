from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("charities", "0003_charitycase_latitude_longitude"),
    ]

    operations = [
        migrations.AddField(
            model_name="charitycase",
            name="payment_click_url",
            field=models.URLField(
                blank=True,
                help_text="Rasmiy Click to‘lov havolasi (https://…). Batafsilda «Click» tugmasi chiqadi.",
                max_length=500,
                verbose_name="Click havolasi",
            ),
        ),
        migrations.AddField(
            model_name="charitycase",
            name="payment_payme_url",
            field=models.URLField(
                blank=True,
                help_text="Rasmiy Payme havolasi (https://…).",
                max_length=500,
                verbose_name="Payme havolasi",
            ),
        ),
        migrations.AddField(
            model_name="charitycase",
            name="payment_other_label",
            field=models.CharField(
                blank=True,
                help_text="Masalan: Paynet, Uzum Bank. Bo‘sh bo‘lsa «Boshqa havola» deb chiqadi.",
                max_length=60,
                verbose_name="Qo‘shimcha to‘lov nomi",
            ),
        ),
        migrations.AddField(
            model_name="charitycase",
            name="payment_other_url",
            field=models.URLField(
                blank=True,
                help_text="Boshqa ilova yoki to‘lov sahifasi havolasi.",
                max_length=500,
                verbose_name="Qo‘shimcha to‘lov havolasi",
            ),
        ),
    ]
