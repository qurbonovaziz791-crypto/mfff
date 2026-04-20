from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy as _


class Kayfiyat(models.Model):
    """Post kayfiyati: admin orqali nom, emoji va tur (asosiy / qo‘shimcha)."""

    slug = models.SlugField(
        "Slug (lotin)",
        max_length=64,
        unique=True,
        help_text="Masalan: quvnoq. Postlar SQLite’da shu qiymat bilan saqlanadi.",
    )
    name = models.CharField("Nomi", max_length=64)
    emoji = models.CharField("Emoji yoki qisqa sticker", max_length=32, blank=True)
    is_primary = models.BooleanField(
        "Asosiy to‘rtlikdan biri",
        default=False,
        db_index=True,
        help_text="Yangi postda tepada ko‘rinadigan 4 ta asosiy tanlovdan biri.",
    )
    sort_order = models.PositiveSmallIntegerField("Tartib", default=0)
    is_active = models.BooleanField("Faol", default=True, db_index=True)

    class Meta:
        ordering = ["-is_primary", "sort_order", "name"]
        verbose_name = _("Kayfiyat")
        verbose_name_plural = _("Kayfiyatlar")

    def __str__(self) -> str:
        return f"{self.emoji} {self.name}" if self.emoji else self.name


class Post(models.Model):
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="posts",
        verbose_name=_("Muallif"),
    )

    title = models.CharField(max_length=50, verbose_name=_("Sarlavha"))
    body = models.TextField(max_length=255, verbose_name=_("Xabar matni"))

    hashtag = models.CharField(max_length=100, blank=True, null=True, verbose_name=_("Hashtag"))

    mood = models.CharField(
        max_length=64,
        default="quvnoq",
        verbose_name=_("Kayfiyat"),
        help_text=_("Kayfiyat.slug bilan mos keladi (per-user SQLite ham)."),
    )

    is_public = models.BooleanField(default=False, verbose_name=_("Ochiq post"))

    parent = models.ForeignKey(
        "self",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="replies",
        verbose_name=_("Zanjir boshi"),
    )

    created_at = models.DateTimeField(auto_now_add=True, verbose_name=_("Yaratilgan vaqti"))
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = _("Post")
        verbose_name_plural = _("Postlar")
        indexes = [
            models.Index(fields=["author", "-created_at"]),
            models.Index(fields=["author", "created_at"]),
            models.Index(fields=["hashtag"]),
            models.Index(fields=["is_public", "-created_at"]),
        ]

    def __str__(self):
        return f"{self.author.username} - {self.title} ({self.created_at.strftime('%Y-%m-%d %H:%M:%S')})"

    @property
    def is_thread(self):
        return self.parent is not None or self.replies.exists()
