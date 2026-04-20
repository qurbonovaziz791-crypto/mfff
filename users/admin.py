from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.utils.html import format_html
from django.utils.translation import gettext_lazy as _
from .models import Comment, FeedPostSeen, Notification, PostCollaboration, User

@admin.register(User)
class MyUserAdmin(UserAdmin):
    # Ro'yxatda (List view) ko'rinadigan ustunlar
    list_display = ('id', 'display_avatar', 'username', 'telegram_id', 'full_name', 'region', 'is_verified_status', 'is_staff')
    
    # Ro'yxatdan turib tahrirlash (tezkor o'zgartirish uchun)
    list_editable = ('region',)
    
    # Filtrlash (O'ng tomonda)
    list_filter = ('is_verified', 'region', 'gender', 'is_staff', 'is_superuser')
    
    # Qidiruv
    search_fields = ('username', 'telegram_id', 'phone', 'first_name', 'last_name', 'email')
    
    # Ma'lumotlarni guruhlarga bo'lib chiqish (Fieldsets)
    fieldsets = (
        (_('Asosiy Akkaunt'), {
            'fields': ('username', 'password', 'telegram_id', 'lk_uuid')
        }),
        (_('Shaxsiy Ma\'lumotlar'), {
            'fields': ('first_name', 'last_name', 'email', 'phone', 'photo', 'gender', 'dob', 'region')
        }),
        (_('Ijtimoiy & Bio'), {
            'fields': ('bio', 'links'),
            'description': _("Foydalanuvchining ijtimoiy tarmoq linklari va qisqacha ma'lumoti")
        }),
        (_('Status va Ruxsatlar'), {
            'fields': ('is_verified', 'is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions'),
        }),
        (_('Muhim Sanalar'), {
            'fields': ('last_login', 'date_joined')
        }),
    )

    # lk_uuid va sanalar readonly bo'lishi kerak
    readonly_fields = ('lk_uuid', 'last_login', 'date_joined')

    # --- Maxsus metodlar (Xatosiz variant) ---

    def full_name(self, obj):
        name = f"{obj.first_name} {obj.last_name}".strip()
        return name if name else obj.username
    full_name.short_description = "F.I.SH"

    def display_avatar(self, obj):
        """Admin panelda avatarni rasmcha qilib ko'rsatish"""
        if obj.photo:
            return format_html(
                '<img src="{}" style="width: 35px; height: 35px; border-radius: 50%; object-fit: cover;" />', 
                obj.photo.url
            )
        return format_html(
            '<div style="width: 35px; height: 35px; border-radius: 50%; background: #ddd; display: flex; align-items: center; justify-content: center; font-size: 9px; color: #666;">{}</div>',
            "N/A"
        )
    display_avatar.short_description = "Avatar"

    def is_verified_status(self, obj):
        """Premium holatini vizual ko'rsatish"""
        if obj.is_verified:
            return format_html(
                '<b style="color: #00acee;">{}</b>', 
                "✔ Premium"
            )
        return format_html(
            '<span style="color: #999;">{}</span>', 
            "Oddiy"
        )
    is_verified_status.short_description = "Status"

    # Superuser yaratganda username avtomatik o'zgarishini inobatga olgan holda
    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "kind", "read_at", "created_at")
    list_filter = ("kind",)
    search_fields = ("user__username",)


@admin.register(PostCollaboration)
class PostCollaborationAdmin(admin.ModelAdmin):
    list_display = ("id", "post_owner", "post_id", "collaborator", "status", "updated_at")
    list_filter = ("status",)


@admin.register(Comment)
class CommentAdmin(admin.ModelAdmin):
    list_display = ("id", "post_owner", "post_id", "author", "created_at")
    search_fields = ("body", "author__username")


@admin.register(FeedPostSeen)
class FeedPostSeenAdmin(admin.ModelAdmin):
    list_display = ("id", "viewer", "post_author", "post_id", "seen_at")