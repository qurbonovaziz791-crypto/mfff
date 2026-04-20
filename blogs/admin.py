"""
Per-user postlar SQLite orqali saqlanadi; `Post` ORM adminda ko‘rinmaydi.
`Kayfiyat` — barcha postlar uchun kayfiyat nomi va emoji admin orqali.
"""

from django.contrib import admin

from .models import Kayfiyat


@admin.register(Kayfiyat)
class KayfiyatAdmin(admin.ModelAdmin):
    list_display = ("emoji_display", "name", "slug", "is_primary", "sort_order", "is_active")
    list_filter = ("is_primary", "is_active")
    list_editable = ("sort_order", "is_primary", "is_active")
    search_fields = ("name", "slug")
    ordering = ("-is_primary", "sort_order", "name")
    fieldsets = (
        (None, {"fields": ("name", "slug", "emoji")}),
        ("Joylashuv", {"fields": ("is_primary", "sort_order", "is_active")}),
    )

    @admin.display(description="Emoji")
    def emoji_display(self, obj: Kayfiyat) -> str:
        return obj.emoji or "—"
