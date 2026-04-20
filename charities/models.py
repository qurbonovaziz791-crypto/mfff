import uuid
from decimal import Decimal
from typing import Optional

from django.conf import settings
from django.db import models
from django.urls import reverse
from django.utils.text import slugify

from users.models import Region


def charity_video_path(instance, filename):
    return f"charity/videos/{uuid.uuid4().hex}_{filename}"


def charity_poster_path(instance, filename):
    return f"charity/posters/{uuid.uuid4().hex}_{filename}"


class CharityStatus(models.TextChoices):
    DRAFT = "draft", "Qoralama"
    REVIEW = "review", "Tekshiruvda"
    PUBLISHED = "published", "Nashr etilgan"
    CLOSED = "closed", "Yopilgan / yordam yakunlandi"


class CharityCategory(models.TextChoices):
    MEDICAL = "medical", "Tibbiy"
    EDUCATION = "education", "Ta’lim"
    HOUSING = "housing", "Uy-joy"
    EMERGENCY = "emergency", "Favqulodda"
    FAMILY = "family", "Oilaviy"
    FOOD = "food", "Oziq-ovqat"
    OTHER = "other", "Boshqa"


class CharityCase(models.Model):
    """
    Hayriya holati — faqat admin/staff tizimga kiritadi (shaxsan tekshirilgan).
    """

    title = models.CharField("Sarlavha", max_length=200)
    slug = models.SlugField("Slug (URL)", max_length=220, unique=True, blank=True)

    teaser = models.CharField(
        "Qisqa tavsif (kartochkada)",
        max_length=280,
        help_text="Reels/kartochkada ko‘rinadigan qisqa matn.",
    )
    body = models.TextField(
        "Batafsil matn (maqola)",
        help_text="Batafsil sahifada to‘liq chiqadi.",
    )

    video = models.FileField(
        "Video",
        upload_to=charity_video_path,
        blank=True,
        null=True,
        help_text="Qisqa video (reels uslubi). Ixtiyoriy — bo‘lmasa faqat matn va rasm.",
    )
    poster = models.ImageField(
        "Poster (oldindan ko‘rinish)",
        upload_to=charity_poster_path,
        blank=True,
        null=True,
        help_text="Videoning kapak rasmi yoki alohida foto.",
    )

    status = models.CharField(
        "Holat",
        max_length=20,
        choices=CharityStatus.choices,
        default=CharityStatus.DRAFT,
        db_index=True,
    )
    category = models.CharField(
        "Kategoriya",
        max_length=20,
        choices=CharityCategory.choices,
        default=CharityCategory.OTHER,
        db_index=True,
    )

    region = models.CharField(
        "Viloyat",
        max_length=50,
        choices=Region.choices,
    )
    district = models.CharField("Tuman / shahar", max_length=120)

    latitude = models.DecimalField(
        "Kenglik (xarita)",
        max_digits=9,
        decimal_places=6,
        null=True,
        blank=True,
        help_text="Xaritadan tanlangan nuqta (ixtiyoriy).",
    )
    longitude = models.DecimalField(
        "Uzunlik (xarita)",
        max_digits=9,
        decimal_places=6,
        null=True,
        blank=True,
        help_text="Xaritadan tanlangan nuqta (ixtiyoriy).",
    )

    address = models.TextField("Manzil", help_text="Yordam yetkazish yoki aloqa uchun.")
    contact_phone = models.CharField("Aloqa telefoni", max_length=32)

    payment_info = models.TextField(
        "To‘lov / karta ma’lumoti",
        blank=True,
        help_text="Ehtiyotkorlik: ochiq internetda to‘liq karta raqamini ko‘rsatish firibgarlik xavfini oshiradi. "
        "Maslahat: bank/hisob nomi + oxirgi 4 raqam yoki Click/Payme havola.",
    )
    payment_click_url = models.URLField(
        "Click havolasi",
        max_length=500,
        blank=True,
        help_text="Rasmiy Click to‘lov havolasi (https://…). Batafsilda «Click» tugmasi chiqadi.",
    )
    payment_payme_url = models.URLField(
        "Payme havolasi",
        max_length=500,
        blank=True,
        help_text="Rasmiy Payme havolasi (https://…).",
    )
    payment_other_label = models.CharField(
        "Qo‘shimcha to‘lov nomi",
        max_length=60,
        blank=True,
        help_text="Masalan: Paynet, Uzum Bank. Bo‘sh bo‘lsa «Boshqa havola» deb chiqadi.",
    )
    payment_other_url = models.URLField(
        "Qo‘shimcha to‘lov havolasi",
        max_length=500,
        blank=True,
        help_text="Boshqa ilova yoki to‘lov sahifasi havolasi.",
    )

    goal_amount = models.DecimalField(
        "Maqsad (so‘m, ixtiyoriy)",
        max_digits=14,
        decimal_places=0,
        null=True,
        blank=True,
        help_text="Kerakli summa. Bo‘sh qoldirsangiz, progress chizig‘i chiqmaydi.",
    )
    collected_amount = models.DecimalField(
        "Yig‘ilgan (so‘m, ixtiyoriy)",
        max_digits=14,
        decimal_places=0,
        null=True,
        blank=True,
        help_text="Hozirgacha yig‘ilgan (qo‘lda yangilanadi).",
    )

    is_publicly_verified = models.BooleanField(
        "Saytda «tekshirilgan» belgisi",
        default=False,
        help_text="Yoqilsa, foydalanuvchilar «Admin tekshirgan» degan badge ko‘radi.",
    )

    sort_order = models.PositiveIntegerField("Tartib (kichik = yuqorida)", default=0)

    verified_note = models.CharField(
        "Tekshiruv eslatmasi (ichki)",
        max_length=200,
        blank=True,
        help_text="Masalan: «2026-04 uyga borib ko‘rildi» — faqat admin.",
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="charity_cases_created",
        verbose_name="Kiritgan",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["sort_order", "-created_at"]
        verbose_name = "Hayriya holati"
        verbose_name_plural = "Hayriya holatlari"

    def __str__(self) -> str:
        return self.title

    @property
    def is_public_on_site(self) -> bool:
        return self.status in (CharityStatus.PUBLISHED, CharityStatus.CLOSED)

    @property
    def collection_percent(self) -> Optional[int]:
        if self.goal_amount is None or self.goal_amount <= 0:
            return None
        coll = self.collected_amount if self.collected_amount is not None else Decimal("0")
        p = (coll * Decimal("100")) / self.goal_amount
        return min(100, int(p))

    def save(self, *args, **kwargs):
        if not self.slug:
            base = slugify(self.title)[:200] or "hayriya"
            self.slug = base
            n = 1
            while CharityCase.objects.filter(slug=self.slug).exclude(pk=self.pk).exists():
                self.slug = f"{base}-{n}"
                n += 1
        super().save(*args, **kwargs)

    def get_absolute_url(self) -> str:
        return reverse("charity_detail", kwargs={"slug": self.slug})


class CharityComplaintStatus(models.TextChoices):
    PENDING = "pending", "Ko‘rib chiqilmoqda"
    REVIEWED = "reviewed", "Ko‘rib chiqilgan"


class CharityComplaint(models.Model):
    """Foydalanuvchi shikoyati — moderatsiya uchun."""

    charity_case = models.ForeignKey(
        CharityCase,
        on_delete=models.CASCADE,
        related_name="complaints",
        verbose_name="Hayriya",
    )
    reporter = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="charity_complaints",
        verbose_name="Yuborgan",
    )
    message = models.TextField("Matn", max_length=2000)
    status = models.CharField(
        "Holat",
        max_length=20,
        choices=CharityComplaintStatus.choices,
        default=CharityComplaintStatus.PENDING,
        db_index=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Hayriya shikoyati"
        verbose_name_plural = "Hayriya shikoyatlari"

    def __str__(self) -> str:
        return f"#{self.pk} — {self.charity_case_id}"


class CharityUpdate(models.Model):
    """Hayriya bo‘yicha qisqa yangilanish/hisobot (admin kiritadi)."""

    charity_case = models.ForeignKey(
        CharityCase,
        on_delete=models.CASCADE,
        related_name="updates",
        verbose_name="Hayriya",
        db_index=True,
    )
    message = models.TextField("Yangilanish matni", max_length=1200)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="charity_updates_created",
        verbose_name="Kiritgan",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Hayriya yangilanishi"
        verbose_name_plural = "Hayriya yangilanishlari"
        indexes = [
            models.Index(fields=["charity_case", "-created_at"]),
        ]

    def __str__(self) -> str:
        return f"update {self.charity_case_id} #{self.pk}"
