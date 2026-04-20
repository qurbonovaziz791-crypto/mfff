import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models

import charities.models as charity_models


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="CharityCase",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("title", models.CharField(max_length=200, verbose_name="Sarlavha")),
                ("slug", models.SlugField(blank=True, max_length=220, unique=True, verbose_name="Slug (URL)")),
                ("teaser", models.CharField(help_text="Reels/kartochkada ko‘rinadigan qisqa matn.", max_length=280, verbose_name="Qisqa tavsif (kartochkada)")),
                ("body", models.TextField(help_text="Batafsil sahifada to‘liq chiqadi.", verbose_name="Batafsil matn (maqola)")),
                ("video", models.FileField(blank=True, help_text="Qisqa video (reels uslubi). Ixtiyoriy — bo‘lmasa faqat matn va rasm.", null=True, upload_to=charity_models.charity_video_path, verbose_name="Video")),
                ("poster", models.ImageField(blank=True, help_text="Videoning kapak rasmi yoki alohida foto.", null=True, upload_to=charity_models.charity_poster_path, verbose_name="Poster (oldindan ko‘rinish)")),
                ("region", models.CharField(choices=[("tashkent_city", "Toshkent shahri"), ("tashkent", "Toshkent viloyati"), ("andijan", "Andijon viloyati"), ("bukhara", "Buxoro viloyati"), ("fergana", "Farg'ona viloyati"), ("jizzakh", "Jizzax viloyati"), ("namangan", "Namangan viloyati"), ("navoi", "Navoiy viloyati"), ("kashkadarya", "Qashqadaryo viloyati"), ("samarkand", "Samarqand viloyati"), ("sirdarya", "Sirdaryo viloyati"), ("surkhandarya", "Surxondaryo viloyati"), ("khorezm", "Xorazm viloyati"), ("karakalpakstan", "Qoraqalpog'iston Respublikasi")], max_length=50, verbose_name="Viloyat")),
                ("district", models.CharField(max_length=120, verbose_name="Tuman / shahar")),
                ("address", models.TextField(help_text="Yordam yetkazish yoki aloqa uchun.", verbose_name="Manzil")),
                ("contact_phone", models.CharField(max_length=32, verbose_name="Aloqa telefoni")),
                ("payment_info", models.TextField(blank=True, help_text="Ehtiyotkorlik: ochiq internetda to‘liq karta raqamini ko‘rsatish firibgarlik xavfini oshiradi. Maslahat: bank/hisob nomi + oxirgi 4 raqam yoki Click/Payme havola.", verbose_name="To‘lov / karta ma’lumoti")),
                ("is_published", models.BooleanField(db_index=True, default=False, verbose_name="Saytda ko‘rsatish")),
                ("sort_order", models.PositiveIntegerField(default=0, verbose_name="Tartib (kichik = yuqorida)")),
                ("verified_note", models.CharField(blank=True, help_text="Masalan: «2026-04 uyga borib ko‘rildi» — faqat admin.", max_length=200, verbose_name="Tekshiruv eslatmasi (ichki)")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("created_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="charity_cases_created", to=settings.AUTH_USER_MODEL, verbose_name="Kiritgan")),
            ],
            options={
                "verbose_name": "Hayriya holati",
                "verbose_name_plural": "Hayriya holatlari",
                "ordering": ["sort_order", "-created_at"],
            },
        ),
    ]
