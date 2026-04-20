from django.contrib import admin

from .models import CharityCase, CharityComplaint, CharityUpdate


class CharityUpdateInline(admin.TabularInline):
    model = CharityUpdate
    extra = 0
    fields = ("created_at", "created_by", "message")
    readonly_fields = ("created_at", "created_by")


@admin.register(CharityComplaint)
class CharityComplaintAdmin(admin.ModelAdmin):
    list_display = ("id", "charity_case", "reporter", "status", "created_at")
    list_filter = ("status", "created_at")
    search_fields = ("message", "charity_case__title", "reporter__username")
    readonly_fields = ("created_at", "charity_case", "reporter", "message")
    ordering = ("-created_at",)

    def has_add_permission(self, request):
        return False


@admin.register(CharityCase)
class CharityCaseAdmin(admin.ModelAdmin):
    list_display = (
        "title",
        "status",
        "category",
        "region",
        "district",
        "is_publicly_verified",
        "sort_order",
        "created_at",
    )
    list_filter = ("status", "category", "region", "is_publicly_verified")
    search_fields = ("title", "district", "contact_phone", "slug")
    prepopulated_fields = {"slug": ("title",)}
    readonly_fields = ("created_at", "updated_at", "created_by")
    inlines = [CharityUpdateInline]
    fieldsets = (
        (
            None,
            {
                "fields": (
                    "title",
                    "slug",
                    "status",
                    "category",
                    "sort_order",
                )
            },
        ),
        (
            "Kontent",
            {
                "fields": ("teaser", "body", "video", "poster"),
            },
        ),
        (
            "Maqsad (pul)",
            {
                "fields": ("goal_amount", "collected_amount"),
            },
        ),
        (
            "Joylashuv va aloqa",
            {
                "fields": (
                    "region",
                    "district",
                    "latitude",
                    "longitude",
                    "address",
                    "contact_phone",
                    "payment_info",
                    "payment_click_url",
                    "payment_payme_url",
                    "payment_other_label",
                    "payment_other_url",
                )
            },
        ),
        (
            "Ishonch",
            {
                "fields": ("is_publicly_verified", "verified_note"),
            },
        ),
        (
            "Ichki",
            {
                "fields": ("created_by", "created_at", "updated_at"),
            },
        ),
    )

    def save_model(self, request, obj, form, change):
        if not change and not obj.created_by_id:
            obj.created_by = request.user
        super().save_model(request, obj, form, change)
